#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基因相关的通路
"""

import base64
import hashlib
import json
import os
import zlib
from glob import glob
from typing import Dict, List, Optional, Union

import pysam
import regex as re
from flask import current_app
from loguru import logger

from src.db import Genome, Reference


def reverse_complement(seq):
    """基本的反向互补函数"""
    comp_dict = {
        'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G',
        'a': 't', 't': 'a', 'g': 'c', 'c': 'g',
        'N': 'N', 'n': 'n',
        'R': 'Y', 'Y': 'R',  # 简并碱基
        'S': 'S', 'W': 'W', 'K': 'M', 'M': 'K',
        'B': 'V', 'D': 'H', 'H': 'D', 'V': 'B',
    }

    # 创建互补序列
    complement = ''.join(comp_dict.get(base, 'N') for base in seq)
    # 反转
    reverse_comp = complement[::-1]

    return reverse_comp


class SequenceExtractor(object):
    def __init__(
        self,
        gene: str,
        genome: str,
        chromosome: str = None,
        start: int = 0,
        end: int = 0,
        strand: str = "+",
        fasta: str = None,
        data_path: str = None,
    ):
        self.gene = gene
        self.gene_id = None
        self.genome = genome
        self.chromosome = chromosome
        self.start = start
        self.end = end
        self.strand = strand

        self.fasta = None
        if fasta is not None and os.path.exists(fasta):
            self.fasta = fasta
        self.reference = self.__find_fasta__(data_path)

        if self.gene:
            self.adjust_gene()

    def __hash__(self):
        return hash((self.gene, self.genome, self.chromosome, self.start, self.end))

    def __find_fasta__(self, data_path: str = None):
        rec = Genome.get_or_none(Genome.genome == self.genome)
        if rec:
            if not data_path:
                path = os.path.join(current_app.config["REF_FOLDER"], rec.fasta)
            else:
                path = os.path.join(data_path, rec.fasta)

            if not os.path.exists(path):
                path = glob(os.path.join(os.path.dirname(path), "*.fa.gz"))
                if len(path) > 0:
                    path = path[0]
        elif os.path.exists(self.genome):
            path = self.genome
        else:
            raise ValueError(f"{self.genome} does not exist")
        return str(path)

    def adjust_gene(self):
        query = Reference.select().where(
            (Reference.genome == self.genome)
            & (Reference.kind == "gene")
            & ((Reference.gene_id == self.gene) | (Reference.name == self.gene))
        )

        def invalid_int(value: Optional[int]):
            if value is None:
                return True
            return value <= 0

        for rec in query:
            self.gene_id = rec.gene_id
            self.gene = rec.name

            if (
                not self.chromosome
                and invalid_int(self.start)
                and invalid_int(self.end)
            ):
                self.chromosome = rec.chromosome
                self.start = rec.start
                self.end = rec.end
                self.strand = rec.strand
            break

    def sequence(self):
        """获取sequence"""

        if self.gene is not None:
            logger.info("Running in gene mode")
            res = []
            # 如果只给了基因的坐标，则查询其名下的所有转录本和外显子
            # 遍历归属于某个基因的所有差异表达分子
            for transcript in (
                Reference.select()
                .join(Genome, on=(Reference.genome == Genome.genome))
                .where(
                    (Genome.genome == self.genome)
                    & (Reference.kind == "transcript")
                    & (Reference.parent == self.gene_id)
                )
            ):
                # 遍历归属于某个转录本的所有外显子
                for exon in (
                    Reference.select()
                    .join(Genome, on=(Reference.genome == Genome.genome))
                    .where(
                        (Genome.genome == self.genome)
                        & (Reference.kind == "exon")
                        & (Reference.parent == transcript.gene_id)
                    )
                ):
                    res.append((exon.chromosome, exon.start, exon.end, exon.gene_id, exon.strand))

            res = sorted(set(res), key=lambda x: [x[0], x[1], x[2]])

            with pysam.FastaFile(self.reference) as fh:
                for exon in res:
                    if exon[4] == "+":
                        yield fh.fetch(*exon[:3]), exon
                    elif exon[4] == "-":
                        yield reverse_complement(fh.fetch(*exon[:3])), exon
                    else:
                        logger.warning(f"invalid strand: {exon[-1]}")
        elif self.chromosome is not None and self.start > 0 and self.end > 0:
            logger.info("Running in genomic region mode")
            with pysam.FastaFile(self.reference) as fh:
                try:
                    yield fh.fetch(self.chromosome, self.start, self.end), None
                except Exception:
                    if self.chromosome.startswith("chr"):
                        chrom = self.chromosome.replace("chr", "")
                    else:
                        chrom = "chr" + self.chromosome
                    if self.strand == "-":
                        yield reverse_complement(fh.fetch(chrom, self.start, self.end)), None
                    else:
                        yield fh.fetch(chrom, self.start, self.end), None

        elif self.fasta is not None:
            logger.info("Running in fasta mode")
            # read sequence from fasta
            with pysam.FastaFile(self.fasta) as fh:
                for name in fh.references:
                    yield fh.fetch(name), name

    @property
    def dicts(self) -> Dict[str, Union[str, int]]:
        return {
            "gene": self.gene,
            "chromosome": self.chromosome,
            "start": self.start,
            "end": self.end,
            "fasta": self.fasta,
            "genome": self.genome,
        }


def dict_to_db_id(dict_str: str, max_length: int = 64, compress: bool = True) -> str:
    """
    生成适合数据库存储的字典ID

    Args:
        dict_str: 字典
        max_length: 最大长度（数据库字段限制）
        compress: 是否压缩

    Returns:
        数据库友好的ID字符串
    """
    # 规范化字典

    # 可选压缩
    if compress:
        dict_bytes = dict_str.encode("utf-8")
        compressed = zlib.compress(dict_bytes, level=9)

        # 使用更高效的哈希（CRC32 + SHA1组合）
        crc32_hash = zlib.crc32(compressed) & 0xFFFFFFFF

        # SHA1哈希
        sha1_hash = hashlib.sha1(compressed).digest()

        # 组合：CRC32(4字节) + SHA1前8字节
        combined = crc32_hash.to_bytes(4, "big") + sha1_hash[:8]

        # Base64编码
        encoded = base64.urlsafe_b64encode(combined).decode("ascii")

        # 移除填充字符
        encoded = encoded.rstrip("=")
    else:
        # 简单哈希
        hash_obj = hashlib.sha256(dict_str.encode())
        encoded = base64.urlsafe_b64encode(hash_obj.digest()).decode("ascii")
        encoded = encoded.rstrip("=")

    # 确保不超过最大长度
    if len(encoded) > max_length:
        # 截断并添加截断标记
        encoded = encoded[: max_length - 1] + "~"

    return encoded


class JobParam(object):
    def __init__(
        self,
        genome: str = "hg38",
        genome_range: str = None,
        fasta: str = None,
        gene: str = None,
        pam: str = None,
        editing_pattern: str = None,
        max_mismatch: int = 5,
        model: str = "OsCas12f1",
        data_path: str = None,
        off_target: bool = False,
    ):
        chromosome, start, end, strand = None, None, None, None
        if genome_range is not None:
            # check the input genomic range
            match = re.match(r"(?P<chrom>\w+):(?P<start>\d+)-(?P<end>\d+):?(?P<strand>[+-])?", genome_range)

            if not match:
                raise ValueError(f"{genome_range} is not a valid genome range")
            params = match.groupdict()
            chromosome, start, end, strand = (
                params["chrom"],
                int(params["start"]),
                int(params["end"]),
                params.get("strand", "+")
            )

        elif fasta is not None:
            assert os.path.exists(fasta), "fasta file does not exist"
        elif gene is None:
            raise ValueError("please provide either gene, genomic range or fasta file")

        self.jobs = SequenceExtractor(
            gene, genome, chromosome, start, end, strand=strand, fasta=fasta, data_path=data_path
        )
        self.pam = pam
        self.editing_pattern = editing_pattern
        self.max_mismatch = max_mismatch
        self.model = model
        self.off_target = off_target

    @property
    def gene(self):
        return self.jobs.gene

    @property
    def genome_range(self):
        if self.jobs.chromosome is not None and self.jobs.start and self.jobs.end:
            return f"{self.jobs.chromosome}:{self.jobs.start}-{self.jobs.end}"
        return None

    @property
    def fasta(self) -> str:
        return self.jobs.fasta

    @property
    def reference(self) -> str:
        return self.jobs.reference

    def __str__(self):
        sorted_items = sorted(self.dicts.items())
        return json.dumps(sorted_items, separators=(",", ":"))

    @property
    def dicts(self) -> Dict[str, Union[str, int]]:
        data = self.jobs.dicts

        data["pam"] = self.pam
        data["editing_pattern"] = self.editing_pattern
        data["max_mismatch"] = self.max_mismatch
        data["model"] = self.model
        data["off_target"] = self.off_target
        return data

    @property
    def id(self) -> str:
        return dict_to_db_id(str(self))

    @classmethod
    def create(cls, data: Union[str, List, Dict]):
        if isinstance(data, str):
            data = json.loads(data)

        if isinstance(data, List):
            res = {}
            for row in data:
                res[row[0]] = row[-1]

            chromosome = res.pop("chromosome") if "chromosome" in res else None
            start = res.pop("start") if "start" in res else None
            end = res.pop("end") if "end" in res else None

            if chromosome and start and end:
                res["genome_range"] = f"{chromosome}:{start}-{end}"
            return cls(**res)
        else:
            return cls(**data)


if __name__ == "__main__":
    pass
