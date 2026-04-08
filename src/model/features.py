#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用于预备训练数据的代码
"""

import itertools
import pickle
from multiprocessing import Pool
from typing import Optional, Union

import Bio.SeqUtils.MeltingTemp as MT
import numpy as np
import pandas as pd
from loguru import logger
from tqdm import tqdm
from ViennaRNA import RNA

from src.model.model import MODEL_SIZES

SCAFFOLDS = {
    "CasMINI": "GGGCTTCACTGATAAAGTGGAGAACCGCTTCACCAAAAGCTGTCCCTTAGGGGATTAGAACTTGAGTGAAGGTGGGCTGCTTGCATCAGCCTAATGTCGAGAAGTGCTTTCTTCGGAAAGTAACCCTCGAAACAAATTCATTTGAATGAAGGAATGCAAC",
    "OsCas12f1": "AGGGCCGACTTCCCGGCCCAAAATCGAGACAGTAGCCGTAAAACGTTGAGTTTCAGCGTGGGCGACACACTCGAAAAGGTTAAGATATGCACATAGTAATCCGTGCATGAGCCGCGAAAGCGGCTTGAAGG",
    "enOsCas12f1": "AGGGCCGACTTCCCGGCCCAAAATCGAGACAGTAGCCGTAAAACGTTGAGTTTCAGCGTGGGCGACACACTCGAAAAGGTTAAGATATGCACATAGTAATCCGTGCATGAGCCGCGAAAGCGGCTTGAAGG",
    "RhCas12f1": "GGACGGCTGATTTAGCAGCCGAAGTCTGAGGGCATGTAGAAAAAAGTATAGGTATATACCAACATACTTGCATTGCCACTCGGAAAGGGTTAACCTTGGTCATTGTGTTACCGACCAAGCATTCCAGAAATGGAATGTAAAT",
    "enRhCas12f1": "GGACGGCTGATTTAGCAGCCGAAGTCTGAGGGCATGTAGAAAAAAGTATAGGTATATACCAACATACTTGCATTGCCACTCGGAAAGGGTTAACCTTGGTCATTGTGTTACCGACCAAGCATTCCAGAAATGGAATGTAAAT",
    "enAsCas12f1": "GGATTCGTCGGTTCAGCGACGATAAGCCGAGAAGTGCCAATAAAACTGTTAAGTGGTTTGGTAACGCTCGGTAAGGTCCGAAAGGAGAACCACT",
    "enAsCas12f": "GGATTCGTCGGTTCAGCGACGATAAGCCGAGAAGTGCCAATAAAACTGTTAAGTGGTTTGGTAACGCTCGGTAAGGTCCGAAAGGAGAACCACT",
    "AsCas12f-HKRA": "GGATTCGTCGGTTCAGCGACGATAAGCCGAGAAGTGCCAATAAAACTGTTAAGTGGTTTGGTAACGCTCGGTAAGGTCCGAAAGGAGAACCACT",
    "SpaCas12f1": "GTTTCGCGCGCCAGGGCAGTTAGGTGCCCTAAAAGAGCGAAGTGGCCGAAAGGAAAGGCTAACGCTTCTCTAACGCTACGGCGACCTTGGCGAAATGCCATCAATACCACGCGGCCCGAAAGGGTTCGCGCGAAACAAGGTAAGCGCGTGGATTG",
}


class FeatureExtractor(object):
    def __init__(
        self,
        seqs,
        pam,
        cas,
        return_twomer=False,
        return_ss=False,
        return_ind=False,
        max_workers=None,
    ):
        self.seqs = seqs
        self.seq_len = self.check_seq_length(self.seqs)
        self.pam = pam
        self.pam_len = self.check_seq_length(self.pam)
        self.pam_seqs = pam + seqs
        self.cas = cas
        self.scaffold_seq = self.get_scaffold_seq()
        self.return_twomer = return_twomer
        self.two_mer = self.get_kmer(2)
        self.return_ss = return_ss
        self.return_ind = return_ind
        self.max_workers = (
            min(24, len(seqs) // 1000) if max_workers is None else max_workers
        )

    @staticmethod
    def check_seq_length(seq) -> int:
        """Check if all sequences in the given series have the same length; raise ValueError if not."""
        lengths = np.unique(seq.apply(len))
        if len(lengths) > 1:
            raise ValueError("All seqs must have the same length.")
        else:
            return lengths[0]

    def get_scaffold_seq(self) -> object:
        """Fetch the scaffold sequence based on the Cas type provided and append the input sequences."""
        return SCAFFOLDS[self.cas] + self.seqs

    @staticmethod
    def get_kmer(k):
        """Generate all possible k-mer combinations of DNA bases (A, T, C, G)."""
        return ["".join(p) for p in itertools.product(["A", "T", "C", "G"], repeat=k)]

    @staticmethod
    def one_hot_encode(
        seq,
        seq_len,
        char_len=1,
        prefix="seq",
        count_chars=None,
        return_1d=True,
    ):
        """One-hot encode the given sequence for specified characters over the sequence length."""

        if count_chars is None:
            count_chars = ["A", "T", "C", "G"]

        one_hot_matrix = np.zeros((len(count_chars), seq_len), dtype=int)
        for pos in range(seq_len):
            for i, char in enumerate(count_chars):
                one_hot_matrix[i, pos] = 1 if seq[pos : pos + char_len] == char else 0

        if return_1d:
            return {
                f"{prefix}_{char}_{pos + 1}": one_hot_matrix[i, pos]
                for pos in range(seq_len)
                for i, char in enumerate(count_chars)
            }
        else:
            return one_hot_matrix

    @staticmethod
    def independent_features(seq):
        """Calculate independent features such as base counts and homopolymers."""
        ind_features = {}
        base_counts = {base: seq.count(base) for base in "ATCG"}
        for base, base_count in base_counts.items():
            ind_features[f"{base}_count"] = base_count
            ind_features[f"{base}_homo"] = FeatureExtractor.max_occurr(seq, base)

        two_mer_counts = {
            two_mer: seq.count(two_mer) for two_mer in FeatureExtractor.get_kmer(2)
        }
        for two_mer, two_mer_count in two_mer_counts.items():
            ind_features[f"{two_mer}_count"] = two_mer_count

        Sequni = sum(seq[i] == seq[i - 1] for i in range(1, len(seq)))
        ind_features["Sequni"] = Sequni
        return ind_features

    @staticmethod
    def max_occurr(seq, string):
        """Find the maximum occurrence of contiguous repeats of a substring in the given sequence."""
        count = 0
        max_count = 0
        for i in range(len(seq) - len(string) + 1):
            if seq[i : i + len(string)] == string:
                count += 1
                max_count = max(max_count, count)
            else:
                count = 0
        return max_count

    def process_row(self, seq, pam, scaffold_seq, pam_len, seq_len, two_mer):
        ss_sca, mfe_global = RNA.fold(scaffold_seq)
        ss_g, mfe_grna = RNA.fold(seq)
        _, mfe_7_20 = RNA.fold(seq[6:])

        feature = {}
        feature.update(self.one_hot_encode(pam, seq_len=pam_len, prefix="pam"))
        feature.update(self.one_hot_encode(seq, seq_len=seq_len, prefix="grna"))
        if self.return_twomer:
            feature.update(
                self.one_hot_encode(
                    seq,
                    seq_len=seq_len - 1,
                    char_len=2,
                    prefix="grna",
                    count_chars=two_mer,
                )
            )

        if self.return_ss:
            feature.update(
                self.one_hot_encode(
                    ss_sca[-seq_len:],
                    seq_len=seq_len,
                    prefix="ss_sca",
                    count_chars=["(", ".", ")"],
                )
            )
            feature.update(
                self.one_hot_encode(
                    ss_g,
                    seq_len=seq_len,
                    prefix="ss",
                    count_chars=["(", ".", ")"],
                )
            )

        if self.return_ind:
            feature.update(self.independent_features(seq))
            feature["mt_grna"] = MT.Tm_Wallace(seq)
            feature["mt_dna"] = MT.Tm_NN(pam + seq, nn_table=MT.DNA_NN2)
            feature["mt_dna_rna"] = MT.Tm_NN(seq, nn_table=MT.R_DNA_NN1)
            feature["mfe_global"] = mfe_global
            feature["mfe_grna"] = mfe_grna
            feature["mfe_7_20"] = mfe_7_20

        return feature

    def extract_features(
        self,
    ):
        seq_num = len(self.seqs)
        tasks = zip(
            self.seqs,
            self.pam,
            self.scaffold_seq,
            [self.pam_len] * seq_num,
            [self.seq_len] * seq_num,
            [self.two_mer] * seq_num,
        )
        tasks = [x for x in tasks]
        results = []
        with Pool(self.max_workers) as executor:
            for row in list(
                tqdm(executor.imap(self.process_args, tasks), total=len(tasks))
            ):
                if row is not None:
                    results.append(row)

        return pd.DataFrame(results)

    def process_args(self, args):
        try:
            return self.process_row(*args)
        except Exception:
            return None


def __prepare_for_training(input_df: pd.DataFrame):
    """one hot encode for before and after"""
    input_df = input_df[input_df["before"].notna()]
    input_df = input_df[input_df["after"].notna()]

    logger.info("formatting before")
    before = pd.DataFrame(
        list(
            input_df["before"].apply(
                lambda seq: FeatureExtractor.one_hot_encode(seq, 6, prefix="before")
            )
        )
    )

    logger.info("formatting after")
    after = pd.DataFrame(
        list(
            input_df["after"].apply(
                lambda seq: FeatureExtractor.one_hot_encode(seq, 6, prefix="after")
            )
        )
    )

    return before, after


def __prepare_for_user(input_df: pd.DataFrame):
    """formatting features with user input"""
    input_df["before"] = input_df.iloc[:, 1].str[:6]
    input_df["after"] = input_df.iloc[:, 1].str[-6:]
    input_df["pam"] = input_df.iloc[:, 1].str[6:10]
    input_df["target"] = input_df.iloc[:, 1].str[10:30]
    return input_df


def prepare_training_data(
    input_df: pd.DataFrame, cas: str, n_jobs: int, return_df: bool = False
):
    """formatting features"""
    logger.info(f"{input_df.shape[0]} records of {cas}")

    if "before" not in input_df.columns and "after" not in input_df.columns:
        logger.info("preparing features")
        input_df = __prepare_for_user(input_df)

    before, after = __prepare_for_training(input_df)
    logger.info(f"{input_df.shape[0]} records after filtering")

    target_key = "target"
    if "sgRNA" in input_df.columns and len(input_df["target"][0]) > 20:
        logger.info("should by our design format, using sgRNA instead of target")
        target_key = "sgRNA"

    extractor = FeatureExtractor(
        input_df[target_key],
        input_df["pam"],
        cas,
        return_twomer=False,
        return_ss=True,
        return_ind=True,
        max_workers=n_jobs,
    )
    logger.info("extract features")
    target = extractor.extract_features()

    if return_df:
        return target, input_df

    before_pam = np.array(
        pd.concat([pd.DataFrame(before), target.iloc[:, :16]], axis=1)
    ).reshape(-1, *reversed(MODEL_SIZES["before_pam"]))
    sg = np.concatenate(
        (
            np.array(target.iloc[:, 16:96]).reshape(-1, MODEL_SIZES["sg"][-1], 4),
            np.array(target.iloc[:, 96:156]).reshape(-1, MODEL_SIZES["sg"][-1], 3),
            np.array(target.iloc[:, 156:216]).reshape(-1, MODEL_SIZES["sg"][-1], 3),
        ),
        axis=2,
    )
    after = np.array(after).reshape(-1, *reversed(MODEL_SIZES["after"]))
    ind = np.array(target.iloc[:, 216:]).reshape(-1, *reversed(MODEL_SIZES["ind"]))
    inputs = [before_pam, sg, after, ind]
    return inputs, input_df


def convert_features(
    input_filename: Union[str, pd.DataFrame],
    n_jobs: int,
    output: Optional[str] = None,
    cas: Optional[str] = None,
    return_df: bool = False,
):
    """convert features from calFreq output to pkl for machine learning"""

    if isinstance(input_filename, str):
        input_df = pd.read_csv(input_filename, sep="\t")
    else:
        input_df = input_filename

    if cas is None:
        for cas in input_df["cas"]:
            cas = {"OsCas12f1-1": "OsCas12f1", "enAsCas12f": "enAsCas12f1"}.get(
                cas, cas
            )
            break
    # 过滤掉只出现一次的pam

    inputs, input_df = prepare_training_data(input_df, cas, n_jobs, return_df=return_df)

    data = {
        "data": input_df,
        "inputs": inputs,
        "y": [x / 100 for x in input_df["corrected_efficiency"]],
        "stratify": pd.Categorical(input_df["pam"]).codes,
    }

    if output is not None:
        with open(output, "wb+") as w:
            pickle.dump(
                {
                    "data": input_df,
                    "inputs": inputs,
                    "y": [x for x in input_df["corrected_efficiency"]],
                    "stratify": pd.Categorical(input_df["pam"]).codes,
                },
                w,
            )
    return data, input_df


if __name__ == "__main__":
    pass
