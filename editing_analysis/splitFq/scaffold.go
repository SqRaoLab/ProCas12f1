package main

import (
	"encoding/json"
	"os"
)

func loadScaffold(path string) (map[string]string, error) {
	res := make(map[string]string)

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal(data, &res); err != nil {
		return nil, err
	}
	return res, err
}
