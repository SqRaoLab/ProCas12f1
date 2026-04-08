
# deepcas12f


```bash

aria2c -c -s 10 --file-allocation=none https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/GRCh38.p14.genome.fa.gz
gunzip GRCh38.p14.genome.fa.gz && bgzip GRCh38.p14.genome.fa && samtools index GRCh38.p14.genome.fa.gz

aria2c -c -s 10 --file-allocation=none https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/gencode.v49.annotation.gtf.gz

apt install ocl-icd-libopencl1 opencl-headers clinfo pocl-opencl-icd
```

## 运行配置

Python >= 3.10


### 运行

```bash
# 如果没有uv，首先安装uv
pip install uv

# 运行
uv run main.py --help
```
