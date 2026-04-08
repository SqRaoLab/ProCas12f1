#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""training code"""

import gc
import json
import os
import pickle
from glob import glob
from typing import List, Optional

import click
import numpy as np
import onnxruntime as ort
import optuna
import pandas as pd
import pytorch_lightning as pl
import torch
from loguru import logger
from optuna.pruners import MedianPruner
from optuna.samplers import CmaEsSampler
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.model_selection import StratifiedKFold, train_test_split
from torch.utils.data import DataLoader, Subset, TensorDataset
from tqdm import tqdm

from src.config import Config
from src.model.features import convert_features
from src.model.model import MODEL_SIZES, Model

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*legacy TorchScript-based ONNX export.*")
warnings.filterwarnings("ignore", category=UserWarning)


def split_data(
    X, y, test_size, random_state=None, stratify=None, return_for_test=False
):
    """
    Split data into train/val/test and convert to TensorDataset.

    Args:
        X: single array or list of arrays (features)
        y: labels array
        test_size: proportion for test set
        random_state: for reproducibility
        stratify: if True, use y for stratified split; if False/None, no stratification
        return_for_test:
    Returns:
        train_ds, val_ds (or None), test_ds
    """
    # Ensure X is a list
    if not isinstance(X, (list, tuple)):
        X = [X]

    # First split: trainval + test
    indices = list(range(len(y)))

    trainval_idx, test_idx = train_test_split(
        indices, test_size=test_size, random_state=random_state, stratify=stratify
    )

    # Second split (optional): train + val
    train_idx, val_idx = trainval_idx, trainval_idx

    if not return_for_test:
        # Helper: create TensorDataset from indices
        def make_dataset(idxs):
            if len(idxs) == 0:
                return None
            X_tensors = [torch.tensor(data[idxs]).float() for data in X]
            y_tensor = torch.tensor(y[idxs]).float()
            return TensorDataset(*X_tensors, y_tensor)

        train_ds = make_dataset(train_idx)
        val_ds = make_dataset(val_idx)
        test_ds = make_dataset(test_idx)

        return train_ds, val_ds, test_ds, train_idx

    # generate lists for test
    return [data[test_idx] for data in X], y[test_idx], None, None


# ================
# 超参搜索目标函数
# ================


def create_objective(
    ckpt_path: str,
    train_data,
    train_len: int,
    val_data,
    stratify_train,
    seed: int = 42,
    n_epoch: int = 200,
    n_cv_splits: int = 3,
    optim: str = "AdamW",
    lr: float = 1e-3,
):
    # 预先划分所有 fold 的索引
    kfold = StratifiedKFold(n_splits=n_cv_splits, shuffle=True, random_state=seed)
    cv_splits = list(kfold.split(range(train_len), stratify_train))

    # 预构建所有 DataLoader（注意：Dataset 是只读的，可安全复用）
    all_loaders = []
    for train_idx, val_idx in cv_splits:
        train_loader = DataLoader(
            Subset(train_data, train_idx),
            batch_size=32,
            shuffle=True,
            num_workers=6,
            pin_memory=False,  # 启用 pin_memory 加速 GPU 传输
            persistent_workers=True,  # 避免每 epoch 重建进程
            drop_last=False,
        )
        val_loader = DataLoader(
            Subset(val_data, val_idx),
            batch_size=32,
            shuffle=False,
            num_workers=6,  # 验证集可减少 workers
            pin_memory=False,
            persistent_workers=True,
        )
        all_loaders.append((train_loader, val_loader))

    def objective(trial):
        def suggest_hidden_layers(
            trial, name, min_layers, max_layers, min_dim, max_dim, step
        ):
            hidden_layers = trial.suggest_int(
                f"{name}_hidden_layers", min_layers, max_layers
            )
            hidden_dims = []
            for i in range(hidden_layers):
                hidden_dims.append(
                    trial.suggest_int(
                        f"{name}_hidden_dim{i}", min_dim, max_dim, step=step
                    )
                )
            return hidden_dims

        # === 超参建议 ===
        before_pam_linear = trial.suggest_int("before_pam_linear", 1, 256)
        before_pam_hidden = suggest_hidden_layers(trial, "before_pam", 1, 3, 4, 512, 4)
        sg_linear = trial.suggest_int("sg_linear", 64, 512, step=32)
        sg_hidden = suggest_hidden_layers(trial, "sg", 1, 2, 64, 1024, 64)
        after_linear = trial.suggest_int("after_linear", 1, 128)
        after_hidden = suggest_hidden_layers(trial, "after", 1, 2, 4, 512, 4)
        ind_hidden = suggest_hidden_layers(trial, "ind", 1, 2, 4, 512, 4)
        fc_hidden = suggest_hidden_layers(trial, "fc", 1, 3, 4, 1024, 4)
        fc_dropout = trial.suggest_float("fc_dropout", 0.01, 0.5, step=0.01)

        val_losses = []

        for fold, (train_loader, val_loader) in enumerate(all_loaders):
            # === 模型 ===
            model = Model(
                before_pam_linear,
                before_pam_hidden,
                sg_linear,
                sg_hidden,
                after_linear,
                after_hidden,
                ind_hidden,
                fc_hidden + [1],  # 输出 1 维
                fc_dropout,
            )

            model.optim = optim
            model.lr = lr

            # === 回调：早停 + 检查点 ===
            early_stop = EarlyStopping(monitor="val_loss", patience=10, mode="min")

            checkpoint = ModelCheckpoint(
                monitor="val_loss",
                save_top_k=1,
                dirpath=ckpt_path,
                filename=f"{trial.number}_best_model",
            )

            # === 训练器：关闭日志，节省 I/O ===
            trainer = pl.Trainer(
                max_epochs=n_epoch,
                precision="32",
                accelerator="gpu",
                devices=1,
                callbacks=[early_stop, checkpoint],
                accumulate_grad_batches=4,
                enable_progress_bar=False,
                logger=False,  # TensorBoardLogger
                enable_checkpointing=True,
            )

            # === 关键：每 epoch 报告，支持剪枝 ===
            trainer.fit(model, train_loader, val_loader)

            trial.set_user_attr(
                f"fold_{fold}_best_model_path", checkpoint.best_model_path
            )

            # 获取最佳验证损失
            val_loss = trainer.callback_metrics["val_loss"].item()
            del model, trainer, train_loader, val_loader

            torch.cuda.empty_cache()
            gc.collect()

            # if val_loss > 0.2:
            #     return val_loss

            val_losses.append(val_loss)

        loss = np.mean(val_losses)
        # 确保 loss 是有限值
        if np.isinf(loss) or np.isnan(loss):
            return 100  # 返回一个很大的惩罚值，而不是 inf
        return loss

    return objective


# ================
# Train
# ================


def train_model(
    data,
    output_dir: str,
    db: str,
    study_name: str = "train",
    test_size: float = 0.2,
    seed: int = 42,
    n_epoch: int = 20,
    n_cv: int = 3,
    n_trials: int = 20,
    optim: str = "AdamW",
    lr: float = 1e-3,
):
    """train models with optuna util"""

    os.makedirs(output_dir, exist_ok=True)

    train_data, val_data, _, train_index = split_data(
        data["inputs"],
        np.sqrt(data["y"]),
        stratify=None,  # data["stratify"],
        test_size=test_size,
        random_state=seed,
    )
    stratify_train = data["stratify"][train_index]
    train_len = len(train_data)

    # === 创建 study ===
    pl.seed_everything(seed)

    logger.info("create study")
    study = optuna.create_study(
        study_name=study_name,
        storage=db,
        direction="minimize",
        load_if_exists=True,
        pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=5),
        sampler=CmaEsSampler(warn_independent_sampling=False),  # 更快收敛
    )

    study.optimize(
        create_objective(
            ckpt_path=output_dir,
            train_data=train_data,
            val_data=val_data,
            train_len=train_len,
            stratify_train=stratify_train,
            n_cv_splits=n_cv,
            n_epoch=n_epoch,
            optim=optim,
            lr=lr,
        ),
        n_trials=n_trials,
        n_jobs=1,
    )  # sqlite just using 1 jobs


# ================
# Dump
# ================


def export_model_to_onnx(ckpt_path, onnx_path):
    """加载 PyTorch Lightning 模型并导出为 ONNX"""

    # 获取输入样例（必须和训练输入一致）
    # 假设你的输入是四个张量：before_pam, sg, after, ind
    # 你需要提供一个 batch（比如 batch_size=1）
    # the export do not support dict, so be it
    models, shapes, names = [], {}, []
    for key, val in MODEL_SIZES.items():
        models.append(torch.randn(1, *list(reversed(val)), requires_grad=True).cpu())
        shapes[key] = {0: "batch"}
        names.append(key)

    # 重建模型结构（使用相同参数）
    model = Model.load_from_checkpoint(ckpt_path)

    # 导出 ONNX
    torch.onnx.export(
        model.cpu(),
        tuple(models),
        onnx_path,
        export_params=True,  # 带权重
        opset_version=17,
        do_constant_folding=True,  # 优化
        input_names=names,
        dynamo=False,
        output_names=["output"],
        dynamic_axes=shapes,
    )


def dump_model(
    output_dir: str,
    db: str,
    # data,
    # test_size: float = 0.3,
    # seed: int = 42,
    study_name: str = "train",
    top_n: Optional[int] = None,
):
    """
    convert ckpt to onnx model and check by the correlations

    :param output_dir: the input and saved directory
    :param db: the database saved training parameters
    :param data: the features for model validation
    :param test_size: the test set size
    :param seed: random seed
    :param study_name: used to get trail parameters from db
    :param top_n: the best (top n) parameters to save
    """
    # 加载已有 study
    study = optuna.load_study(study_name=study_name, storage=db)

    # test_data, val_data, _, _ = split_data(
    #     data["inputs"],
    #     np.sqrt(data["y"]),
    #     stratify=None,  # data["stratify"],
    #     test_size=test_size,
    #     random_state=seed,
    #     return_for_test=True,
    # )

    # 获取所有已完成的 trials，并按 value 排序
    complete_trials = [
        t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
    ]

    # 按 value 排序（默认最小化）, best score logger
    best_model = {}
    best_model_records = os.path.join(os.path.dirname(output_dir), "best_models.json")
    if os.path.exists(best_model_records):
        with open(best_model_records) as r:
            best_model = json.load(r)

    # only check top 10 trials
    complete_trials = sorted(complete_trials, key=lambda t: t.value)
    if top_n is not None and top_n > 0:
        complete_trials = complete_trials[:top_n]

    for trial in tqdm(complete_trials):
        # check all the ckpt file under this trial
        for ckpt in glob(os.path.join(output_dir, f"{trial.number}_*.ckpt")):
            onnx = ckpt.replace(".ckpt", ".onnx")

            if onnx not in best_model:
                if not os.path.exists(onnx):
                    export_model_to_onnx(ckpt, onnx)

                # valid the prediction results
                # val = predict_value(onnx, test_data)
                # corr, _ = spearmanr(val, val_data)
                # best_model[onnx] = corr

                # tqdm.write(
                #     f"trial number: {trial.number};"
                #     f"loss value: {trial.value};"
                #     f"corr: {corr:.4f}"
                # )

    # save the progress
    # with open(best_model_records, "w+") as w:
    #     json.dump(best_model, w, indent=4)

    # temp = [[x, y] for x, y in best_model.items()]
    # temp = sorted(temp, key=lambda x: x[1])

    # if len(temp) > 0:
    #     with open(
    #         os.path.join(os.path.dirname(output_dir), "best_model.onnx"), "wb+"
    #     ) as w:
    #         with open(temp[0][0], "rb") as r:
    #             w.write(r.read())


def predict_value(ort_session, test_data) -> List[float]:
    """
    check the model
    :param ort_session: the model itself
    :param test_data: test data
    """

    if isinstance(ort_session, str):
        ort_session = ort.InferenceSession(ort_session)

    input_names = [inp.name for inp in ort_session.get_inputs()]
    input_data = {
        name: array.astype(np.float32) for name, array in zip(input_names, test_data)
    }
    outputs = ort_session.run(None, input_data)
    # y_pred = outputs[0].reshape(-1)
    return list(np.clip(outputs[0].reshape(-1), 0, 1) ** 2 * 100)


@click.command(
    context_settings=dict(help_option_names=["-h", "--help"]), no_args_is_help=True
)
@click.option(
    "-i",
    "--infile",
    type=click.Path(exists=True),
    help="the path to input file, standard output by calFreq, please filter before using this function",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=True,
    help="path to save model, only save state_dict",
)
@click.option("-t", "--n-jobs", type=int, default=10, help="the number of cpu to used")
@click.option("--seed", type=int, default=42, help="the random state")
@click.option(
    "--test-size", type=float, default=0.3, help="the fraction of test dataset"
)
@click.option("--n-epoch", type=int, default=100, help="the number of epoch")
@click.option(
    "--n-cv", type=int, default=5, help="the number of cross validation splits"
)
@click.option("--n-trials", type=int, default=200, help="the number of trials")
@click.option("--dump", is_flag=True, help="only dump best model")
@click.option("--top-n", type=int, help="only dump best (top n) models")
@click.option(
    "--optim",
    type=click.Choice(["AdamW", "SGD"]),
    default="AdamW",
    help="choose one optimizer to use",
)
@click.option("--lr", type=float, default=1e-3, help="the learning rate")
def train(
    infile,
    output,
    n_jobs,
    seed,
    test_size,
    n_epoch: int = 20,
    n_cv: int = 3,
    lr: float = 1e-3,
    n_trials: int = 20,
    dump: bool = False,
    top_n: Optional[int] = None,
    optim: str = "AdamW",
):
    """train deep learning model"""
    os.makedirs(output, exist_ok=True)

    # optuna.seed(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)

    pkl = os.path.join(output, "features.pkl")
    if os.path.exists(pkl):
        logger.info("restore features from cache")
        try:
            with open(pkl, "rb") as f:
                data = pickle.load(f)
        except Exception as e:
            logger.error(e)
            logger.error(
                f"failed to load feature cache from {pkl}, please remove and run again"
            )
            exit(1)
    else:
        logger.info("generate features")
        data, _ = convert_features(infile, n_jobs=n_jobs, output=pkl)

        with open(pkl, "wb+") as w:
            pickle.dump(data, w)

    db = f"sqlite:///{output}/params.db"
    study_name = "train"
    ckpt = os.path.join(output, "ckpts")

    logger.info("training model")

    train_model(
        data=data,
        output_dir=ckpt,
        db=db,
        study_name=study_name,
        seed=seed,
        test_size=test_size,
        n_epoch=n_epoch,
        n_cv=n_cv,
        n_trials=n_trials,
        optim=optim,
        lr=lr,
    )

    if dump:
        logger.info("dump best model")
        dump_model(
            output_dir=ckpt,
            db=db,
            # test_size=test_size,
            # seed=seed,
            study_name=study_name,
            # data=data,
            top_n=top_n,
        )


@click.command(
    context_settings=dict(help_option_names=["-h", "--help"]), no_args_is_help=True
)
@click.option(
    "-i",
    "--infile",
    type=click.Path(exists=True),
    required=True,
    help="the path to input file, standard output by calFreq, please filter before using this function",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=True,
    help="path to output file",
)
@click.option(
    "-m",
    "--model",
    type=str,
    required=True,
    help="path to saved model or just keyword",
)
@click.option(
    "-n",
    "--n-jobs",
    type=int,
    default=1,
    help="the number of cpu to use",
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, dir_okay=True),
    default="./config.ini",
)
@click.option("--use-cache", is_flag=True)
def predict(
    infile: str,
    output: str,
    model: str,
    n_jobs: int,
    config: str,
    use_cache: bool = False,
):
    """predict the editing frequency"""
    config = Config(config)

    input_df = pd.read_csv(infile, sep=None, engine="python")
    if os.path.isfile(model):
        onnx = model

        if "cas" not in input_df.columns:
            logger.warning("??")
            input_df["cas"] = "SpaCas12f1"
    else:
        onnx = os.path.join(config["data"]["models"], f"{model}.onnx")
        assert os.path.exists(onnx), f"{onnx} not found"

        if "cas" not in input_df.columns:
            logger.warning(f"cas protein not labeled in input csv, using {model}")
            input_df["cas"] = model

    if "cas" not in input_df.columns:
        raise ValueError("cas not exists in input file")

    # input_df = filter_df(input_df)

    logger.info(f"using model: {onnx}")

    predict = []
    chunk = 10000
    if input_df.shape[0] > chunk:
        logger.info("performing predictions in batches")

    # only load model once
    ort_session = ort.InferenceSession(onnx)
    for i in range(0, input_df.shape[0], chunk):
        if use_cache:
            outdir = os.path.dirname(output)
            cache = os.path.join(outdir, "cache")
            os.makedirs(cache, exist_ok=True)

            pkl = os.path.join(cache, f"{i}.pkl")
            if not os.path.exists(pkl):
                data, temp_df = convert_features(
                    input_df.iloc[i : (i + chunk), :], n_jobs
                )

                with open(pkl, "wb+") as w:
                    pickle.dump({"data": data, "df": temp_df}, w)
            else:
                logger.debug(f"restore cache {pkl}")
                with open(pkl, "rb") as r:
                    data = pickle.load(r)
                    data, temp_df = data["data"], data["df"]
        else:
            data, temp_df = convert_features(input_df.iloc[i : (i + chunk), :], n_jobs)

        temp_df["predict"] = predict_value(ort_session, data["inputs"])

        predict.append(temp_df)

    input_df = pd.concat(predict)
    input_df.to_csv(output, index=False)


if __name__ == "__main__":
    pass
