# calFreq

Used to calculate editing frequency by comparing the input file against a background reference file.

---

### Installation

```bash
# Go 1.24+ required
go build .
```

### Run

参数如下：
```bash
calFreq --help

Usage: calFreq [global options] 

Global options:
        -i, --input      The path to output file of decodeFq (*)
        -b, --background The path to background file, output by decodeFq (*)
        -o, --output     The path to output file (default: output.txt) (*)
            --debug      Enable debug mode
        -v, --version    Print version
        -h, --help       Show this help
```

### Output format

```csv
before,pam,spacer,after,target,bgIndel,bgTotal,bgFreq,indel,total,corrected_efficiency
GTCAAG,CCCC,CCTTGTCAAGGCTATTGGTC,AGGCAA,CCTTGTCAAGGCTATTGGTC,0,21,0.000000,3,85,3.529412
GTTCTC,ACCA,TGGCCACATGGAGTGACCTG,GCCTCT,TGGCCACATGGAGTGACCTG,0,31,0.000000,0,49,0.000000
GATTTC,TTTG,CCTGGACACCCCCATCTCCT,TGGATT,CCTGGACACCCCGTTCTCCT,0,5,0.000000,2,14,14.285715
TCTCTC,GCCC,CCAGAACCTCTAAGGTTTGC,TACGAT,CCAGAACCTCTAAGGTTTGC,5,426,1.173709,40,1879,0.966426
```