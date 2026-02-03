#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" """

import os

from flask import Blueprint, current_app, jsonify, send_file

from src.db import Genome
from src.design import IUPAC_DICT, PAM_MAP

api_const = Blueprint("const", __name__)


@api_const.route("/genome")
def default_genome():
    res = []
    for rec in Genome.select():
        res.append(
            {"label": f"{rec.scientific_name} ({rec.genome})", "value": rec.genome}
        )
    return jsonify(res)


@api_const.route("/pam")
def default_pam():
    res = []
    for k, v in PAM_MAP.items():
        res.append({"label": f"{k} ({v})", "value": v})
    return jsonify(res)


@api_const.route("/rule")
def default_pam_rule():
    return jsonify(IUPAC_DICT)


@api_const.route("/example/fasta")
def default_fasta():
    return send_file(
        os.path.join(current_app.config["DATA"], "example", "sequence.fasta"),
        mimetype="text/plain",
    )


if __name__ == "__main__":
    pass
