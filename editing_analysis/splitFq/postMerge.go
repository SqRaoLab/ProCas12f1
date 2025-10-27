package main

import (
	"compress/gzip"
	"io"
	"os"
	"path/filepath"
	"sort"
)

// 后续的文件融合策略
func merge(pattern, outPath string) {
	tempMatches, _ := filepath.Glob(pattern)

	matches := make([]string, 0)
	for _, i := range tempMatches {
		if i == outPath {
			continue
		}
		matches = append(matches, i)
	}

	sort.Strings(matches)

	if len(matches) < 2 {
		os.Rename(matches[0], outPath)
	} else {
		outFile, err := os.Create(outPath)
		if err != nil {
			sugar.Fatal(err)
		}
		defer outFile.Close()
		gz := gzip.NewWriter(outFile)

		for _, path := range matches {
			inFile, err := os.Open(path)
			if err != nil {
				sugar.Fatal(err)
			}
			io.Copy(gz, inFile)
		}
	}
}
