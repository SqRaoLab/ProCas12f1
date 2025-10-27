package main

import (
	"strings"
)

// subsetString 采用坐标从bytes中截取对应的值
func subsetString(seq string, start, end int) string {
	if start >= 0 && end <= len(seq) && start < end {
		return string(seq[start:end])
	}
	sugar.Debugf("subsetString start and end pos error: %d-%d", start, end)
	return ""
}

// SeqComponent 记录序列中的各种元件
type SeqComponent struct {
	PAM      string
	Edit     string
	Scaffold string
	Behind   string
	Before   string
	Target   string
	After    string
	PrimerR  string
	Spacer   string
	UMI      string
	Cigar    string
	Sketch   string
}

func (s *SeqComponent) Header(umi bool) string {
	headers := []string{"scaffold", "spacer", "before", "pam", "target", "after", "primer_r", "edit", "cigar", "sketch"}
	if umi {
		headers = append(headers, "umi")
	}

	return strings.Join(headers, "\t")
}

// String 将元件转换为可输出的字符串
func (s *SeqComponent) String(umi bool) string {
	vals := []string{s.Scaffold, s.Spacer, s.Before, s.PAM, s.Target, s.After, s.PrimerR, s.Edit, s.Cigar, s.Sketch}
	if umi {
		vals = append(vals, s.UMI)
	}

	return strings.Join(vals, "\t")
}

// findAllIndexes 返回子字符串在主字符串中所有出现的起始索引
func findAllIndexes(text, substr string) []int {
	var indexes []int
	start := 0
	for {
		index := strings.Index(text[start:], substr)
		if index == -1 {
			break
		}
		// 记录全局位置
		globalIndex := start + index
		indexes = append(indexes, globalIndex)
		// 从下一个位置继续查找（避免重复匹配同一个起始点）
		start = start + index + 1
	}
	return indexes
}

// 解析测序序列
func (designSize *DesignSize) decodeString(seq, umi string, library *PoolLibrary) *SeqComponent {
	res := &SeqComponent{}
	// 预计算 designSize 相关偏移
	beforeOffset := designSize.SpacerDistance
	pamLen := designSize.PAMLen

	if umi != "" {
		umiAnchors := strings.Split(umi, "|")
		idxs := make([]int, 0)
		for _, ua := range umiAnchors {
			idxs = append(idxs, strings.Index(seq, ua))
		}

		start, end := 0, 0
		if idxs[0] > 0 {
			start = idxs[0] + len(umiAnchors[0])
		}
		if idxs[1] > 0 {
			end = idxs[1]
		}

		if start > 0 && end > 0 {
			res.UMI = subsetString(seq, start, end)
		} else if start > 0 {
			res.UMI = subsetString(seq, start, start+designSize.UMILen)
		} else if end > 0 {
			res.UMI = subsetString(seq, end-designSize.UMILen, end)
		}
	}

	for scaffold, spacers := range library.Spacer {
		for _, idx := range findAllIndexes(seq, scaffold) {
			// sugar.Debug(seq[idx:(idx+len(scaffold))] == scaffold)
			totalLen := len(scaffold) + designSize.SpacerLen
			if idx+totalLen > len(seq) {
				break
			}

			segment := seq[idx+len(scaffold) : idx+totalLen]

			// 检查该spacer是否为该scaffold对应的spacer
			ok := false
			for _, spacer := range spacers {
				if segment == spacer {
					ok = true
					break
				}
			}
			if !ok {
				continue
			}

			// 检查后续是否匹配任意 spacer
			// 匹配成功
			matchEnd := idx + totalLen // scaffoldSpacer 结束位置
			res.Spacer = segment

			// 提取 Before
			beforeStart := matchEnd + beforeOffset
			beforeEnd := beforeStart + designSize.BeforeLen
			if beforeEnd > len(seq) {
				continue
			}
			res.Before = subsetString(seq, beforeStart, beforeEnd)

			// 提取 PAM
			pamStart := beforeEnd
			pamEnd := pamStart + pamLen
			if pamEnd > len(seq) {
				continue
			}
			res.PAM = subsetString(seq, pamStart, pamEnd)

			// 提取 Target 和 Edit
			targetStart := pamEnd
			editEnd := targetStart + designSize.TargetLen
			if editEnd > len(seq) {
				continue
			}

			res.Target = library.Targets[res.Spacer]
			res.Edit = subsetString(seq, targetStart, editEnd)

			res.After = subsetString(seq, editEnd, editEnd+designSize.BehindLen)
			res.PrimerR = subsetString(seq, editEnd+designSize.BehindLen, editEnd+designSize.BehindLen+designSize.PrimerLen)

			res.Scaffold = scaffold
			_, alignedRef1, alignedQuery1 := NeedlemanWunsch(res.Target, res.Edit)
			cigar, sketch := GenerateCIGAR(alignedRef1, alignedQuery1)
			res.Cigar = cigar
			res.Sketch = sketch
			return res
		}
	}

	return nil
}

// ReadPair 代表一对FASTQ读段
type ReadPair struct {
	ID string
	R1 string
	R2 string
}
