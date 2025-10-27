# splitFq

根据已有的序列barcode信息，将原始数据拆分成不同的`fastq.gz`文件

## Run

```bash
Usage: splitFq [global options] 

Global options:
        -b, --barcode the path to json file with barcodes
        -i, --input   the path to json with file path
        -o, --output  the output directory (default: output.txt)
            --or      using or instead of and
            --debug   enable debug log
        -v, --version print version
        -h, --help    Show this help
```
