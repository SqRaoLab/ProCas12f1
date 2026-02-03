#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download reference file
"""

import gzip
import json
import os
from multiprocessing import Pool
from subprocess import check_call
from typing import Dict, List, Tuple

import click
import pysam
from loguru import logger
from tqdm import tqdm

from src.config import Config
from src.db import Genome, Reference, bulk_insert, check_table, init_db


def __prepare_fasta_file__(path: str):
    """解压缩，bgzip压缩并生成index"""
    if os.path.exists(path):
        check_call(f"gunzip {path}", shell=True)
        pass

    if os.path.exists(path.replace(".gz", "")):
        cmd = f"bgzip -@ 10 -c {path.replace('.gz', '')} > {path}"
        check_call(cmd, shell=True)
        pass

    pysam.faidx(path)


def __download_cmd__(url: str, out_path: str) -> Tuple[str, str]:
    """生成aria2c下载链接"""
    out_file = os.path.join(out_path, os.path.basename(url))
    return out_file, f"aria2c -c -s 20 -o {out_file} {url}"


def download_files(path: str, output_dir: str = None):
    """下载基因组文件"""
    os.makedirs(output_dir, exist_ok=True)
    with open(path) as r:
        data = json.load(r)

    logger.info("download files")
    res = []
    for rec in data:
        out_path = os.path.join(output_dir, rec["genome"])
        os.makedirs(out_path, exist_ok=True)

        # prepare the relative path
        out_file, url = __download_cmd__(rec["gtf"], out_path)
        check_call(url, shell=True)
        rec["gtf"] = out_file.replace(output_dir, "").lstrip("/")

        out_file, url = __download_cmd__(rec["fasta"], out_path)
        check_call(url, shell=True)
        rec["fasta"] = out_file.replace(output_dir, "").lstrip("/")
        res.append(rec)

    logger.info("recompress fasta, and generate index")

    with Pool(len(res)) as p:
        list(
            tqdm(
                p.imap(
                    __prepare_fasta_file__,
                    [os.path.join(output_dir, x["fasta"]) for x in res],
                ),
                total=len(res),
            )
        )

    return res


def __decode_atts__(attrs: str) -> Dict[str, str]:
    """解析gtf的特征列"""
    res = {}

    for attr in attrs.split(";"):
        vals = [x.replace('"', "").strip() for x in attr.split()]

        if len(vals) > 1:
            res[vals[0]] = vals[1]
    return res


def decode_gtf(path: str, version: str):
    """用于生成数据库所需数据"""

    # 检查表格是否存在
    check_table(Reference)

    if path.endswith(".gz"):
        r = gzip.open(path, "rt")
    else:
        r = open(path)

    # 遍历读取文件
    data = {}
    for line in r:
        if line.startswith("#"):
            continue

        lines = line.strip().split("\t")
        if len(lines) >= 8:
            attrs = __decode_atts__(lines[8])
            kind = lines[2]

            if kind in ["gene", "transcript", "CDS", "exon"]:
                temp = {
                    "genome": version,
                    "chromosome": lines[0],
                    "start": int(lines[3]),
                    "end": int(lines[4]),
                    "strand": lines[6],
                    "kind": kind,
                }

                if kind != "CDS":
                    temp["name"] = attrs.get(f"{kind.lower()}_name")
                    temp["gene_id"] = attrs.get(f"{kind.lower()}_id")
                else:
                    temp["name"] = attrs.get("exon_name")
                    temp["gene_id"] = attrs.get("exon_id")

                if kind in ["exon", "CDS"]:
                    temp["parent"] = attrs.get("transcript_id")
                if kind == "transcript":
                    temp["parent"] = attrs.get("gene_id")

                if not temp["gene_id"]:
                    continue

                data[temp["gene_id"]] = temp

    r.close()

    bulk_insert(Reference, list(data.values()))


def prepare_reference(data: List[Dict[str, str]], data_path: str):
    """准备数据"""
    check_table(Genome)
    try:
        bulk_insert(Genome, data)
    except Exception:
        pass

    # 批量插入gtf文件
    for rec in Genome.select():
        logger.info(f"insert {rec.gtf}")
        decode_gtf(os.path.join(data_path, rec.gtf), rec.genome)


@click.command(
    context_settings=dict(help_option_names=["-h", "--help"]), no_args_is_help=True
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, dir_okay=True),
    default="./config.ini",
)
@click.option("-i", "--input-json", type=click.Path(exists=True))
def setup(input_json: str, config: str):
    """prepare the database for web interface"""

    config = Config(config)

    logger.info("check whether the download file is ready")
    res = download_files(input_json, config["data"]["reference"])

    logger.info("connect to database")
    init_db(config["database"]["uri"])

    logger.info("insert data")
    prepare_reference(res, config["data"]["reference"])
    pass


if __name__ == "__main__":
    pass
