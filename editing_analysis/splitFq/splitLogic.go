package main

import (
	"compress/gzip"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/schollz/progressbar/v3"
)

// FileWriterCache 缓存输出文件句柄
type FileWriterCache struct {
	writers map[string]*gzip.Writer
	files   map[string]*os.File
}

func NewFileWriterCache() *FileWriterCache {
	return &FileWriterCache{
		writers: make(map[string]*gzip.Writer),
		files:   make(map[string]*os.File),
	}
}

func (c *FileWriterCache) GetWriter(sample, readID, outdir string) (*gzip.Writer, error) {
	key := fmt.Sprintf("%s_%s.fq.gz", sample, readID)
	filename := filepath.Join(outdir, key)
	if w, exists := c.writers[key]; exists {
		return w, nil
	}
	file, err := os.Create(filename)
	if err != nil {
		return nil, err
	}

	gz := gzip.NewWriter(file)
	c.writers[key] = gz
	c.files[key] = file
	return gz, nil
}

func (c *FileWriterCache) CloseAll() {
	for key, gz := range c.writers {
		gz.Close()
		c.files[key].Close()
	}
}

// ProcessFilePair 处理一对 R1/R2 FASTQ 文件
func ProcessFilePair(pairs []string, outdir string, rule SampleBarcodeRule, bar *progressbar.ProgressBar, workWg *sync.WaitGroup, enableOr bool) {
	var wg sync.WaitGroup
	defer workWg.Done()
	// 启动读取goroutine
	wg.Add(2)

	r1Path, r2Path := pairs[0], pairs[1]

	// 解析
	r1Ch := make(chan Read, 100) // 缓冲channel
	r2Ch := make(chan Read, 100)

	go readFastqInChannel(r1Path, r1Ch, &wg, bar)
	go readFastqInChannel(r2Path, r2Ch, &wg, bar)

	writerCahce := NewFileWriterCache()
	defer writerCahce.CloseAll()

	var matched, total uint64
	var reads1, reads2 = make(map[string]Read, 0), make(map[string]Read, 0)
	for {
		s1, ok := <-r1Ch
		if !ok {
			break
		}
		s2, ok := <-r2Ch
		if !ok {
			break
		}
		total++

		var r1, r2 = []Read{}, []Read{}
		if s1.Id() == s2.Id() {
			r1 = append(r1, s1)
			r2 = append(r2, s2)
		} else {
			// 如果r2对应的r1已经被收录了，取出来用。没有就记录r2
			if s, ok := reads1[s2.Id()]; ok {
				r1 = append(r1, s)
				r2 = append(r2, s2)
				reads1[s1.Id()] = s1
			} else {
				sugar.Debugf("%s", s2.Id())
				reads2[s2.Id()] = s2
			}
			// 如果r1对应的r2已经被收录了，取出来用。没有就记录r1
			if s, ok := reads2[s1.Id()]; ok {
				r1 = append(r1, s1)
				r2 = append(r2, s)
				reads2[s2.Id()] = s2
			} else {
				sugar.Debugf("%s", s1.Id())
				reads1[s1.Id()] = s1
			}
		}

		if len(r1) != len(r2) {
			sugar.Fatal("!=")
		}

		idx := 0
		for idx < len(r1) {
			// 启用不同的判断标准，默认是上下游对对的上才保留
			barcodeMatch := (strings.Contains(r1[idx].Seq, rule.Up) && strings.Contains(r2[idx].Seq, rule.Down)) ||
				(strings.Contains(r2[idx].Seq, rule.Up) && strings.Contains(r1[idx].Seq, rule.Down)) ||
				(strings.Contains(r1[idx].Complement, rule.Up) && strings.Contains(r2[idx].Complement, rule.Down)) ||
				(strings.Contains(r2[idx].Complement, rule.Up) && strings.Contains(r1[idx].Complement, rule.Down))

			if enableOr {
				barcodeMatch = (strings.Contains(r1[idx].Seq, rule.Up) || strings.Contains(r2[idx].Seq, rule.Down)) ||
					(strings.Contains(r2[idx].Seq, rule.Up) || strings.Contains(r1[idx].Seq, rule.Down))
			}

			if barcodeMatch {
				w1, err := writerCahce.GetWriter(rule.Sample, fmt.Sprintf("%s_R1", rule.Data), outdir)
				if err != nil {
					sugar.Fatal(err)
				}
				w1.Write([]byte(fmt.Sprintf("%s\n%s\n+\n%s\n", r1[idx].ID, r1[idx].Seq, r1[idx].Qual)))

				w2, err := writerCahce.GetWriter(rule.Sample, fmt.Sprintf("%s_R2", rule.Data), outdir)
				if err != nil {
					sugar.Fatal(err)
				}
				w2.Write([]byte(fmt.Sprintf("%s\n%s\n+\n%s\n", r2[idx].ID, r2[idx].Seq, r2[idx].Qual)))

				delete(reads1, s2.Id())
				delete(reads2, s1.Id())
				matched++
			}
			idx += 1
		}
	}
	wg.Wait()
	sugar.Debugf("%s (%s) Done: %d / %d reads matched", rule.Data, rule.Sample, matched, total)
}
