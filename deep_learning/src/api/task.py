#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API handles the task creation and running related
"""

import hashlib
import json
import os

from flask import Blueprint, current_app, jsonify, request

from src.db import Task
from src.design import PAM_MAP
from src.model.params import JobParam

__dir__ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

api_task = Blueprint("task", __name__)


def allowed_file(filename):
    """just check the file type by subfix"""
    for i in [".fasta", ".fa", ".fasta.gz", ".fa.gz"]:
        if filename.endswith(i):
            return True
    return False


def compute_md5(data: str) -> str:
    """计算字符串的 MD5 哈希值"""
    return hashlib.md5(data.encode("utf-8")).hexdigest()


@api_task.route("/submit", methods=["POST", "GET"])
def handle_post():
    """处理 POST 请求（接收 JSON 元数据和 fasta 文件）"""
    # 1. 检查是否为 multipart 表单

    data = request.get_json()
    data["model"] = "OsCas12f1"
    for key, value in PAM_MAP.items():
        if value == data.get("pam"):
            data["model"] = key
            break

    if data["fasta"]:
        # save fasta to file
        md5_hex = hashlib.md5(data["fasta"].encode("utf-8")).hexdigest()
        file_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], md5_hex + ".fasta"
        )
        if not os.path.exists(file_path):
            with open(file_path, "w+") as w:
                w.write(data["fasta"])
        data["fasta"] = file_path

    off_target = data.pop("off_target")
    job = JobParam.create(data)

    if isinstance(off_target, bool):
        job.off_target = off_target
    else:
        job.off_target = "true" in str(off_target).lower()
    current_app.config["JOB"].put(job)
    return job.id


@api_task.route("/status/<task_id>", methods=["GET"])
def get_job_status(task_id):
    job = Task.get_or_none(Task.id == task_id)

    if job is None:
        return jsonify(f"Task {task_id} not found"), 404

    def to_dict(self):
        res = {
            "id": self.id,
            "description": self.description.split(".")[-1],
            "status": self.status.split(".")[-1],
        }

        if self.progress:
            res["progress"] = json.loads(str(self.progress))
        if self.error:
            res["error"] = json.loads(str(self.error))

        if self.parameters:
            # 重新将fasta的路径补全
            data = json.loads(self.parameters)
            params = []
            for row in data:
                if row[0] == "fasta" and row[-1]:
                    row[-1] = os.path.join(__dir__, row[-1])
                params.append(row)
            res["parameters"] = JobParam.create(params).dicts

        fasta_path = res.get("parameters", {}).get("fasta")
        if fasta_path is not None and current_app.config["REF_FOLDER"] in fasta_path:
            res["parameters"]["fasta"] = None

        return res

    return jsonify(to_dict(job))


if __name__ == "__main__":
    pass
