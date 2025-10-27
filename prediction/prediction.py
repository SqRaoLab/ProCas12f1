import pandas as pd
import argparse
import numpy as np
from ViennaRNA import RNA
import Bio.SeqUtils.MeltingTemp as MT
import itertools
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import gc
import onnxruntime as ort


class FeatureExtractor:
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
        scaffolds = {
            "CasMINI": "GGGCTTCACTGATAAAGTGGAGAACCGCTTCACCAAAAGCTGTCCCTTAGGGGATTAGAACTTGAGTGAAGGTGGGCTGCTTGCATCAGCCTAATGTCGAGAAGTGCTTTCTTCGGAAAGTAACCCTCGAAACAAATTCATTTGAATGAAGGAATGCAAC",
            "OsCas12f1": "AGGGCCGACTTCCCGGCCCAAAATCGAGACAGTAGCCGTAAAACGTTGAGTTTCAGCGTGGGCGACACACTCGAAAAGGTTAAGATATGCACATAGTAATCCGTGCATGAGCCGCGAAAGCGGCTTGAAGG",
            "RhCas12f1": "GGACGGCTGATTTAGCAGCCGAAGTCTGAGGGCATGTAGAAAAAAGTATAGGTATATACCAACATACTTGCATTGCCACTCGGAAAGGGTTAACCTTGGTCATTGTGTTACCGACCAAGCATTCCAGAAATGGAATGTAAAT",
            "enAsCas12f1": "GGATTCGTCGGTTCAGCGACGATAAGCCGAGAAGTGCCAATAAAACTGTTAAGTGGTTTGGTAACGCTCGGTAAGGTCCGAAAGGAGAACCACT",
            "SpaCas12f1": "GTTTCGCGCGCCAGGGCAGTTAGGTGCCCTAAAAGAGCGAAGTGGCCGAAAGGAAAGGCTAACGCTTCTCTAACGCTACGGCGACCTTGGCGAAATGCCATCAATACCACGCGGCCCGAAAGGGTTCGCGCGAAACAAGGTAAGCGCGTGGATTG",
        }
        return scaffolds[self.cas] + self.seqs

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
        count_chars=["A", "T", "C", "G"],
        return_1d=True,
    ):
        """One-hot encode the given sequence for specified characters over the sequence length."""
        one_hot_matrix = np.zeros((len(count_chars), seq_len), dtype=int)
        for pos in range(seq_len):
            for i, char in enumerate(count_chars):
                one_hot_matrix[i, pos] = 1 if seq[pos : pos + char_len] == char else 0

        if return_1d:
            return {
                f"{prefix}_{char}_{pos+1}": one_hot_matrix[i, pos]
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

        ExecutorClass = ProcessPoolExecutor if seq_num > 1000 else ThreadPoolExecutor
        with ExecutorClass(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.process_args, tasks))
        gc.collect()
        return pd.DataFrame(results)

    def process_args(self, args):
        return self.process_row(*args)


def get_parser():
    desc = """
    Program: Cas12_prediction
    Version: 0.1
    Author : Liheng Luo
    Email  : <luoliheng@ibms.pumc.edu.cn>

    Optional Cas12s: ['CasMINI', 'OsCas12f1', 'RhCas12f1', 'enAsCas12f1', 'SpaCas12f1']

    Examples:
        1) input file:
                ID,SEQ(4bp pam + 20bp target)
                seq1,TTTAACAGGGGATACACCTCCTCT

           """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=desc
    )

    parser.add_argument(
        "-i",
        "--input_filename",
        type=str,
        help="The name of the input file. MUST be a two-column .csv file",
        required=True,
    )
    parser.add_argument(
        "-n",
        "--Cas12f_name",
        choices=["CasMINI", "OsCas12f1", "RhCas12f1", "enAsCas12f1", "SpaCas12f1"],
        type=str,
        help="The name of the Cas12f to use for prediction.",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output_filename",
        type=str,
        default="./output.csv",
        help="The name of the output file. (default='./output.csv')",
    )

    return parser


def one_hot_encode(seq):

    cols = [f"pos_{i+1}_{nuc}" for i in range(len(seq)) for nuc in ["A", "T", "C", "G"]]
    one_hot_df = pd.DataFrame(columns=cols, index=[0]).fillna(0)

    for i, nucleotide in enumerate(seq):
        col_name = f"pos_{i+1}_{nucleotide}"
        one_hot_df.at[0, col_name] = 1

    one_hot_df.columns = [
        f"{prefix}_{i}_{nuc}"
        for prefix, end in [("PAM", 5), ("target", 21)]
        for i in range(1, end)
        for nuc in ["A", "T", "C", "G"]
    ]
    return one_hot_df


def main(input_filename, cas, output_filename):
    input_df = pd.read_csv(input_filename)
    before = pd.DataFrame(
        list(
            input_df.iloc[:, 1]
            .str[:6]
            .apply(lambda seq: FeatureExtractor.one_hot_encode(seq, 6, prefix="before"))
        )
    )
    after = pd.DataFrame(
        list(
            input_df.iloc[:, 1]
            .str[-6:]
            .apply(lambda seq: FeatureExtractor.one_hot_encode(seq, 6, prefix="after"))
        )
    )
    extractor = FeatureExtractor(
        input_df.iloc[:, 1].str[10:30],
        input_df.iloc[:, 1].str[6:10],
        cas,
        return_twomer=False,
        return_ss=True,
        return_ind=True,
        max_workers=1,
    )
    target = extractor.extract_features()
    X_before_pam = np.array(pd.concat([before, target.iloc[:, :16]], axis=1)).reshape(
        -1, 10, 4
    )
    X_sg = np.concatenate(
        (
            np.array(target.iloc[:, 16:96]).reshape(-1, 20, 4),
            np.array(target.iloc[:, 96:156]).reshape(-1, 20, 3),
            np.array(target.iloc[:, 156:216]).reshape(-1, 20, 3),
        ),
        axis=2,
    )
    X_after = np.array(after).reshape(-1, 6, 4)
    X_ind = np.array(target.iloc[:, 216:]).reshape(-1, 1, 31)
    inputs = (X_before_pam, X_sg, X_after, X_ind)
    ort_session = ort.InferenceSession(f"models/{cas}_best_model.onnx")

    input_names = [inp.name for inp in ort_session.get_inputs()]
    input_data = {
        name: array.astype(np.float32) for name, array in zip(input_names, inputs)
    }
    outputs = ort_session.run(None, input_data)

    y_pred = np.clip(outputs[0].reshape(-1), 0, 1) ** 2
    input_df[f"{cas}_efficiency"] = y_pred
    input_df.to_csv(output_filename, index=False)


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    main(args.input_filename, args.Cas12f_name, args.output_filename)
