package main

import "github.com/voxelbrain/goptions"

type params struct {
	Input         string        `goptions:"-i, --input, obligatory, description='the output file of decodeFq'"`
	Background    string        `goptions:"-b, --background, obligatory, description='the background file, output file of decodeFq'"`
	Output        string        `goptions:"-o, --output, obligatory, description='the output file path'"`
	BgFreq        float32       `goptions:"-f, --bg-freq, description='exclude the records with background indel freq > this value（%）'"`
	BgCountThres  int           `goptions:"-c, --bg-count, description='include the background reads with count > this value'"`
	ReadCountTres int           `goptions:"-r, --read-count, description='include the editted reads with count > this value'"`
	MatchKey      string        `goptions:"-m, --match, description='the perfect match cigar'"`
	Debug         bool          `goptions:"--debug, description='enable debug log'"`
	Version       bool          `goptions:"-v, --version, description='print version'"`
	Help          goptions.Help `goptions:"-h, --help, description='Show this help'"`
}

func defaultParams() *params {
	return &params{
		Output:        "output.txt",
		BgFreq:        8,
		BgCountThres:  0,
		ReadCountTres: 10,
		MatchKey:      "20M",
	}
}
