#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multiple machine learning models"""

import os
import pickle
import sys
import warnings
from glob import glob
from typing import Optional

import click
import numpy as np
import pandas as pd
import seaborn as sns
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor, early_stopping
from loguru import logger
from matplotlib import pyplot as plt
from shap import TreeExplainer, plots
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import (
    AdaBoostRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import (  # ElasticNet,; Lasso,; PassiveAggressiveRegressor,  # deprecated in scikit-learn 1.10+
    LinearRegression,
    Ridge,
    SGDRegressor,
)
from sklearn.model_selection import (
    RandomizedSearchCV,
    cross_val_score,
    train_test_split,
)
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor

from src.model.features import convert_features

warnings.filterwarnings("ignore")

sns.set_theme(style="whitegrid", palette=None)


class LGBMRegressorWithES(BaseEstimator, RegressorMixin):
    def __init__(
        self,
        num_leaves=31,
        learning_rate=0.1,
        n_estimators=1000,  # 设大值，靠早停控制
        device="cpu",
        random_state=None,
        early_stopping_rounds=20,
        eval_size=0.2,
        n_jobs: int = 1,
    ):
        self.num_leaves = num_leaves
        self.learning_rate = learning_rate
        self.n_estimators = n_estimators
        self.device = device
        self.random_state = random_state
        self.early_stopping_rounds = early_stopping_rounds
        self.eval_size = eval_size
        self.n_jobs = n_jobs

    def fit(self, X, y):
        # 划分内部验证集用于早停
        if self.eval_size > 0:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=self.eval_size, random_state=self.random_state
            )
            eval_set = [(X_val, y_val)]
        else:
            X_train, y_train = X, y
            eval_set = None

        self.model_ = LGBMRegressor(
            num_leaves=self.num_leaves,
            learning_rate=self.learning_rate,
            n_estimators=self.n_estimators,
            device=self.device,
            random_state=self.random_state,
            feature_fraction=0.8,
            n_jobs=self.n_jobs,
            max_depth=6,  # to avoid too complicated graph
            verbose=-1,
        )

        fit_params = {}
        if eval_set is not None:
            fit_params["eval_set"] = eval_set
            fit_params["callbacks"] = [
                early_stopping(self.early_stopping_rounds, verbose=False)
            ]

        self.model_.fit(X_train, y_train, **fit_params)
        return self

    def predict(self, X):
        return self.model_.predict(X)

    def get_params(self, deep=True):
        return {
            "num_leaves": self.num_leaves,
            "learning_rate": self.learning_rate,
            "n_estimators": self.n_estimators,
            "device": self.device,
            "random_state": self.random_state,
            "early_stopping_rounds": self.early_stopping_rounds,
            "eval_size": self.eval_size,
        }

    def set_params(self, **params):
        for key, value in params.items():
            setattr(self, key, value)
        return self


def split_data(data, test_size, random_state=None):
    x, x_test, y, y_test = train_test_split(
        [x for x in range(data["inputs"].shape[0])],
        data["y"],
        test_size=test_size,
        random_state=random_state,
        stratify=data["stratify"],
    )

    return data["inputs"].iloc[x, :], y, data["inputs"].iloc[x_test, :], y_test


def get_models_and_params(task="regression", seed=42, n_jobs=10):
    models = {}

    # 回归任务参数
    if task == "regression":
        models = {
            "Decision Tree": (
                DecisionTreeRegressor(random_state=seed),
                {
                    "max_depth": [3, 5, 7, 10, None],
                    "min_samples_split": [2, 5, 10],
                    "min_samples_leaf": [1, 2, 4],
                    "criterion": ["squared_error", "friedman_mse"],
                },
            ),
            "Passive Aggressive": (
                SGDRegressor(
                    loss="epsilon_insensitive",
                    penalty="l2",  # Passive Aggressive 默认使用 L2 正则（通过 C 控制）
                    learning_rate="pa1",  # 关键：启用 PA-I 更新规则
                    eta0=1.0,  # PA 要求固定为 1.0
                    random_state=seed,
                    warm_start=False,
                    average=False,
                ),
                {
                    "alpha": [1 / 0.1, 1 / 1.0, 1 / 10.0],  # alpha = 1 / C
                    "max_iter": [50, 100, 200],
                    "tol": [1e-3, 1e-4],
                },
            ),
            "AdaBoost": (
                AdaBoostRegressor(random_state=seed),
                {"n_estimators": [50, 100, 200], "learning_rate": [0.01, 0.1, 1.0]},
            ),
            "K Neighbors": (
                KNeighborsRegressor(),
                {
                    "n_neighbors": [3, 5, 7, 10],
                    "weights": ["uniform", "distance"],
                    "p": [1, 2],
                },
            ),
            "Random Forest": (
                RandomForestRegressor(random_state=seed, n_jobs=n_jobs),
                {
                    "n_estimators": [100, 200, 300],
                    "max_depth": [4, 6, 8, 10, 12],  # 不要 None！
                    "min_samples_split": [10, 20, 30, 50],  # ≥10，避免太细
                    "min_samples_leaf": [5, 10, 15, 20],  # ≥5
                    "max_features": ["sqrt", "log2", 0.5],
                    "bootstrap": [True],
                },
            ),
            "Linear": (LinearRegression(), {}),
            "Ridge": (
                Ridge(random_state=seed),
                {"alpha": [0.1, 1.0, 10.0], "solver": ["auto", "svd", "cholesky"]},
            ),
            "Gradient Boosting": (
                GradientBoostingRegressor(random_state=seed),
                {
                    "n_estimators": [100, 200],
                    "learning_rate": [0.01, 0.1],
                    "max_depth": [3, 5],
                    "subsample": [0.8, 1.0],
                },
            ),
            "Light Gradient Boosting Machine": (
                LGBMRegressorWithES(device="gpu", random_state=seed),
                {
                    "num_leaves": [31, 62],
                    "learning_rate": [0.01, 0.1],
                    "device": ["gpu"],
                },
            ),
            "Catboost": (
                CatBoostRegressor(verbose=0, random_state=seed),
                {
                    "iterations": [100, 200],
                    "learning_rate": [0.01, 0.1],
                    "depth": [4, 6],
                },
            ),
        }
    elif task == "classification":
        # 可以扩展分类任务（略）
        pass

    # 过滤掉未安装的模型
    filtered_models = {}
    for name, (model, params) in models.items():
        if model is not None:
            filtered_models[name] = (model, params)
        else:
            logger.error(f"model {name} is not installed, skip...")
    return filtered_models


def batch_train_models(
    X,
    y,
    seed=42,
    cv=3,
    n_iter=10,
    n_jobs: int = -1,
    scoring="neg_mean_squared_error",
    model_directory: Optional[str] = None,
):
    """
    批量训练多个模型并搜索最优参数
    """
    # logger.info(f"data shape: X={X.shape}, y={y.shape}")
    logger.info(f"score: {scoring}")
    logger.info("-" * 60)

    results = []

    models = get_models_and_params(seed=seed, n_jobs=n_jobs)

    for name, (model, param_dist) in models.items():
        logger.info(f"train model: {name}")

        if model_directory:  # and name != "Random Forest":
            if os.path.exists(os.path.join(model_directory, f"{name}.pkl")):
                logger.info(f"cached model {name} found, skip")
                continue

        if name == "Catboost":
            result = model.randomized_search(param_dist, X=X, y=y, cv=cv, n_iter=n_iter)
            best_score = np.min(result["cv_results"]["test-RMSE-mean"])
            best_params = result["params"]
        elif name == "Light Gradient Boosting Machine":
            search = RandomizedSearchCV(
                model,
                param_distributions=param_dist,
                n_iter=n_iter,
                cv=cv,
                scoring=scoring,
                n_jobs=1,  # to avoid memory leak
                verbose=0,
                random_state=seed,
            )
            search.fit(X, y)
            best_score = search.best_score_
            best_params = search.best_params_
        elif param_dist:  # 有超参数搜索空间
            search = RandomizedSearchCV(
                model,
                param_dist,
                n_iter=n_iter,
                cv=cv,
                scoring=scoring,
                n_jobs=n_jobs,  # to avoid memory leak
                verbose=0,
                random_state=seed,
            )
            search.fit(X, y)
            best_score = search.best_score_
            best_params = search.best_params_
        else:  # 无超参数（如 LinearRegression）
            model.fit(X, y)
            cv_scores = cross_val_score(model, X, y, cv=cv, scoring=scoring)
            best_score = cv_scores.mean()
            best_params = "无超参数"

        results.append(
            {
                "Name": name,
                "Model": model.fit(X, y),
                "Best CV Score": best_score,
                "Best Parameters": best_params,
            }
        )

        if model_directory:
            os.makedirs(model_directory, exist_ok=True)
            with open(os.path.join(model_directory, f"{name}.pkl"), "wb+") as w:
                pickle.dump(results[-1]["Model"], w)

        logger.info(f"{name}: score = {best_score:.4f}")

    # 转为 DataFrame 并排序
    try:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Best CV Score", ascending=False)
        return df_results
    except KeyError:
        logger.error("failed to collect the best params for each model")
        return None


def training(x, y, model_directory: str, n_jobs: int = 1, seed: int = 42):
    df = batch_train_models(
        x,
        y,
        seed=seed,
        n_jobs=n_jobs,
        model_directory=model_directory,
    )
    if df is not None and model_directory is not None:
        df.to_csv(os.path.join(model_directory, "best_params.csv"), index=False)


def testing(output_file: str, df=None, X=None, y=None, n_jobs: int = 1, model_dir=None):
    """running prediction on test dataset"""
    if df is not None:
        test_data, _ = convert_features(df, n_jobs, return_df=True)
    elif X is not None:
        test_data = {"inputs": X, "y": y}

    if model_dir is None:
        model_dir = output_file.replace(".csv", "")

    data = []
    for m in glob(os.path.join(model_dir, "*.pkl")):
        logger.debug(f"running test on model: {m}")
        key = os.path.basename(m).replace(".pkl", "")
        with open(m, "rb") as r:
            model = pickle.load(r)
            predict = model.predict(test_data["inputs"])
            row = [
                {"model": key, "y": x, "predict": y}
                for x, y in zip(test_data["y"], predict)
            ]

            data += row
    df = pd.DataFrame(data)
    logger.info(f"save predict results to: {output_file}")
    df.to_csv(output_file, index=False)


@click.command(
    context_settings=dict(help_option_names=["-h", "--help"]), no_args_is_help=True
)
@click.option(
    "-i", "--input-file", type=click.Path(exists=True), help="Path to input features"
)
@click.option(
    "-t",
    "--test-file",
    type=str,
    help="Path to test features or regex path contains the output files by calFreq",
)
@click.option("-o", "--output-file", type=click.Path(), help="Path to output features")
@click.option("-p", "--n-jobs", type=int, default=1, help="Path to output features")
@click.option("--test-size", type=float, default=0.3, help="The fraction of test size")
@click.option("--seed", type=int, default=10)
@click.option("--verbose", is_flag=True, help="show more detailed logs")
def ml(
    input_file: str,
    test_file: str,
    output_file: str,
    n_jobs: int,
    test_size: float,
    seed: int,
    verbose: bool,
):
    """test prediction effect on multiple machine learning models"""

    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO")
    logger.debug("DEBUG" if verbose else "INFO")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # load input file
    df = pd.read_csv(input_file, sep=None, engine="python")

    # generate feature and caches
    cache = os.path.join(os.path.dirname(output_file), "machine_learning_features.pkl")
    if os.path.exists(cache):
        logger.info(f"restore input features from cached: {cache}")
        with open(cache, "rb") as r:
            data = pickle.load(r)
        data, df = data["data"], data["df"]
    else:
        data, df = convert_features(df, n_jobs, return_df=True)
        with open(cache, "wb+") as w:
            pickle.dump({"data": data, "df": df}, w)

    # generate all cache path
    ext = "." + os.path.basename(output_file).split(".")[-1]
    model_directory = output_file.replace(ext, "").rstrip(".")

    X, y, x_test, y_test = split_data(data, test_size=test_size, random_state=seed)
    training(X, y, model_directory=model_directory, n_jobs=n_jobs, seed=seed)

    logger.info("running testing")
    testing(
        X=x_test,
        y=y_test,
        output_file=output_file.replace(ext, "_internal.csv")
        if test_file is not None
        else output_file,
        n_jobs=n_jobs,
        model_dir=output_file.replace(ext, ""),
    )

    if test_file is not None:
        logger.info("running independant test")
        # test code
        cache = os.path.join(test_file + ".pkl")
        if os.path.exists(cache):
            logger.info(f"restore test features from cached: {cache}")
            with open(cache, "rb") as r:
                data = pickle.load(r)
            data, df = data["data"], data["df"]
        else:
            data, df = convert_features(df, n_jobs, return_df=True)
            with open(cache, "wb+") as w:
                pickle.dump({"data": data, "df": df}, w)
        testing(X=data["inputs"], y=data["y"], output_file=output_file, n_jobs=n_jobs)


@click.command(
    context_settings=dict(help_option_names=["-h", "--help"]), no_args_is_help=True
)
@click.option(
    "-i", "--input-file", type=click.Path(exists=True), help="Path to input features"
)
@click.option(
    "-m", "--model", type=click.Path(exists=True), help="Path to input features"
)
@click.option(
    "-r",
    "--rename",
    type=click.Path(exists=True),
    help="Path to xlsx records the axis tick labels",
)
@click.option("-o", "--output-file", type=click.Path(), help="Path to output pdf")
@click.option("-p", "--n-jobs", type=int, default=1, help="Path to output features")
@click.option("--test-size", type=float, default=0.3, help="The fraction of test size")
@click.option("--seed", type=int, default=10)
def shap(
    input_file: str,
    model: str,
    seed: int,
    test_size: float,
    n_jobs: int,
    output_file: str,
    rename: str,
):
    """calculate SHAP values to score the importance of each feature."""

    # load input file
    df = pd.read_csv(input_file, sep=None, engine="python")

    # generate feature and caches
    cache = os.path.join(os.path.dirname(input_file), "machine_learning_features.pkl")
    if os.path.exists(cache):
        logger.info(f"restore input features from cached: {cache}")
        with open(cache, "rb") as r:
            data = pickle.load(r)
        data, df = data["data"], data["df"]
    else:
        data, df = convert_features(df, n_jobs, return_df=True)
        with open(cache, "wb+") as w:
            pickle.dump({"data": data, "df": df}, w)

    _, _, x_test, _ = split_data(data, test_size=test_size, random_state=seed)

    if rename is not None:
        logger.info("load rename tick labels")
        df = pd.read_excel(rename)
        rename = {}
        for column in df.columns:
            val = df.loc[0, column]

            if val.startswith("Target"):
                val = val.replace("Target_", "Position: ")
                val = val.replace("_", " ")
            elif "count" in val:
                val = f"Number of {val.replace('_count', '')}"
            else:
                val = val.replace("_", " ")
            rename[column] = val

    with open(model, "rb") as r:
        model = pickle.load(r)

    if "LGBMRegressorWithES" in str(model):
        explainer = TreeExplainer(model.model_.booster_)
    else:
        explainer = TreeExplainer(model)
    shap_values = explainer(x_test)

    # 关键设置：禁止将文本转为路径
    plt.rcParams["pdf.fonttype"] = 42  # 使用 TrueType 字体（可编辑）
    plt.rcParams["ps.fonttype"] = 42  # 对 PS 也生效
    # plt.rcParams['font.family'] = 'Arial'  # 或 'Arial', 'Times New Roman' 等标准字体
    plt.switch_backend("agg")

    fig, ax = plt.subplots(figsize=(6, 6))
    ax = plots.beeswarm(shap_values, show=False, max_display=20)

    if rename is not None:
        original_ticks = ax.get_yticklabels()  # 获取当前 y 轴刻度位置
        ax.set_yticklabels(
            [rename.get(x.get_text(), x) for x in original_ticks]
        )  # 设置新标签
    ymin, ymax = ax.get_ylim()
    new_ymin = ymin + 1.5
    ax.set_ylim(new_ymin, ymax)

    plt.savefig(output_file, bbox_inches="tight")


if __name__ == "__main__":
    pass
