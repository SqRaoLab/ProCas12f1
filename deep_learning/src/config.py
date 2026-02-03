#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser


class Config(object):
    def __init__(self, path: str):
        # 创建 ConfigParser 对象
        config = configparser.ConfigParser()

        # 读取配置文件
        config.read(path)

        self.data = {}
        for section in config.sections():
            self.data[section] = {x: y for x, y in config[section].items()}

    def __getitem__(self, item):
        return self.data[item]


if __name__ == "__main__":
    pass
