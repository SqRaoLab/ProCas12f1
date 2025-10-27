package main

import (
	"encoding/json"
	"io"
	"os"
)

// PoolLibrary
type PoolLibrary struct {
	Key     string              `json:"key"`
	Spacer  map[string][]string `json:"spacer"`
	Targets map[string]string   `json:"targets"`
}

func LoadPoolLibrary(path string) map[string]*PoolLibrary {
	f, err := os.Open(path)
	if err != nil {
		sugar.Fatal(err)
	}

	temp := make([]*PoolLibrary, 0)
	// 加载并解码
	content, err := io.ReadAll(f)
	if err != nil {
		sugar.Fatal(err)
	}
	err = json.Unmarshal(content, &temp)
	if err != nil {
		sugar.Fatal(err)
	}

	// 预处理
	res := make(map[string]*PoolLibrary)
	for _, barcode := range temp {
		res[barcode.Key] = barcode
	}
	return res
}

// DesignSize代表设计的质粒各元件的大小，及特定元件之间的距离
type DesignSize struct {
	TargetLen      int // gDNA target的长度
	PrimerLen      int // Reverse Primer的长度
	BehindLen      int // behind target length
	BeforeLen      int // before target length
	PAMLen         int // PAM的长度
	SpacerLen      int // spacer的长度
	SpacerDistance int // spacer与before target的间距
	PrimerRLen     int
	UMILen         int
}

// len获取设计元件的最短长度，用于过滤等段的测序片段
// func (designSize *DesignSize) len() int {
// 	return designSize.BeforeLen +
// 		designSize.BehindLen +
// 		designSize.TargetLen +
// 		designSize.PrimerLen +
// 		designSize.PAMLen +
// 		designSize.SpacerLen +
// 		designSize.SpacerDistance +
// 		designSize.PrimerLen
// }
