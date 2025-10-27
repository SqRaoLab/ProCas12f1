# calFreq

```bash
Usage: calFreq [global options] 

Global options:
        -i, --input      the output file of decodeFq (*)
        -b, --background the background file, output file of decodeFq (*)
        -o, --output     the output file path (default: output.txt) (*)
        -f, --bg-freq    exclude the records with background indel freq > this value（%） (default: 8)
        -c, --bg-count   include the background reads with count > this value
        -r, --read-count include the editted reads with count > this value (default: 10)
        -m, --match      the perfect match cigar (default: 20M)
            --debug      enable debug log
        -v, --version    print version
        -h, --help       Show this help
```
