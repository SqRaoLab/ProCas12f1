package main

import (
	"bufio"
	"compress/gzip"
	"io"
	"os"
	"strings"
	"sync"

	"github.com/k0kubun/go-ansi"

	"github.com/schollz/progressbar/v3"
)

// ReadPair 表示一对 FASTQ reads
type Read struct {
	ID, Seq, Qual, Complement string
}

func (r *Read) Id() string {
	id_ := strings.Split(r.ID, " ")[0]
	if strings.Contains(id_, "/1") || strings.Contains(id_, "/2") {
		id_ = strings.Split(id_, "/")[0]
	}
	return id_
}

// SampleBarcodeRule 每个样本的 barcode 规则
type SampleBarcodeRule struct {
	Sample string
	Data   string
	Up     string
	Down   string
}

// --- 文件读取和并发处理 ---
// progressReader 是一个包装器，用于在读取时更新进度条
type progressReader struct {
	reader io.Reader // 原始 Reader (例如 *os.File)
	bar    *progressbar.ProgressBar
}

// Read 实现 io.Reader 接口
func (pr *progressReader) Read(p []byte) (n int, err error) {
	// 调用原始 Reader 的 Read 方法
	n, err = pr.reader.Read(p)
	// 更新进度条
	if n > 0 {
		pr.bar.Add(n)
	}
	return n, err
}

func progressBar(size int64, showBytes bool) *progressbar.ProgressBar {
	if size > 0 {
		return progressbar.NewOptions64(
			size,
			progressbar.OptionSetDescription("Reading"),       // 设置描述
			progressbar.OptionSetWriter(ansi.NewAnsiStderr()), // 使用ansi防止奇怪的换行等显示错误
			progressbar.OptionUseANSICodes(true),              // avoid progressbar downsize error
			progressbar.OptionEnableColorCodes(true),
			progressbar.OptionSetElapsedTime(true),
			progressbar.OptionSetPredictTime(true),
			progressbar.OptionSetWriter(os.Stderr), // 避免 stdout 冲突
			progressbar.OptionShowBytes(showBytes), // 显示已读/总字节数
			progressbar.OptionShowCount(),          // 显示计数（可选）
			progressbar.OptionFullWidth(),          // 全宽显示（可选）
		)
	}
	return progressbar.NewOptions(-1,
		progressbar.OptionSetDescription("Reading"),
		progressbar.OptionSetWriter(ansi.NewAnsiStderr()), // 使用ansi防止奇怪的换行等显示错误
		progressbar.OptionUseANSICodes(true),              // avoid progressbar downsize error
		progressbar.OptionEnableColorCodes(true),
		progressbar.OptionSetItsString("items"),
		progressbar.OptionSpinnerType(14),      // 旋转光标
		progressbar.OptionSetWriter(os.Stderr), // 避免 stdout 冲突
		progressbar.OptionSetItsString("files"),
	)
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

// readFastqInChannel 从gzip压缩的FASTQ文件读取记录，并发送到channel
func readFastqInChannel(filename string, recordChan chan<- Read, wg *sync.WaitGroup, bar *progressbar.ProgressBar) {
	defer wg.Done()
	defer close(recordChan) // 读取完成后关闭channel

	file, err := os.Open(filename)
	if err != nil {
		sugar.Fatalf("Error opening file %s: %v", filename, err)
	}
	defer file.Close()

	var gzReader *gzip.Reader
	if bar != nil {
		// --- 4. 创建进度条包装器 ---
		progressReaderInstance := &progressReader{
			reader: file, // 包装原始文件 Reader
			bar:    bar,  // 关联进度条
		}
		gzReader, err = gzip.NewReader(progressReaderInstance)
		if err != nil {
			sugar.Fatalf("Error creating gzip reader for %s: %v", filename, err)
		}
	} else {
		gzReader, err = gzip.NewReader(file)
		if err != nil {
			sugar.Fatalf("Error creating gzip reader for %s: %v", filename, err)
		}
	}

	if gzReader != nil {
		defer gzReader.Close()
	}

	scanner := bufio.NewScanner(gzReader)
	buffer := make([]string, 0, 4) // 缓冲4行

	for scanner.Scan() {
		line := scanner.Text()
		buffer = append(buffer, line)

		if len(buffer) == 4 { // 一个完整的FASTQ记录
			// 发送记录的副本到channel
			recordCopy := make([]string, 4)
			copy(recordCopy, buffer)
			recordChan <- Read{
				ID:   recordCopy[0],
				Seq:  strings.TrimSpace(recordCopy[1]),
				Qual: strings.TrimSpace(recordCopy[3]),
			}
			buffer = buffer[:0] // 重置缓冲区
		}
	}

	if err := scanner.Err(); err != nil {
		sugar.Fatalf("Error reading from %s: %v", filename, err)
	}

	if bar != nil {
		bar.Finish()
	}

	// 处理文件末尾可能存在的不完整记录（理论上不应存在）
	if len(buffer) > 0 {
		sugar.Infof("Warning: Incomplete FASTQ record found at end of %s", filename)
	}
}
