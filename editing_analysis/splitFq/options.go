package main

import "github.com/voxelbrain/goptions"

type params struct {
	Barcode  string        `goptions:"-b, --barcode, obligatory,  description='Path to json file records barcode information'"`
	Pool     string        `goptions:"-i, --input, obligatory, description='Path to json file records fastq file paths'"`
	Scaffold string        `goptions:"-s, --scaffold, description='Path to json file records scaffold, (for more checks, not necessary)'"`
	Output   string        `goptions:"-o, --output, description='Path to output directory'"`
	Merge    bool          `goptions:"-m, --merge, description='Merge records into single fq file'"`
	Debug    bool          `goptions:"--debug, description='Enable debug mode'"`
	Version  bool          `goptions:"-v, --version, description='Print version'"`
	Help     goptions.Help `goptions:"-h, --help, description='Show this help'"`
}

func defaultParams() *params {
	return &params{
		Output: "output",
	}
}
