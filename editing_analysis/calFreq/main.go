package main

import (
	"compress/gzip"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/voxelbrain/goptions"
)

func validBackground(rs *ReadStats, bgFreq float32, bgCount int) bool {
	sugar.Debugf("match: %v; indel: %v, freq: %v", rs.Match, rs.Indel, rs.Freq())
	return rs.Match > 0 && rs.Freq() <= bgFreq && rs.Total() > bgCount
}

func main() {
	options := defaultParams()
	goptions.ParseAndFail(options)

	if options.Version {
		fmt.Println("version = 0.0.0")
		os.Exit(0)
	}

	if options.Debug {
		setLogger(options.Debug)
	}

	sugar.Infof("计算背景变量")
	bgIndelFreq := readGzFile(options.Background, options.MatchKey)

	sugar.Infof("统计编辑数量")
	indelFreq := readGzFile(options.Input, options.MatchKey)

	sugar.Infof("计算编辑效率")

	err := os.MkdirAll(filepath.Dir(options.Output), os.ModePerm)
	if err != nil {
		sugar.Fatal(err)
	}

	w, err := os.Create(options.Output)
	if err != nil {
		sugar.Fatal(err)
	}
	defer w.Close()

	gzWriter := gzip.NewWriter(w)
	defer gzWriter.Close()

	fmt.Fprintln(gzWriter, "pam\tspacer\tbgIndel\tbgTotal\tbgFreq\tindel\ttotal\tcorrected_freq")

	bar := progressBar(int64(len(indelFreq)), false)
	for key, rs := range indelFreq {
		bar.Add(1)
		if rs.Total() < options.ReadCountTres {
			continue
		}

		if bgRs, ok := bgIndelFreq[key]; ok {
			if validBackground(bgRs, options.BgFreq, options.BgCountThres) {
				keys := strings.Split(key, "|")

				corrected := rs.CorrectedFreq(bgRs.Freq())
				if corrected >= 0 {
					fmt.Fprintf(gzWriter, "%s\t%s\t%d\t%d\t%f\t%d\t%d\t%f\n",
						keys[0],      // pam
						keys[1],      // spacer,
						bgRs.Indel,   // bg indel
						bgRs.Total(), // bg match
						bgRs.Freq(),  // bg indel freq
						rs.Indel,     // genome indel
						rs.Total(),   // genome total
						rs.CorrectedFreq(bgRs.Freq()),
					)
				}
			}
		}
	}
	bar.Finish()
}
