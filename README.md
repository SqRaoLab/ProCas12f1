# ProCas12f

This repo contains the analysis code and prediction model for ProCas12f

## 1. Prediciton code

The prediciton code was kept under `predicition` folder, it's a Python script for predicting ProCas12f. It takes a CSV file containing sequence information as input, performs prediction using a specified Cas12 (options include CasMINI, OsCas12f1, RhCas12f1, enAsCas12f1, SpaCas12f1), and outputs the prediction results to a CSV file.

### 1.1 Installation

```shell
# Python 3.10-3.12
pip install pandas numpy viennarna biopython onnxruntime
git clone git@github.com:ShuquanRaolab/ProCas12f.git
cd ProCas12f/prediction
wget https://github.com/ShuquanRaolab/ProCas12f/releases/download/models_v1/models.tar.gz
tar -xvf models.tar.gz
```

### 1.1 Argument Details

`-i` or `--input_filename`: The name of the input file. It MUST be a two-column CSV file. This is a required argument.

`-n` or `--Cas12f_name`: The name of the Cas12 to use for prediction. It must be one of 'CasMINI', 'OsCas12f1', 'RhCas12f1', 'enAsCas12f1', 'SpaCas12f1'. This is a required argument.

`-o` or `--output_filename`: The name of the output file. The default is './output.csv'.

### 1.2 Usage Example

The input file should be a CSV file with two columns: ID and SEQ. SEQ should be a 24bp sequence, including a 4bp pam and a 20bp target. For example:

```csv
ID,SEQ(6bp before + 4bp pam + 20bp target + 6bp after)
seq1,AGCGCTATTACAGCTCGCAGATCTGCACCCGGGAAA
seq2,GCTGATTTTATCTCCACGTGCCCTGAAGGTTAACCT
```

The command to run the script is as follows:

```python
python prediction.py -i example_input.csv -n OsCas12f1 -o example_output.csv
```

---

## 2. Editing analysis

A comprehensive pipeline for analyzing CRISPR-Cas gene editing experiments from high-throughput sequencing data. This toolkit processes raw sequencing reads, identifies editing events, quantifies editing efficiencies.

### 2.1 Installation

[Go version>=1.20](https://go.dev/) was required to compile these tools, please install golang by official instruction.

### 2.2 Argument Details

#### (1) splitFq

The `editing_analysis/splitFq` contains the tool used to split raw sequencing data by barcodes.

```bash
cd editing_analysis/splitFq

# install requirements
go mod tidy

# compile this tool
go build .

# print help info
./splitFq --help
```

The parameters required

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

#### (2) decodeFq

The `editing_analysis/decodeFq` contains the tool used to decode the PAM, spacer, target and editting evens from fastq files.

```bash
cd editing_analysis/decodeFq

# install requirements
go mod tidy

# compile this tool
go build .

# print help info
./decodeFq --help
```

The parameters required

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

#### (3) calFreq

The `editing_analysis/calFreq` contains the tool used to calculate the indel frequency.

```bash
cd editing_analysis/calFreq

# install requirements
go mod tidy

# compile this tool
go build .

# print help info
./calFreq --help
```

The parameters required

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


## Example pipeline

```bash
./editing_analysis/splitFq/splitFq -b example/barcodes.json -i example/files.json -o example

./editing_analysis/decodeFq/decodeFq -1 example/OsCas12f1-genome_R1.fq.gz -2 example/OsCas12f1-genome_R2.fq.gz -c OsCas12f1 -l example/library.json -o example/genome.tsv.gz
./editing_analysis/decodeFq/decodeFq -1 example/OsCas12f1-plasmid_R1.fq.gz -2 example/OsCas12f1-plasmid_R2.fq.gz -c OsCas12f1 -l example/library.json -o example/plasmid.tsv.gz

./editing_analysis/calFreq/calFreq -i example/genome.tsv.gz -b example/plasmid.tsv.gz -o example/indel_freq.tsv.gz
```

---

## 3. eCROP

The `eCROP` folder contains the contains the code to analyze the eCROP-seq data from the manuscript

### 3.1 Installation

Exept the pyhton environment, the `R 4.3+` and several libraries were also required.

- corrplot
- data.table
- dplyr
- forcasts
- ggplto2
- ggsci
- GGally
- gridExtra
- Matrix
- pheatmap
- purrr
- qs
- readr
- scales
- Seurat
- SingleR
- tibble
- tidyr
- tidyverse

### 3.2. Usage Example

- `crop_count.py`: Code for counting sgRNAs from eCROP-seq experiments. Use `python crop_count.py -h` to view help.

- `sgrna_assign.R`: Integrates gRNA assignments from read and transcriptome data, filters low-quality cells based on QC, and appends final assignments to the gene-count matrix.

- `eCROP_UMAPs.R`, `eCROP_Seurat.R`, `eCROP_ClusterEnrichments.R`: Loaded the aggregated scRNA-seq data into R with Seurat, integrated the final sgRNA assignments into the object metadata, and performed data processing to generate manuscript **Figure 6**.
