package main

import (
	"strings"
	"sync"
)

// processFilePair 处理一对 R1/R2 FASTQ 文件
func processFilePair(
	readChan chan *ReadPair,
	outputChan map[string]chan *ReadPair,
	rules []SampleBarcodeRule,
	workWg *sync.WaitGroup,
	scaffolds map[string]string,
) {
	for {
		readPair, ok := <-readChan
		if !ok {
			break
		}

		r1, r2 := readPair.R1, readPair.R2

		// iter barcodes for different cas protein
		for _, rule := range rules {
			forward := strings.HasPrefix(r1.Seq, rule.Up) && strings.HasPrefix(r2.Seq, rule.Down)
			reverse := strings.HasPrefix(r2.Seq, rule.Up) && strings.HasPrefix(r1.Seq, rule.Down)

			if scaffolds != nil {
				scaffold, ok := scaffolds[rule.Sample]
				if !ok {
					sugar.Fatalf("scaffold not found for %s", rule.Sample)
				}
				if forward {
					forward = strings.Contains(r1.Seq, scaffold)
				}
				if reverse {
					reverse = strings.Contains(r2.Seq, scaffold)
				}
			}

			readPair.Switch = reverse

			if forward || reverse {
				readPair.Sample = rule.Sample
				outputChan[rule.Sample] <- readPair
				break
			}
		}
	}

	workWg.Done()
}
