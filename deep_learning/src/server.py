#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os
import threading
from multiprocessing import Queue

import click
from flask import Blueprint, Flask, send_from_directory
from loguru import logger

from src.config import Config
from src.db import (
    OffTarget,
    Results,
    Task,
    TaskStatus,
    TaskType,
    UserData,
    check_tables,
    init_db,
)
from src.design import run_design

try:
    from flask_cors import CORS
except ImportError:
    pass

from src.api.const import api_const
from src.api.data import api_data
from src.api.gene import api_gene
from src.api.results import api_result
from src.api.task import api_task


class InterceptHandler(logging.Handler):
    def emit(self, record):
        logger_opt = logger.opt(depth=6, exception=record.exc_info)
        logger_opt.log(record.levelno, record.getMessage())


__dir__ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not __dir__.endswith("/"):
    __dir__ = __dir__ + "/"

app = Flask(__name__)
app.logger.addHandler(InterceptHandler())
stop_event = threading.Event()

procas12f = Blueprint(
    "procas12f",
    __name__,
    static_folder=os.path.join(__dir__, "./frontend/dist"),
    static_url_path="/",
)
api = Blueprint("api", __name__)


def init_server(
    data: str, model: str, reference: str, static: str, debug: bool = False
):
    """启动服务器"""
    # 确保目录存在

    if debug:
        CORS(app)

    args = [data, model, reference, static]

    abs_path = []

    for arg in args:
        if not os.path.isabs(arg):
            abs_path.append(os.path.join(__dir__, arg))

    data, model, reference, static = abs_path

    app.config.update(
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 最大请求体 100MB
        DATA_FOLDER=os.path.dirname(data),
        UPLOAD_FOLDER=data,  # 文件存储目录
        MODEL_FOLDER=model,
        REF_FOLDER=reference,
        STATIC=static,
        JOB=Queue(),
        ALLOWED_EXTENSIONS={"fasta", "fa"},  # 允许的文件扩展名
    )


def background_task():
    while not stop_event.is_set():
        job = app.config["JOB"].get()

        task = Task.get_or_none(Task.id == job.id)
        if task is None:
            if job.gene:
                description = TaskType.GENE.value
            elif job.genome_range:
                description = TaskType.REGION.value
            else:
                description = TaskType.FASTA.value

            Task.create(
                **{
                    "id": job.id,
                    "description": description,
                    "parameters": str(job).replace(__dir__, "").strip("/"),
                }
            )

        task = Task.get_or_none(Task.id == job.id)
        if task.status not in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
            Task.update(**{"status": TaskStatus.RUNNING.value}).where(
                Task.id == task.id
            ).execute()

            run_design(
                job,
                model_path=app.config["MODEL_FOLDER"],
                online=True,
                off_target=job.off_target,
            )
            Task.update(**{"status": TaskStatus.COMPLETED.value}).where(
                Task.id == task.id
            ).execute()


@app.errorhandler(404)
def handle404(e):
    return send_from_directory(procas12f.static_folder, "index.html")


@procas12f.route("/", defaults={"path": "index.html"})
@procas12f.route("/<path>")
def get_main(path):
    """处理静态文件请求"""
    # 安全校验：防止目录遍历
    # 如果路径包含 "."，很可能是静态文件（如 app.js, style.css, favicon.ico）
    path = os.path.join(procas12f.static_folder, path)

    if os.path.exists(path):
        return send_from_directory(os.path.dirname(path), os.path.basename(path))
    else:
        # 无扩展名 → 前端路由，返回 index.html
        return send_from_directory(procas12f.static_folder, "index.html")


api.register_blueprint(api_gene, url_prefix="/gene")
api.register_blueprint(api_task, url_prefix="/task")
api.register_blueprint(api_result, url_prefix="/result")
api.register_blueprint(api_const, url_prefix="/const")
api.register_blueprint(api_data, url_prefix="/upload")
procas12f.register_blueprint(api, url_prefix="/api")
app.register_blueprint(procas12f, url_prefix="/procas12f")


def run_app(args):
    config, debug = args
    app.run(
        host=config["web"].get("host", "0.0.0.0"),
        port=int(config["web"].get("port", 5000)),
        debug=debug,
        threaded=True,
        use_reloader=False,  # 👈 关键：禁用 reloader
    )


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, dir_okay=True),
    default="./config.ini",
)
@click.option("--debug", is_flag=True)
def start(config: str, debug):
    """start web interface"""

    config = Config(config)

    init_db(config["database"]["uri"])

    logger.info("check whether database is ready")
    check_tables()

    for table in [Task, Results, OffTarget, UserData]:
        if not table.table_exists():
            table.create_table()

    init_server(
        data=config["data"]["uploads"],
        model=config["data"]["models"],
        reference=config["data"]["reference"],
        static=config["web"]["static"],
        debug=debug,
    )
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    web_thread = threading.Thread(target=run_app, args=([config, debug],), daemon=True)
    job_thread = threading.Thread(target=background_task)
    web_thread.start()
    job_thread.start()

    try:
        # 等待后台任务线程结束（它会响应 stop_event）
        job_thread.join()
    except KeyboardInterrupt:
        stop_event.set()
        job_thread.join(timeout=5)  # 最多等5秒
        logger.info("Background job thread terminated.")


if __name__ == "__main__":
    pass
