package main

import "github.com/voxelbrain/goptions"

type params struct {
	R1             string        `goptions:"-1, --r1, description='R1 FASTQ (gzipped)'"`
	R2             string        `goptions:"-2, --r2, description='R2 FASTQ (gzipped)'"`
	Cas            string        `goptions:"-c, --cas, description='the Cas protein'"`
	Pool           string        `goptions:"-l, --library, description='the path to json with pool library information'"`
	Output         string        `goptions:"-o, --output, description='the output file path'"`
	Procs          int           `goptions:"-p, --process, description='the number of goroutines to use'"`
	TargetLen      int           `goptions:"--target-length, description='length of gDNA target'"`
	PrimerLen      int           `goptions:"--primer-length, description='length of reverse primer'"`
	PAMLen         int           `goptions:"--pam-length, description='length of PAM'"`
	SpacerLen      int           `goptions:"--spacer-length, description='length of spacer'"`
	SpacerDistance int           `goptions:"--spacer-distance, description='length between spacer and before target'"`
	BeforeLen      int           `goptions:"--before-length, description='length of before target'"`
	BehindLen      int           `goptions:"--behind-length, description='length of before target'"`
	ReadCmd        string        `goptions:"--cmd, description='used to read fastq file from quip format'"`
	UMIAnchor      string        `goptions:"-U, --umi-anchor, description='the designed umi'"`
	UMILen         int           `goptions:"-u, --umi, description='the length of designed umi'"`
	Reverse        bool          `goptions:"-r, --reverse, description='complement reverse reads'"`
	Debug          bool          `goptions:"--debug, description='enable debug'"`
	Version        bool          `goptions:"-v, --version, description='print version'"`
	Help           goptions.Help `goptions:"-h, --help, description='Show this help'"`
}

func defaultParams() *params {
	return &params{
		Output:         "output.txt",
		Procs:          10,
		TargetLen:      20,
		PrimerLen:      20,
		PAMLen:         4,
		SpacerLen:      20,
		SpacerDistance: 6,
		BeforeLen:      6,
		BehindLen:      6,
		UMILen:         28,
	}
}
