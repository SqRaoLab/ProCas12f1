package main

import (
	"bufio"
	"compress/gzip"
	"fmt"
	"os"
	"strings"
	"sync"

	"github.com/voxelbrain/goptions"
	"go.uber.org/zap"
)

var (
	sugar      *zap.SugaredLogger
	designSize *DesignSize
	poolLibMap map[string]*PoolLibrary
)

// processPairs 处理读段对
func processPairs(pairChan <-chan *ReadPair, resultChan chan<- string, key string, umi string, reverse bool) {
	for pair := range pairChan {
		reads := []string{pair.R1, pair.R2}
		if reverse {
			reads = []string{reverseComplement(pair.R1), reverseComplement(pair.R2)}
		}
		// 看reverse primer在r1还是r2上
		for _, s := range reads {
			if res := designSize.decodeString(s, umi, poolLibMap[key]); res != nil {
				if umi != "" && res.UMI == "" {
					continue
				}

				outStr := res.String(umi != "")
				if outStr != "" {
					resultChan <- fmt.Sprintf("%s\t%s\t%s", key, pair.ID, outStr)
				}

			}
		}
	}
}

// reverseComplement 返回 DNA 序列的反向互补链
func reverseComplement(seq string) string {
	// 定义互补映射
	complement := map[rune]rune{
		'A': 'T',
		'T': 'A',
		'G': 'C',
		'C': 'G',
		'a': 't', // 可选：支持小写
		't': 'a',
		'g': 'c',
		'c': 'g',
	}

	var builder strings.Builder
	builder.Grow(len(seq)) // 预分配空间，提升性能

	// 从后往前遍历，实现反向 + 互补
	for i := len(seq) - 1; i >= 0; i-- {
		r := rune(seq[i])
		if comp, exists := complement[r]; exists {
			builder.WriteRune(comp)
		} else {
			// 可选：处理非法字符，如 'N' 或其他
			builder.WriteRune(r) // 或 builder.WriteRune('N') 表示未知
		}
	}

	return builder.String()
}

// --- 主函数 ---

func main() {
	options := defaultParams()
	goptions.ParseAndFail(options)
	setLogger(options.Debug)

	if options.Version {
		fmt.Println("Version: 0.1.1")
		os.Exit(0)
	}

	if options.R1 == "" || options.R2 == "" || options.Cas == "" {
		sugar.Errorf("-1, -2, -c参数都需要")
		goptions.PrintHelp()
		os.Exit(0)
	}

	if options.Reverse {
		sugar.Info("启用Reverse模式")
	}

	designSize = &DesignSize{
		TargetLen:      options.TargetLen,
		PAMLen:         options.PAMLen,
		SpacerLen:      options.SpacerLen,
		SpacerDistance: options.SpacerDistance,
		BeforeLen:      options.BeforeLen,
		BehindLen:      options.BehindLen,
		PrimerLen:      options.PrimerLen,
		UMILen:         options.UMILen,
	}

	// 定义条形码集
	poolLibMap = LoadPoolLibrary(options.Pool)
	for key := range poolLibMap {
		sugar.Debugf("Library: %v loaded", key)
	}

	// 创建channel
	r1Chan := make(chan []string, 100) // 缓冲channel
	r2Chan := make(chan []string, 100)
	pairChan := make(chan *ReadPair, 1000)         // 更大的缓冲区以平衡生产者和消费者
	resultChan := make(chan string, options.Procs) // 缓冲区大小等于worker数

	var wg sync.WaitGroup

	// 启动读取goroutine
	wg.Add(2)
	if options.ReadCmd != "" {
		go readFromCmd(options.R1, options.ReadCmd, r1Chan, &wg, true)
		go readFromCmd(options.R2, options.ReadCmd, r2Chan, &wg, false)
	} else {
		go readFastqInChannel(options.R1, r1Chan, &wg, true)
		go readFastqInChannel(options.R2, r2Chan, &wg, false)
	}

	// 启动配对goroutine
	go func() {
		defer close(pairChan)

		for {
			r1Record, ok1 := <-r1Chan
			r2Record, ok2 := <-r2Chan

			if !ok1 || !ok2 {
				break // 如果任一channel关闭，则停止
			}

			// 简单的ID匹配检查 (实际应解析@后的ID)
			// 这里假设顺序严格对应，且ID行格式为 @...
			if len(r1Record) > 0 && len(r2Record) > 0 {
				id1 := strings.SplitN(r1Record[0], " ", 2)[0] // 取第一个空格前的部分

				pairChan <- &ReadPair{
					ID: id1,
					R1: r1Record[1], // 序列行
					R2: r2Record[1], // 序列行
				}
			}
		}
	}()

	// 启动worker goroutine
	var workerWg sync.WaitGroup
	for i := 0; i < options.Procs; i++ {
		workerWg.Add(1)
		go func(id int) {
			defer workerWg.Done()
			sugar.Debugf("processing cas %v", options.Cas)
			processPairs(pairChan, resultChan, options.Cas, options.UMIAnchor, options.Reverse)
		}(i)
	}

	// 等待读取完成
	go func() {
		wg.Wait()
	}()

	// 等待所有worker完成
	go func() {
		workerWg.Wait()
		close(resultChan) // 关闭结果channel
	}()

	// --- 写入结果 ---
	outFile, err := os.Create(options.Output)
	if err != nil {
		sugar.Fatalf("Error creating output file %s: %v", options.Output, err)
	}
	defer outFile.Close()

	var writer *bufio.Writer
	if strings.HasSuffix(options.Output, ".gz") {
		gzFile := gzip.NewWriter(outFile)
		defer gzFile.Close()

		writer = bufio.NewWriter(gzFile)
	} else {
		writer = bufio.NewWriter(outFile)
	}

	defer writer.Flush()

	// 写入表头 pam, spacer, behind, before
	temp := &SeqComponent{}
	writer.WriteString(fmt.Sprintf("CasProtein\tReads\t%s\n", temp.Header(options.UMIAnchor != "")))
	writer.Flush() // 初始刷新

	count := 0
	const flushInterval = 1000 // 每1000行刷新一次

	for res := range resultChan {
		_, err := writer.WriteString(fmt.Sprintln(res))
		if err != nil {
			sugar.Infof("Error writing to output file: %v", err)
			// 可以选择继续或退出
		}
		count++
		if count%flushInterval == 0 {
			err := writer.Flush()
			if err != nil {
				sugar.Infof("Error flushing output file: %v", err)
			}
		}
	}
	// 循环结束后，确保所有缓冲数据都被写入
	err = writer.Flush()
	if err != nil {
		sugar.Infof("Error final flush to output file: %v", err)
	}
	sugar.Infof("Results written to %s", options.Output)
}
