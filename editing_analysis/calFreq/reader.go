package main

import (
	"bufio"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/k0kubun/go-ansi"
	"github.com/schollz/progressbar/v3"
)

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

type ReadStats struct {
	Indel int
	Match int
}

func (rs *ReadStats) Total() int {
	return rs.Indel + rs.Match
}

func (rs *ReadStats) Freq() float32 {
	return float32(rs.Indel) / float32(rs.Total()) * 100
}

func (rs *ReadStats) CorrectedFreq(bg float32) float32 {
	assumeBgIndelReads := float32(rs.Total()) * bg / 100

	return (float32(rs.Indel) - assumeBgIndelReads) / (float32(rs.Total()) - assumeBgIndelReads) * 100
}

func readGzFile(path, match string) map[string]*ReadStats {
	sugar.Infof("读取 %s", path)

	stat, err := os.Stat(path)
	if os.IsNotExist(err) {
		sugar.Fatal(err)
	}
	bar := progressBar(stat.Size(), true)
	defer bar.Finish()
	f, err := os.Open(path)
	if err != nil {
		sugar.Fatal(err)
	}
	defer f.Close()

	progressReaderInstance := &progressReader{
		reader: f,   // 包装原始文件 Reader
		bar:    bar, // 关联进度条
	}
	gz, err := gzip.NewReader(progressReaderInstance)
	if err != nil {
		sugar.Fatal(err)
	}
	defer gz.Close()

	scanner := bufio.NewScanner(gz)

	headers := make([]string, 0)
	res := make(map[string]*ReadStats)
	// optionally, resize scanner's capacity for lines over 64K, see next example
	for scanner.Scan() {
		temp := strings.Split(strings.TrimSpace(scanner.Text()), "\t")
		if len(headers) < 1 {
			headers = temp
		} else {
			row := make(map[string]string)

			for idx, header := range headers {
				row[header] = temp[idx]
			}

			// pam + spacer
			key := fmt.Sprintf("%s|%s", row["pam"], row["spacer"])
			if _, ok := res[key]; !ok {
				res[key] = &ReadStats{0, 0}
			}

			if row["cigar"] == match {
				res[key].Match += 1
			} else {
				res[key].Indel += 1
			}
		}
	}

	if err := scanner.Err(); err != nil {
		sugar.Fatal(err)
	}
	return res
}
