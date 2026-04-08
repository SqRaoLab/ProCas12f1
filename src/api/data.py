#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基因相关的通路
"""

import hashlib
import json
import os

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from src.db import UserData

api_data = Blueprint("data", __name__)


@api_data.route("/", methods=["POST"])
def submit():
    try:
        file = request.files.get("file")
        email = request.form.get("email")
        description = request.form.get("description")

        if file.content_length > 500 * 1024 * 1024:
            return "file too large", 500

        md5_hash = hashlib.md5()
        chunk_size = 8192  # 8KB chunks

        # 先读取所有块，计算 MD5，并保存到临时路径（用原名）
        temp_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], secure_filename(file.filename)
        )

        with open(temp_path, "wb") as f:
            while True:
                chunk = file.stream.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                md5_hash.update(chunk)

        md5_hex = md5_hash.hexdigest()
        final_path = os.path.join(current_app.config["UPLOAD_FOLDER"], md5_hex)

        # 如果已存在同名文件，可跳过保存（去重）
        if os.path.exists(final_path):
            os.remove(temp_path)  # 删除临时文件
        else:
            # 重命名：temp_path → md5_hex
            os.rename(temp_path, final_path)

        UserData.create(
            **{"email": email, "description": description, "data": final_path}
        ).execute()

    except Exception as e:
        return f"error: {e}", 500

    return "success"


if __name__ == "__main__":
    pass
