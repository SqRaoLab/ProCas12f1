#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基因相关的通路
"""

from flask import Blueprint, jsonify

from src.db import Genome, Reference

api_gene = Blueprint("gene", __name__)


@api_gene.route("/<genome>/<gene>", methods=["GET"])
def gene(genome: str, gene: str):
    """根据输入的内容输出相似的基因名"""

    if len(gene) < 3:
        return jsonify({"msg": "input text too short"}), 500

    # 查询相似的基因名
    query = (
        Reference.select()
        .join(Genome, on=(Genome.genome == Reference.genome))
        .where(
            (Genome.genome == genome)
            & (Reference.kind == "gene")
            & (
                Reference.gene_id.ilike(f"%{gene}%")
                | (Reference.name.ilike(f"%{gene}%"))
            )
        )
        .order_by(Reference.name)
        .limit(10)
    )
    res = []
    for rec in query:
        res.append({"id": rec.gene_id, "name": rec.name})
    return jsonify(res)


# @api_gene.route("/sequence/<genome>/<gene>", methods=["GET"])
# def sequence(genome: str, gene: str):
#     """根据输入的内容输出相似的基因名"""
#
#     if len(gene) < 3:
#         return jsonify({"msg": "input text too short"}), 500
#
#     job = JobParams(gene, genome)
#
#     return jsonify([x for x in job.sequence])


if __name__ == "__main__":
    pass
