#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" """

import logging
import sys

import click
from loguru import logger

from src.design import design
from src.machine_learning import ml, shap
from src.server import start
from src.setup import setup
from src.train import predict, train

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> - <level>{level}</level> - <level>{message}</level>",
)


@click.group()
def main():
    pass


main.add_command(setup)
main.add_command(start)
main.add_command(train)
main.add_command(predict)
main.add_command(design)
main.add_command(ml)
main.add_command(shap)


if __name__ == "__main__":
    main()
