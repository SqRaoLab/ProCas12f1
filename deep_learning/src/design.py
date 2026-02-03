#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于输入的fasta序列或基因名，根据具体蛋白矩阵名进行预处理获取target_seq

Author: 杜静怡
Modified By: 张一鸣
Date: 20250723
"""

import json
import os
import tempfile
from subprocess import check_call
from typing import Dict, List, Optional

import click
import pandas as pd
import regex as re
from Bio.Seq import Seq
from loguru import logger

from src.config import Config
from src.db import Results, Task, TaskStatus, ext_db, init_db
from src.model.features import prepare_training_data
from src.model.params import JobParam, SequenceExtractor
from src.train import predict_value

IUPAC_DICT = {
    "A": "A",
    "T": "T",
    "C": "C",
    "G": "G",
    "R": "[AG]",
    "Y": "[CT]",
    "M": "[AC]",
    "W": "[AT]",
    "S": "[GC]",
    "K": "[GT]",
    "B": "[CGT]",
    "D": "[AGT]",
    "H": "[ACT]",
    "V": "[ACG]",
    "N": "[ATCG]",
}

PAM_MAP = {
    "OsCas12f1": "NTTM",
    "CasMINI": "TTTR",
    "AsCas12f-HKRA": "NTTR",
    "SpaCas12f1": "NTTY",
    "enRhCas12f1": "CCCW",
}


def convert_iupac_to_regex(pam):
    return "".join([IUPAC_DICT.get(base.upper(), base) for base in pam])


def calculate_gc(seq):
    gc = seq.count("G") + seq.count("C")
    return round(gc / len(seq) * 100, 2)


def find_sgrna_sites_cas12(seq: str, pam: str):
    """
    created by Du Jingyi
    :param seq: genome sequence
    :param pam: pam sequence or pam code
    :param pam_len: pam length
    """
    results = []
    seq = Seq(seq)

    pam_regex = convert_iupac_to_regex(pam)
    pam_len = len(pam)

    for seq_upper in [seq.upper(), str(Seq(seq.upper()).reverse_complement())]:
        for match in re.finditer(f"(?={pam_regex})", str(seq_upper), overlapped=True):
            pam_start = match.start()
            sgrna_start = pam_start + pam_len
            sgrna_end = sgrna_start + 20
            if sgrna_end + 6 > len(seq_upper):
                continue
            six_bp_before = seq_upper[max(pam_start - 6, 0) : pam_start]
            pam_seq = seq_upper[pam_start : pam_start + pam_len]
            sgrna_seq = seq_upper[sgrna_start:sgrna_end]
            six_bp_after = seq_upper[sgrna_end : sgrna_end + 6]
            target_seq = six_bp_before + pam_seq + sgrna_seq + six_bp_after
            results.append(
                {
                    "sgrna_position": f"{sgrna_start + 1}:{sgrna_end}",
                    "before": str(six_bp_before),
                    "pam": str(pam_seq),
                    "sgRNA": str(sgrna_seq),
                    "after": str(six_bp_after),
                    "target": str(target_seq),
                    "GC_content": calculate_gc(sgrna_seq),
                }
            )

    return results


def design_sgrna(
    sequence_extractor: SequenceExtractor,
    pam_regex: str = "NTTM",
):
    """design by gene, through gene id or gene name"""

    res = []

    for sequence, exon in sequence_extractor.sequence():
        # w.write(f"{exon[-1]}\t{exon[0]}\t{exon[1]}\t{exon[2]}\n")
        # w.write(f">{exon[-1]}\n{sequence}\n")
        results = find_sgrna_sites_cas12(sequence, pam_regex)

        temp = []
        for row in results:
            if sequence_extractor.gene_id is not None:
                row["gene_id"] = sequence_extractor.gene_id

            if sequence_extractor.gene is not None:
                row["gene_name"] = sequence_extractor.gene

            if sequence_extractor.chromosome and sequence_extractor.start > 0:
                row["range"] = (
                    f"{sequence_extractor.chromosome}:{sequence_extractor.start}-{sequence_extractor.end}"
                )

            if exon is not None and not isinstance(exon, str):
                row["exon_id"] = exon[-1]
                row["exon_range"] = f"{exon[0]}:{exon[1]}-{exon[2]}"
            elif exon is not None and isinstance(exon, str):
                row["name"] = exon

            temp.append(row)

        res += temp

    return pd.DataFrame(res)


def detect_opencl_gpus() -> List[Dict]:
    """check is opencl GPU exists for cas-offinder"""
    gpus = []
    try:
        import pyopencl as cl

        for platform in cl.get_platforms():
            for device in platform.get_devices():
                if device.type == cl.device_type.GPU:
                    gpus.append(
                        {
                            "platform": platform.name,
                            "device": device.name,
                            "compute_units": device.max_compute_units,
                            "global_mem": device.global_mem_size // (1024**2),  # MB
                        }
                    )
    except Exception:
        pass
    return gpus


def create_counts_table(df, seq_col=0, quality_col=5):
    """
    创建计数透视表

    Args:
        df: DataFrame
        seq_col: 序列列的索引或名称
        quality_col: quality列的索引或名称

    Returns:
        透视表DataFrame
    """
    # 确保列名正确
    if isinstance(seq_col, int):
        seq_col = df.columns[seq_col]
    if isinstance(quality_col, int):
        quality_col = df.columns[quality_col]

    # 创建透视表
    pivot_df = pd.crosstab(index=df[seq_col], columns=df[quality_col], dropna=False)

    # 确保所有quality值0-5都存在
    for q in range(6):
        if q not in pivot_df.columns:
            pivot_df[q] = 0

    # 按quality排序
    pivot_df = pivot_df.reindex(sorted(pivot_df.columns), axis=1)

    # 重命名列
    pivot_df.columns = [f"M{col}" for col in pivot_df.columns]

    # 添加总计
    pivot_df["Total"] = pivot_df.sum(axis=1)

    # 按总计降序排序
    pivot_df.sort_values("Total", ascending=False, inplace=True)

    return pivot_df


def run_off_target(
    fasta: str,
    df: pd.DataFrame,
    editing_pattern: str,
    pam_pattern: str,
    max_mismatch: int = 5,
) -> pd.DataFrame:
    """
    apt install ocl-icd-libopencl1 opencl-headers clinfo pocl-opencl-icd
    """
    temp_file_path = None
    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".txt", delete=False
    ) as temp_file:
        temp_file.write(f"{os.path.dirname(fasta)}\n")
        temp_file.write(f"{editing_pattern}{pam_pattern}\n")
        temp_file_path = temp_file.name

        # write lines
        seqs = []
        seq_records = {}
        for _, row in df.iterrows():
            seq = f"{row['sgRNA']}{row['pam']}"
            seqs.append(seq)
            seq_records[seq] = [row["sgRNA"], row["pam"]]
            temp_file.write(f"{seq}\t{max_mismatch}\n")

    try:
        df["id"] = [x for x in seqs]

        gpu_code = "G" if detect_opencl_gpus() else "C"

        check_call(
            f"cas-offinder {temp_file_path} {gpu_code} {temp_file_path}.off", shell=True
        )

        logger.info(f"cas-offinder is finished")

        res = pd.read_csv(temp_file_path + ".off", sep="\t", header=None)
        temp = create_counts_table(res)

        # if online is not None:
        #     logger.info(f"insert cas-offinder results of task: {online}")
        #     # 如果是在线任务，则将对应的结果塞进数据库中
        #     res.columns = ["id", "chromosome", "position", "strand", "number"]
        #
        #     spacer, pam = [], []
        #     for x in tqdm(res["id"], total=res.shape[0]):
        #         temp = seq_records[x]
        #         spacer.append(temp[0])
        #         pam.append(temp[-1])
        #
        #     res["spacer"] = spacer
        #     res["pam"] = pam
        #
        #     logger.info(f"formatting data: {res.shape}")
        #     data = []
        #     for row in tqdm(res.to_dict("records")):
        #         row.pop("id")
        #         row["task"] = online
        #         data.append(row)
        #
        #     with ext_db.atomic():
        #         for i in tqdm(range(0, len(data), 100)):
        #             OffTarget.insert_many(data[i : (i + 100)]).execute()

        logger.info("merging results")
        temp = temp.reset_index().rename(columns={0: "id"})
        df = pd.merge(df, temp, on="id", how="outer")
    except Exception as e:
        pass

    # clear temp file
    for f in [temp_file_path, temp_file_path + ".off"]:
        if os.path.exists(f):
            os.remove(f)

    return df.drop(columns=["id"]) if "id" in df.columns else df


def __set_running_log__(id_: str, message: str, is_error: bool = False):
    """update job status"""
    status = Task.get(Task.id == id_)
    data = []
    if not is_error and status.progress is not None:
        data = json.loads(status.progress)
    elif is_error and status.error is not None:
        data = json.loads(status.error)

    data.append(message)

    key = "error" if is_error else "progress"

    Task.update(
        **{
            key: json.dumps(data),
            "status": TaskStatus.RUNNING.value
            if key != "error"
            else TaskStatus.FAILED.value,
        }
    ).where(Task.id == id_).execute()


def run_design(
    param: JobParam, model_path: str, online: bool = False, off_target: bool = False
) -> Optional[pd.DataFrame]:
    """decode input params generate jobs and run design job"""

    jobs = param.jobs
    pam = param.pam

    editing_pattern = param.editing_pattern
    model = param.model
    max_mismatch = param.max_mismatch

    if online:
        # if online mode and results already exists, just return
        if Results.select().where(Results.task == param.id).count() > 0:
            return None

        __set_running_log__(param.id, "start design sgRNA")

    df = design_sgrna(jobs, pam_regex=pam)
    fasta = jobs.reference

    if online:
        __set_running_log__(
            param.id, "formatting designed sgRNA for indel frequency prediction"
        )
    inputs, df = prepare_training_data(df, cas=model, n_jobs=1)

    if df.shape[0] > 0:
        logger.info("predict editing frequency")

        if not os.path.exists(param.model) and model_path:
            model = os.path.join(model_path, f"{model}.onnx")
        else:
            model = param.model

        if not os.path.exists(model):
            if online:
                __set_running_log__(param.id, f"{model} is not exists", is_error=True)
            else:
                raise ValueError(f"{model} is not exists")

        # predict editing freq
        if online:
            __set_running_log__(param.id, "predicting indel frequency")
        df["indel_freq"] = predict_value(model, inputs)

    if editing_pattern is None:
        editing_pattern = "N" * len(df["sgRNA"][0])

    try:
        if off_target:
            # find off target
            logger.info(f"start to predict off target")
            if online:
                __set_running_log__(param.id, "predicting off targets")
            df = run_off_target(
                fasta=fasta,
                df=df,
                editing_pattern=editing_pattern,
                pam_pattern=pam,
                max_mismatch=max_mismatch,
            )
    except Exception as e:
        logger.error(f"failed to predict off target: {e}")
        if online:
            __set_running_log__(
                param.id, f"failed to predict off target: {e}", is_error=True
            )

    df = df.dropna(subset=["GC_content"])
    if online:
        # 在线任务则将结果塞入数据库
        data = []
        for row in df.to_dict("records"):
            row = {x.lower(): y for x, y in row.items()}
            row["task"] = param.id
            data.append(row)

        with ext_db.atomic():
            for i in range(0, len(data), 100):
                Results.insert_many(data[i : (i + 100)]).execute()
    return df


@click.command()
@click.option("-g", "--gene", type=str, help="the gene name or gene id")
@click.option(
    "-v", "--genome", type=str, help="the genome version, required if gene is provided"
)
@click.option(
    "-r", "--genome-range", type=str, help="the genomic range, eg: chr1:100-200"
)
@click.option("-f", "--fasta", type=click.Path(exists=True), help="path to fasta file")
@click.option("-o", "--output", type=click.Path(), help="path to output file")
@click.option(
    "-m",
    "--model",
    type=click.Choice(PAM_MAP.keys()),
    default="OsCas12f1",
    help="the cas protein",
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True),
    default="./config.ini",
    help="path to config file",
)
@click.option("-p", "--pam", type=str, default="NTTM", help="the pam pattern")
@click.option("--off-target", is_flag=True, help="run the off-target prediction")
@click.option(
    "-e",
    "--editing-pattern",
    type=str,
    help="the editing pattern, default is N * target length",
)
@click.option(
    "--max-mismatch",
    type=click.IntRange(min=1, max=5),
    default=5,
    help="the max mismatch number",
)
def design(
    gene: str,
    genome: str,
    genome_range: str,
    fasta: str,
    max_mismatch: int,
    config: str,
    model: str,
    output: str,
    pam: str,
    off_target: bool,
    editing_pattern: str,
):
    """design sgRNA by gene or fasta file"""

    config = Config(config)

    init_db(config["database"]["uri"])
    assert genome is not None, "genome required if gene is provided"

    if pam is None:
        pam = PAM_MAP.get(model, "NTTM")

    param = JobParam(
        genome=genome,
        genome_range=genome_range,
        fasta=fasta,
        gene=gene,
        pam=pam,
        editing_pattern=editing_pattern,
        max_mismatch=max_mismatch,
        model=model,
        data_path=config["data"]["reference"],
    )

    df = run_design(
        param=param,
        model_path=config["data"]["models"],
        off_target=off_target,
        online=False,
    )

    if output is not None:
        os.makedirs(os.path.abspath(os.path.dirname(output)), exist_ok=True)
        df.to_csv(output, index=False)
        return None
    else:
        return df


if __name__ == "__main__":
    pass
