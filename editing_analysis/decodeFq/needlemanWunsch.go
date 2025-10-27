package main

import (
	"math"
	"strconv"
	"strings"
)

// --- 配置参数 ---
const (
	MatchScore    = 2  // 匹配得分
	MismatchScore = -1 // 错配得分
	GapPenalty    = -1 // 插入/缺失惩罚
)

// NeedlemanWunsch 使用 Needleman-Wunsch 算法进行全局序列比对。
// 参数:
//
//	seq1: 第一个序列 (通常作为参考序列)。
//	seq2: 第二个序列 (待比对序列)。
//
// 返回:
//
//	score: 最优比对得分。
//	align1: 比对后的seq1。
//	align2: 比对后的seq2。
func NeedlemanWunsch(seq1, seq2 string) (int, string, string) {
	runes1 := []rune(seq1)
	runes2 := []rune(seq2)
	n := len(runes1)
	m := len(runes2)

	// 1. 初始化打分矩阵 (Score Matrix)
	scoreMatrix := make([][]int, n+1)
	for i := range scoreMatrix {
		scoreMatrix[i] = make([]int, m+1)
	}
	// 第一行和第一列初始化为累积的缺口惩罚
	for i := 0; i <= n; i++ {
		scoreMatrix[i][0] = GapPenalty * i
	}
	for j := 0; j <= m; j++ {
		scoreMatrix[0][j] = GapPenalty * j
	}

	// 2. 填充打分矩阵
	for i := 1; i <= n; i++ {
		for j := 1; j <= m; j++ {
			var scoreDiag int
			if runes1[i-1] == runes2[j-1] {
				scoreDiag = scoreMatrix[i-1][j-1] + MatchScore
			} else {
				scoreDiag = scoreMatrix[i-1][j-1] + MismatchScore
			}

			scoreUp := scoreMatrix[i-1][j] + GapPenalty   // seq1 插入 (seq2 缺失)
			scoreLeft := scoreMatrix[i][j-1] + GapPenalty // seq2 插入 (seq1 缺失)

			// 取最大得分
			scoreMatrix[i][j] = max(scoreDiag, max(scoreUp, scoreLeft))
		}
	}

	// 3. 回溯以找到最优比对路径
	align1Runes := make([]rune, 0)
	align2Runes := make([]rune, 0)
	i, j := n, m

	for i > 0 || j > 0 {
		currentScore := scoreMatrix[i][j]
		var scoreDiag, scoreUp, scoreLeft int

		if i > 0 && j > 0 {
			if runes1[i-1] == runes2[j-1] {
				scoreDiag = scoreMatrix[i-1][j-1] + MatchScore
			} else {
				scoreDiag = scoreMatrix[i-1][j-1] + MismatchScore
			}
		} else {
			scoreDiag = math.MinInt32 // 使用一个极小值表示不可达
		}

		if i > 0 {
			scoreUp = scoreMatrix[i-1][j] + GapPenalty
		} else {
			scoreUp = math.MinInt32
		}

		if j > 0 {
			scoreLeft = scoreMatrix[i][j-1] + GapPenalty
		} else {
			scoreLeft = math.MinInt32
		}

		// 根据得分来源决定移动方向
		switch currentScore {
		case scoreDiag:
			align1Runes = append([]rune{runes1[i-1]}, align1Runes...)
			align2Runes = append([]rune{runes2[j-1]}, align2Runes...)
			i--
			j--
		case scoreUp:
			align1Runes = append([]rune{runes1[i-1]}, align1Runes...)
			align2Runes = append([]rune{'-'}, align2Runes...) // seq2 中的缺口
			i--
		case scoreLeft:
			align1Runes = append([]rune{'-'}, align1Runes...) // seq1 中的缺口
			align2Runes = append([]rune{runes2[j-1]}, align2Runes...)
			j--
		}
	}

	return scoreMatrix[n][m], string(align1Runes), string(align2Runes)
}

// GenerateCIGAR 根据比对结果生成 CIGAR 字符串。
// 参数:
//
//	refAligned: 比对后的参考序列。
//	queryAligned: 比对后的查询序列。
//
// 返回:
//
//	cigar: 生成的 CIGAR 字符串。
func GenerateCIGAR(refAligned, queryAligned string) (string, string) {
	var seq strings.Builder
	var cigar strings.Builder
	runesRef := []rune(refAligned)
	runesQuery := []rune(queryAligned)

	currentOp := ""
	currentCount := 0

	for i := 0; i < len(runesRef); i++ {
		var op string
		rChar := runesRef[i]
		qChar := runesQuery[i]

		if rChar == '-' {
			op = "I" // Insertion (相对于参考序列)
			seq.WriteRune('+')
		} else if qChar == '-' {
			op = "D" // Deletion (相对于参考序列)
			seq.WriteRune('-')
		} else {
			op = "M" // Match or Mismatch
			seq.WriteRune(rChar)
		}

		if op == currentOp {
			currentCount++
		} else {
			// 输出之前的块
			if currentCount > 0 && currentOp != "" {
				cigar.WriteString(strconv.Itoa(currentCount))
				cigar.WriteString(currentOp)
			}
			// 开始新的块
			currentOp = op
			currentCount = 1
		}
	}

	// 输出最后一个块
	if currentCount > 0 && currentOp != "" {
		cigar.WriteString(strconv.Itoa(currentCount))
		cigar.WriteString(currentOp)
	}

	return cigar.String(), seq.String()
}
