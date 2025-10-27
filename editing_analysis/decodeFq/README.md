# splitFq

```bash
Usage: decodeFq [global options] 

Global options:
        -1, --r1              R1 FASTQ (gzipped)
        -2, --r2              R2 FASTQ (gzipped)
        -c, --cas             the Cas protein
        -l, --library         the path to json with pool library information
        -o, --output          the output file path (default: output.txt)
        -p, --process         the number of goroutines to use (default: 10)
            --target-length   length of gDNA target (default: 20)
            --primer-length   length of reverse primer (default: 20)
            --pam-length      length of PAM (default: 4)
            --spacer-length   length of spacer (default: 20)
            --spacer-distance length between spacer and before target (default: 6)
            --before-length   length of before target (default: 6)
            --behind-length   length of before target (default: 6)
            --cmd             used to read fastq file from quip format
        -U, --umi-anchor      the designed umi
        -u, --umi             the length of designed umi (default: 28)
        -r, --reverse         complement reverse reads
            --debug           enable debug
        -v, --version         print version
        -h, --help            Show this help
```
