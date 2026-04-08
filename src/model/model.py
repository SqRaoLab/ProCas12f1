#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI models
"""

import logging

import pytorch_lightning as pl
import torch
import torch.nn.functional as F
from einops import rearrange
from loguru import logger
from torch import nn

import warnings
warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)

# ================
# 全局配置
# ================
torch.set_float32_matmul_precision("medium")  # 如果支持 Tensor Cores

# 🔇 关闭 PyTorch Lightning 所有日志
logging.getLogger("pytorch_lightning").setLevel(logging.WARNING)


# preset sizes for different model
MODEL_SIZES = {"before_pam": [4, 10], "sg": [10, 20], "after": [4, 6], "ind": [31, 1]}


# ================
# 模型定义（保持不变）
# ================


class BiGRU(nn.Module):
    def __init__(self, input_dim, seq_len, linear_dim, hidden_dims, hidden_dropout=0):
        super(BiGRU, self).__init__()
        self.linear = nn.Linear(input_dim, linear_dim)
        self.hidden_layers = nn.ModuleList()
        self.norm_layers = nn.ModuleList()
        self.dropout_layers = nn.ModuleList()
        self.seq_len = seq_len
        for i, hidden_dim in enumerate(hidden_dims):
            input_size = linear_dim if i == 0 else hidden_dims[i - 1] * 2
            self.norm_layers.append(nn.LayerNorm(input_size))
            gru_layer = nn.GRU(
                input_size=input_size,
                hidden_size=hidden_dim,
                batch_first=True,
                bidirectional=True,
            )
            self.hidden_layers.append(gru_layer)
            self.dropout_layers.append(
                nn.Dropout(hidden_dropout if i != len(hidden_dims) - 1 else 0)
            )
            self._init_weights(gru_layer)

    def _init_weights(self, layer):
        for name, param in layer.named_parameters():
            if "weight_ih" in name or "weight_hh" in name:
                nn.init.orthogonal_(param.data)
            elif "bias_ih" in name or "bias_hh" in name:
                nn.init.zeros_(param.data)

    def forward(self, x):
        if x.shape[1] != self.seq_len:
            raise ValueError(f"Expected seq len {self.seq_len}, got {x.shape[1]}")
        x = self.linear(x)
        for hidden_layer, norm_layer, dropout_layer in zip(
            self.hidden_layers, self.norm_layers, self.dropout_layers
        ):
            x = rearrange(x, "b s f -> (b s) f")
            x = norm_layer(x)
            x = rearrange(x, "(b s) f -> b s f", s=self.seq_len)
            x, _ = hidden_layer(x)
            x = dropout_layer(x)
        return x[:, -1:, :]


class FC(nn.Module):
    def __init__(self, input_dim, linear_dims, fc_dropout):
        super(FC, self).__init__()
        if not linear_dims:
            raise ValueError("linear_dims should contain at least one layer dimension.")
        layers = []
        prev_dim = input_dim
        for i, mid_dim in enumerate(linear_dims):
            layers.append(nn.Linear(prev_dim, mid_dim))
            # layers.append(nn.BatchNorm1d(mid_dim))
            if i < len(linear_dims) - 1:
                layers.append(nn.Dropout(fc_dropout))
                layers.append(nn.GELU())
            prev_dim = mid_dim
        self.fc_layers = nn.Sequential(*layers)
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x):
        return self.fc_layers(x)


class Model(pl.LightningModule):
    def __init__(
        self,
        before_pam_linear,
        before_pam_hidden,
        sg_linear,
        sg_hidden,
        after_linear,
        after_hidden,
        ind_hidden,
        fc_hidden,
        fc_dropout,
    ):
        super().__init__()
        self.save_hyperparameters()
        self.before_pam_model = BiGRU(
            *MODEL_SIZES["before_pam"], before_pam_linear, before_pam_hidden
        )
        self.sg_model = BiGRU(*MODEL_SIZES["sg"], sg_linear, sg_hidden)
        self.after_model = BiGRU(*MODEL_SIZES["after"], after_linear, after_hidden)
        self.ind_model = FC(MODEL_SIZES["ind"][0], ind_hidden, 0)
        fc_input_dim = (
            before_pam_hidden[-1] * 2
            + sg_hidden[-1] * 2
            + after_hidden[-1] * 2
            + ind_hidden[-1]
        )
        self.last_fc = FC(fc_input_dim, fc_hidden, fc_dropout)
        self.loss_fn = nn.MSELoss()

        self.optim = "AdamW"
        self.lr = 1e-3

    def forward(self, before_pam, sg, after, ind):
        before_pam = self.before_pam_model(before_pam)
        sg = self.sg_model(sg)
        after = self.after_model(after)
        ind = self.ind_model(ind)
        x = torch.cat([before_pam, sg, after, ind], dim=-1)
        return self.last_fc(x)

    def _calculate_loss(self, batch, mode="train"):
        before_pam, sg, after, ind, y = batch
        y_pred = self(before_pam, sg, after, ind).squeeze()
        loss = self.loss_fn(y_pred, y)

        # 单独计算 Spearman（仅用于 logging）
        # y_pred_np = y_pred.detach().cpu().numpy()
        # y_true_np = y.detach().cpu().numpy()
        # spearman_corr = spearmanr(y_pred_np, y_true_np)

        # self.log(f"{mode}val_spearman", spearman_corr.statistic)
        self.log(f"{mode}_loss", loss, on_epoch=True, prog_bar=True, logger=False)
        return loss

    def training_step(self, batch, batch_idx):
        loss = self._calculate_loss(batch, mode="train")
        torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=1.0)
        return loss

    def validation_step(self, batch, batch_idx):
        return self._calculate_loss(batch, mode="val")

    def configure_optimizers(self):
        logger.debug(f"create optimizers: {self.optim}")
        if self.optim == "AdamW":
            optimizer = torch.optim.AdamW(
                self.parameters(), lr=self.lr, weight_decay=1e-2
            )
        else:
            optimizer = torch.optim.SGD(
                self.parameters(), lr=self.lr, momentum=0.9, weight_decay=1e-4
            )

        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            factor=0.5,
            mode="min",
            patience=10,
            min_lr=1e-6,  # 防止 LR 降到 0
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "monitor": "val_loss"},
        }


if __name__ == "__main__":
    pass
