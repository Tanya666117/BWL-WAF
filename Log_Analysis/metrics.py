# metrics.py
# -*- coding: utf-8 -*-
from AegisSense.metrics import EvaluationMetrics
from typing import List, Tuple
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score

class EvaluationMetrics:
    """评估指标计算工具类"""
    def __init__(self):
        self.tp = 0  # 真阳性：实际攻击，预测攻击
        self.tn = 0  # 真阴性：实际正常，预测正常
        self.fp = 0  # 假阳性：实际正常，预测攻击（误报）
        self.fn = 0  # 假阴性：实际攻击，预测正常（漏报）
        self.y_true = []  # 真实标签列表
        self.y_pred = []  # 预测标签列表

    def update(self, true_label: int, pred_label: int) -> None:
        """更新混淆矩阵计数"""
        self.y_true.append(true_label)
        self.y_pred.append(pred_label)
        if true_label == 1 and pred_label == 1:
            self.tp += 1
        elif true_label == 0 and pred_label == 0:
            self.tn += 1
        elif true_label == 0 and pred_label == 1:
            self.fp += 1
        elif true_label == 1 and pred_label == 0:
            self.fn += 1

    def get_precision(self) -> float:
        """精确率 = TP / (TP + FP)"""
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)

    def get_recall(self) -> float:
        """召回率 = TP / (TP + FN)"""
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)

    def get_f1(self) -> float:
        """F1分数 = 2*(精确率*召回率)/(精确率+召回率)"""
        p = self.get_precision()
        r = self.get_recall()
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    def get_fpr(self) -> float:
        """误报率 = FP / (FP + TN)"""
        if self.fp + self.tn == 0:
            return 0.0
        return self.fp / (self.fp + self.tn)

    def get_ap(self) -> float:
        """平均精度（AP）：基于预测置信度排序的精确率-召回率曲线下面积"""
        # Snort规则匹配无置信度，用0/1标签计算（等价于threshold=0.5的AP）
        return average_precision_score(self.y_true, self.y_pred)

    def print_metrics(self, method_name: str = "Snort规则匹配法") -> None:
        """打印所有指标"""
        print(f"\n{method_name} 评估指标：")
        print(f"精确率（Precision）：{self.get_precision():.4f}")
        print(f"召回率（Recall）：{self.get_recall():.4f}")
        print(f"F1分数（F1-Score）：{self.get_f1():.4f}")
        print(f"平均精度（AP）：{self.get_ap():.4f}")
        print(f"误报率（FPR）：{self.get_fpr():.4f}")