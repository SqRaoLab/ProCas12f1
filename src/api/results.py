#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API handles the task creation and running related
"""

import io
import json
from typing import Optional

import pandas as pd
from flask import Blueprint, jsonify, make_response, request

from src.db import OffTarget, Results, Task, TaskType

api_result = Blueprint("result", __name__)


def is_task_off_target(task_id: str):
    task = Task.get_or_none(Task.id == task_id)

    if task is None:
        raise ValueError(f"task {task_id} not found")

    params = json.loads(task.parameters)
    off_target = True
    for row in params:
        if row[0] == "off_target":
            off_target = row[-1]
            break
    return off_target, task


def get_results_columns_by_task_type(task_id: str):
    """setup the query columns"""
    off_target, task = is_task_off_target(task_id)
    # get results
    columns = [
        Results.sgrna_position,
        # Results.before,
        Results.pam,
        Results.sgrna,
        # Results.after,
        # Results.target,
        Results.gc_content,
        Results.indel_freq,
    ]

    if off_target:
        columns += [
            Results.m0,
            Results.m1,
            Results.m2,
            Results.m3,
            Results.m4,
            Results.m5,
            Results.total,
        ]

    if task.description == TaskType.GENE.value:
        columns = [
            Results.gene_id,
            Results.gene_name,
            Results.exon_id,
            Results.exon_range,
        ] + columns
    elif task.description == TaskType.REGION.value:
        columns = [Results.range] + columns
    else:
        columns = [Results.name] + columns
    return columns


def select_data_from_db(
    table,
    task_id: str,
    offset: int = 1,
    length: int = 10,
    order=None,
    order_by=None,
    columns=None,
):
    """query logic"""
    if columns is not None:
        query = table.select(*columns)
    else:
        query = table.select()

    query = query.where(table.task == task_id)
    total = query.count()

    if order_by:
        if "asc" in order.lower():
            query = query.order_by(getattr(table, order_by))
        else:
            query = query.order_by(getattr(table, order_by).desc())

    try:
        offset = int(offset)
        length = int(length)
        query = query.offset((offset - 1) * length).limit(length)
    except ValueError as _:
        query = query.limit(10)

    return {
        "total": total,
        "offset": offset,
        "length": length,
        "data": [x for x in query.dicts()],
    }


class Headers(object):
    def __init__(self, title: str, key: str, min_width: Optional[int] = None):
        self.key = key
        self.title = title
        self.min_width = min_width

    def __dict__(self):
        return self.dict

    @property
    def dict(self):
        return {
            "key": self.key,
            "title": self.title,
            "minWidth": self.min_width,
            "sorter": True,
        }


@api_result.route("/headers/<task_id>", methods=["GET"])
def list_headers(task_id: str):
    headers = [
        Headers("sgRNA position", "sgrna_position"),
        # Headers("Before", "before"),
        Headers("PAM", "pam"),
        Headers("sgRNA", "sgrna"),
        # Headers("After target", "after"),
        # Headers("Target", "target"),
        Headers("GC content", "gc_content"),
        Headers("Indel freq (%)", "indel_freq"),
    ]

    off_target, _ = is_task_off_target(task_id)
    if off_target:
        headers += [
            Headers("Frequency of on-target", "m0"),
            Headers("Frequency of 1 mismatch", "m1"),
            Headers("Frequency of 2 mismatches", "m2"),
            Headers("Frequency of 3 mismatches", "m3"),
            Headers("Frequency of 4 mismatches", "m4"),
            Headers("Frequency of 5 mismatches", "m5"),
            Headers("Total off targets", "total"),
        ]

    headers = [x.dict for x in headers]

    categories = {
        TaskType.GENE.value: [
            Headers("Gene ID", "gene_id"),
            Headers("Gene ID", "gene_name"),
            Headers("Exon ID", "exon_id"),
            Headers("Exon range", "exon_range"),
        ],
        TaskType.REGION.value: [
            Headers("Genomic region", "range"),
        ],
        TaskType.FASTA.value: [Headers("Sequence name", "name")],
    }

    return jsonify(
        {
            "categories": {x: [z.dict for z in y] for x, y in categories.items()},
            "headers": headers,
        }
    )


@api_result.route("/download/<task_id>", methods=["GET"])
def handle_download(task_id):
    """used to download task results"""
    content_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    try:
        columns = get_results_columns_by_task_type(task_id)
    except ValueError as e:
        return jsonify({"msg": str(e)}), 404

    # select data
    data = [
        x
        for x in Results.select(*columns)
        .where(Results.task == task_id)
        .order(Results.indel_freq.desc())
        .dicts()
    ]
    df = pd.DataFrame(data)

    # make buffer
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    resp = make_response(buffer.getvalue())
    resp.headers["Content-Disposition"] = f"attachment; filename={task_id}.xlsx"
    resp.headers["Content-Type"] = content_types["xlsx"]
    return resp


@api_result.route("/<task_id>", methods=["GET"])
def list_results(task_id):
    """used to list task results"""
    # 获取参数
    offset = request.args.get("offset", 1)
    length = request.args.get("length", 10)
    order_by = request.args.get("order_by", "indel_freq")
    order = request.args.get("order", "desc")

    try:
        columns = get_results_columns_by_task_type(task_id)
    except ValueError as e:
        return jsonify({"msg": str(e)}), 404

    return jsonify(
        select_data_from_db(
            Results,
            task_id=task_id,
            offset=offset,
            length=length,
            order_by=order_by,
            order=order,
            columns=columns,
        )
    )


@api_result.route("/off/<task_id>", methods=["GET"])
def list_off_target(task_id):
    """used to list task off-target"""
    # 获取参数
    offset = request.args.get("offset", 1)
    length = request.args.get("length", 10)
    order_by = request.args.get("order_by", None)
    order = request.args.get("order", "asc")

    return jsonify(
        select_data_from_db(
            OffTarget,
            task_id=task_id,
            offset=offset,
            length=length,
            order_by=order_by,
            order=order,
        )
    )


if __name__ == "__main__":
    pass
