#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用来记录gene cds片段的数据库
"""

import urllib
from enum import Enum
from typing import List

import peewee as pw
from loguru import logger
from playhouse.postgres_ext import PostgresqlExtDatabase, SqliteDatabase
from tqdm import trange

ext_db = pw.Proxy()


def init_db(name: str):
    """初始化数据库"""
    if name.startswith("postg"):
        logger.info("init postgres")

        # 解析 PostgreSQL URL
        parsed = urllib.parse.urlparse(name)
        database = parsed.path[1:]  # 去掉开头的 '/'
        user = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port or 5432

        db = PostgresqlExtDatabase(
            database,
            user=user,
            password=password,
            host=host,
            port=port,
            # 可选：添加其他参数如 sslmode, timeout 等
        )

    else:
        logger.info("init sqlite")
        db = SqliteDatabase(name)
    ext_db.initialize(db)


class Model(pw.Model):
    """基础模型"""

    class Meta:
        database = ext_db


class Genome(Model):
    """记录基因组的文件位置，相对位置"""

    genome = pw.CharField(primary_key=True, index=True, unique=True)
    gtf = pw.CharField(index=True)
    fasta = pw.CharField(index=True)
    scientific_name = pw.CharField(index=True)
    sci_name = pw.CharField(index=True)

    class Meta:
        table_name = "genome"


class Reference(Model):
    """记录注释文件的信息"""

    genome = pw.ForeignKeyField(Genome)
    gene_id = pw.CharField(index=True, null=False)
    chromosome = pw.CharField(index=True, null=False)
    kind = pw.CharField(index=True, null=False)
    name = pw.CharField(index=True, null=True)
    parent = pw.CharField(index=True, null=True)
    start = pw.IntegerField(index=True, null=False)
    end = pw.IntegerField(index=True, null=False)
    strand = pw.CharField(index=False)

    class Meta:
        table_name = "reference"


# 任务状态枚举
class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 已失败


class TaskType(Enum):
    GENE = "gene"
    REGION = "region"
    FASTA = "fasta"


# 任务表 - 核心表
class Task(Model):
    """任务表 - 存储任务实例"""

    id = pw.CharField(primary_key=True)  # 任务ID (UUID)
    description = pw.CharField()  # 任务实例名称

    # 状态相关字段
    status = pw.CharField(default=TaskStatus.PENDING.value)  # 当前状态

    # 执行相关字段
    parameters = pw.TextField(null=True)  # 任务参数(JSON)

    # 进度相关字段
    progress = pw.TextField(null=True)  # 进度消息

    # 结果相关字段
    error = pw.TextField(null=True)  # 错误信息

    class Meta:
        table_name = "tasks"


class Results(Model):
    task = pw.ForeignKeyField(Task)
    sgrna_position = pw.CharField()
    before = pw.CharField()
    pam = pw.CharField(index=True)
    sgrna = pw.CharField(index=True)
    after = pw.CharField()
    target = pw.CharField(index=True)
    gc_content = pw.FloatField()
    gene_id = pw.CharField(null=True)
    gene_name = pw.CharField(null=True)
    range = pw.CharField(null=True)
    exon_id = pw.CharField(null=True)
    exon_range = pw.CharField(null=True)
    name = pw.CharField(null=True)
    indel_freq = pw.FloatField(index=True)
    m0 = pw.IntegerField(null=True)
    m1 = pw.IntegerField(null=True)
    m2 = pw.IntegerField(null=True)
    m3 = pw.IntegerField(null=True)
    m4 = pw.IntegerField(null=True)
    m5 = pw.IntegerField(null=True)
    total = pw.IntegerField(null=True)

    class Meta:
        table_name = "results"
        indexes = [("target", "pam"), ("spacer", "pam")]


class OffTarget(Model):
    """
    First column - given query sequence
    Second column - FASTA sequence title (if you downloaded it from UCSC or Ensembl, it is usually a chromosome name)
    Third column - position of the potential off-target site (same convention with Bowtie)
    Forth column - actual sequence located at the position (mismatched bases noted in lowercase letters)
    Fifth column - indicates forward strand(+) or reverse strand(-) of the found sequence
    Last column - the number of the mismatched bases ('N' in PAM sequence are not counted as mismatched bases)
    """

    task = pw.ForeignKeyField(Task)

    sgrna = pw.CharField(index=True)
    pam = pw.CharField(index=True)
    chromosome = pw.CharField(null=True)
    position = pw.IntegerField(null=True)
    strand = pw.CharField()
    number = pw.IntegerField()

    class Meta:
        table_name = "off_target"
        indexes = [("sgrna", "pam")]


class UserData(Model):
    email = pw.CharField(null=True)
    data = pw.CharField()
    description = pw.CharField(null=True)

    class Meta:
        table_name = "user_data"


def check_tables():
    """check the database is ready?"""
    for table in [Genome, Reference]:
        if not table.table_exists():
            raise ValueError("please run setup before start the web interface")


def check_table(table: Model):
    """检查表格是否存在"""
    if not table.table_exists():
        table.create_table()


def bulk_insert(table: Model, data: List[dict]):
    """向表格插入数据"""
    check_table(table)

    with ext_db.atomic():
        if len(data) <= 100:
            table.insert_many(data).execute()
        else:
            for i in trange(0, len(data), 100):
                table.insert_many(data[i : (i + 100)]).execute()


if __name__ == "__main__":
    pass
