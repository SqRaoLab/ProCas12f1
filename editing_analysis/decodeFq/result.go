package main

import "sync"

// Result 用于存储计数结果，并保证并发安全
type Result struct {
	sync.RWMutex
	Data map[string]map[string]int
}

// NewResult 创建一个新的Result实例
func NewResult() *Result {
	return &Result{
		Data: make(map[string]map[string]int),
	}
}

// Add 增加计数，保证并发安全
func (r *Result) Add(barcodeSet, pam string) {
	r.Lock()
	defer r.Unlock()
	if _, ok := r.Data[barcodeSet]; !ok {
		r.Data[barcodeSet] = make(map[string]int)
	}
	r.Data[barcodeSet][pam]++
}

// GetData 获取结果的副本，避免并发读写问题
func (r *Result) GetData() map[string]map[string]int {
	r.RLock()
	defer r.RUnlock()
	copy := make(map[string]map[string]int)
	for k, v := range r.Data {
		copy[k] = make(map[string]int)
		for kk, vv := range v {
			copy[k][kk] = vv
		}
	}
	return copy
}
