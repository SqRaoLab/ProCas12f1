package main

import (
	"compress/gzip"
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/voxelbrain/goptions"
)

//func validBackground(rs *ReadStats, bgFreq float32, bgCount int) bool {
//	sugar.Debugf("match: %v; indel: %v, freq: %v", rs.Match, rs.Indel, rs.Freq())
//	return rs.Match > 0 && rs.Freq() <= bgFreq && rs.Total() > bgCount
//}

func main() {
	options := defaultParams()
	goptions.ParseAndFail(options)

	if options.Version {
		fmt.Println("version = 0.2.1")
		os.Exit(0)
	}

	if options.Debug {
		setLogger(options.Debug)
	}

	sugar.Infof("calculating background editting frequency")
	bgIndelFreq := readGzFile(options.Background)

	sugar.Infof("calculating the editting frequency")
	indelFreq := readGzFile(options.Input)

	sugar.Infof("adjust editting frequency")

	err := os.MkdirAll(filepath.Dir(options.Output), os.ModePerm)
	if err != nil {
		sugar.Fatal(err)
	}

	w, err := os.Create(options.Output)
	if err != nil {
		sugar.Fatal(err)
	}

	var gzWriter *gzip.Writer
	var writer *csv.Writer
	if strings.HasSuffix(options.Output, ".gz") {
		gzWriter = gzip.NewWriter(w)
		writer = csv.NewWriter(gzWriter)
	} else {
		writer = csv.NewWriter(w)
	}

	// write headers
	var headers []string
	if options.Cas != "" {
		headers = append(headers, "cas")
	}
	headers = append(headers, []string{
		"before", "pam", "spacer",
		"after", "target",
		"bgIndel", "bgTotal", "bgFreq",
		"indel", "total",
		"corrected_efficiency",
		"number_of_edit",
	}...)
	_ = writer.Write(headers)

	bar := progressBar(int64(len(indelFreq)), false)
	for key, rs := range indelFreq {
		_ = bar.Add(1)
		//if rs.Total() < options.ReadCountTres {
		//	continue
		//}
		var row []string
		if options.Cas != "" {
			row = append(row, options.Cas)
		}
		row = append(row, strings.Split(key, "|")...)

		if bgRs, ok := bgIndelFreq[key]; ok {
			//if validBackground(bgRs, options.BgFreq, options.BgCountThres) {
			corrected := rs.CorrectedFreq(bgRs.Freq())
			row = append(row, []string{
				fmt.Sprintf("%d", bgRs.Indel),   // bg indel
				fmt.Sprintf("%d", bgRs.Total()), // bg match
				fmt.Sprintf("%f", bgRs.Freq()),  // bg indel freq
				fmt.Sprintf("%d", rs.Indel),     // genome indel
				fmt.Sprintf("%d", rs.Total()),   // genome total
				fmt.Sprintf("%f", rs.CorrectedFreq(bgRs.Freq())),
				fmt.Sprintf("%v", len(rs.Kind)),
			}...)

			if corrected >= 0 {
				_ = writer.Write(row)
			}
		} else {
			row = append(row, []string{
				fmt.Sprintf("%d", 0),          // bg indel
				fmt.Sprintf("%d", 0),          // bg match
				fmt.Sprintf("%d", 0),          // bg indel freq
				fmt.Sprintf("%d", rs.Indel),   // genome indel
				fmt.Sprintf("%d", rs.Total()), // genome total
				fmt.Sprintf("%f", rs.CorrectedFreq(0)),
				fmt.Sprintf("%v", len(rs.Kind)),
			}...)
			_ = writer.Write(row)
		}
	}
	_ = bar.Finish()

	// force to flush and close file
	if writer != nil {
		writer.Flush()
	}
	if gzWriter != nil {
		_ = gzWriter.Close()
	}

	_ = w.Close()
}
