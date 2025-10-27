package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"sync"

	"github.com/voxelbrain/goptions"
)

// LoadBarcodes 从 JSON 文件加载 barcode 规则
func LoadBarcodes(path string) (map[string][]SampleBarcodeRule, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var raw map[string]map[string][][]string
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	rules := make(map[string][]SampleBarcodeRule)
	for sample, dataMap := range raw {
		for dataKey, pairs := range dataMap {
			for _, pair := range pairs {
				if len(pair) >= 2 {
					if _, ok := rules[sample]; !ok {
						rules[sample] = make([]SampleBarcodeRule, 0)
					}
					rules[sample] = append(rules[sample], SampleBarcodeRule{
						Sample: sample,
						Data:   dataKey,
						Up:     pair[0],
						Down:   pair[1],
					})
				}
			}
		}
	}
	sugar.Infof("Loaded %d barcode rules.\n", len(rules))
	return rules, nil
}

func main() {
	options := defaultParams()
	goptions.ParseAndFail(options)
	setLogger(filepath.Join(options.Output, "splitFq.log"))

	if options.Version {
		sugar.Info("Version: 0.1.0")
		os.Exit(0)
	}

	// 可在此处硬编码路径，或读 config.json
	barcodesFile := options.Barcode
	outputDir := options.Output

	// 创建输出目录
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		log.Fatal(err)
	}

	// 加载 barcode 规则
	rules, err := LoadBarcodes(barcodesFile)
	if err != nil {
		log.Fatal("Load barcodes error: ", err)
	}

	if options.Debug {
		sugar.Infof("%v", rules)
	}

	// 定义 FASTQ 路径模式
	fqPatterns := map[string]string{}
	content, err := os.ReadFile(options.Pool)
	if err != nil {
		sugar.Fatal(err)
	}
	json.Unmarshal(content, &fqPatterns)

	// 收集所有文件对
	// var allPairs = make(map[string][]string)
	fileSize := make(map[string]int64)
	allPairs := make(map[string][]string)
	for group, pattern := range fqPatterns {
		matches, _ := filepath.Glob(pattern)
		sort.Strings(matches)

		if len(matches) < 1 {
			sugar.Fatalf("%v找不到文件", pattern)
		}

		allPairs[group] = matches

		fileSize[group] = 0
		for _, f := range matches {
			if stat, ok := os.Stat(f); !os.IsNotExist(ok) {
				fileSize[group] += stat.Size()
			}
		}
	}

	// 统计总共要读取的文件大小
	total := int64(0)
	for _, rules := range rules {
		// sugar.Infof("%v", rules)
		for _, rule := range rules {
			total += fileSize[rule.Data]
		}
	}

	if options.Debug {
		sugar.Infof("%v", allPairs)
	}

	// 1. 在 main 函数开始处创建全局的 FileWriterCache
	// 并发处理（使用 GOMAXPROCS）
	sugar.Info("分割文件")
	splitOutDir := outputDir // filepath.Join(outputDir, "split")
	os.MkdirAll(splitOutDir, os.ModePerm)

	var workerWg sync.WaitGroup
	bar := progressBar(total, true)
	for _, rules := range rules {
		for _, rule := range rules {
			workerWg.Add(1)
			go ProcessFilePair(allPairs[rule.Data], splitOutDir, rule, bar, &workerWg, options.Or)
		}
	}

	workerWg.Wait()
	bar.Finish()

	sugar.Info("融合输出文件")
	bar = progressBar(int64(len(rules)), false)
	for key := range rules {
		merge(filepath.Join(splitOutDir, fmt.Sprintf("%s*_R1.fq.gz", key)), filepath.Join(outputDir, fmt.Sprintf("%s_R1.fq.gz", key)))
		merge(filepath.Join(splitOutDir, fmt.Sprintf("%s*_R2.fq.gz", key)), filepath.Join(outputDir, fmt.Sprintf("%s_R2.fq.gz", key)))
		bar.Add(1)
	}
	bar.Finish()
	log.Println("✅ All tasks completed.")
}
