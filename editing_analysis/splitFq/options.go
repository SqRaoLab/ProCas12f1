package main

import "github.com/voxelbrain/goptions"

type params struct {
	Barcode string        `goptions:"-b, --barcode, description='the path to json file with barcodes'"`
	Pool    string        `goptions:"-i, --input, description='the path to json with file path'"`
	Output  string        `goptions:"-o, --output, description='the output directory'"`
	Or      bool          `goptions:"--or, description='using or instead of and'"`
	Debug   bool          `goptions:"--debug, description='enable debug log'"`
	Version bool          `goptions:"-v, --version, description='print version'"`
	Help    goptions.Help `goptions:"-h, --help, description='Show this help'"`
}

func defaultParams() *params {
	return &params{
		Output: "output.txt",
	}
}
