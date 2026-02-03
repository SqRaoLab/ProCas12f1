package main

import "github.com/voxelbrain/goptions"

type params struct {
	Input      string        `goptions:"-i, --input, obligatory, description='The path to output file of decodeFq'"`
	Background string        `goptions:"-b, --background, obligatory, description='The path to background file, output by decodeFq'"`
	Output     string        `goptions:"-o, --output, obligatory, description='The path to output file'"`
	Cas        string        `goptions:"-c, --cas, obligatory, description='The path to cas'"`
	Debug      bool          `goptions:"--debug, description='Enable debug mode'"`
	Version    bool          `goptions:"-v, --version, description='Print version'"`
	Help       goptions.Help `goptions:"-h, --help, description='Show this help'"`
}

func defaultParams() *params {
	return &params{
		Output: "output.txt",
	}
}
