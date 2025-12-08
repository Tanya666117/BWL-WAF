# test_snort_rules.py
# -*- coding: utf-8 -*-
from AegisSense.snort_rules import get_snort_matcher
import json
from typing import Dict

from metrics import EvaluationMetrics
from datasets import load_dataset

def load_labeled_dataset(split: str = "test") -> List[Dict]:
    """加载带真实标签的测试数据集（假设标签字段为'label'，1=攻击，0=正常）"""
    # 若使用自定义数据集，替换为实际路径和加载逻辑
    ds = load_dataset("tiangler/cybersecurity_alarm_analysis")
    # 确保数据集包含'label'字段，若字段名不同需修改
    labeled_data = []
    for item in ds[split]:
        try:
            alert = json.loads(item["input"]) if isinstance(item["input"], str) else item["input"]
            # 假设标签字段为'label'，1表示攻击，0表示正常
            label = item.get("label", 0) if "label" in item else (1 if alert.get("is_attack", False) else 0)
            labeled_data.append({"alert": alert, "label": label})
        except Exception as e:
            print(f"加载数据失败: {e}，跳过该样本")
    return labeled_data

def evaluate_snort_rules():
    """评估Snort规则匹配法的各项指标"""
    # 初始化匹配器和评估器
    matcher = get_snort_matcher()
    metrics = EvaluationMetrics()
    
    # 加载带标签的测试集（建议测试集规模≥1000样本，确保指标可靠）
    print("加载测试数据集...")
    labeled_data = load_labeled_dataset(split="test")
    print(f"测试样本数量: {len(labeled_data)}")
    
    # 遍历样本进行匹配和评估
    for i, data in enumerate(labeled_data):
        alert = data["alert"]
        true_label = data["label"]
        
        # Snort规则匹配：匹配到规则则预测为攻击（1），否则为正常（0）
        matched, _ = matcher.match_alert(alert)
        pred_label = 1 if matched else 0
        
        # 更新指标
        metrics.update(true_label, pred_label)
        
        # 打印进度
        if (i + 1) % 100 == 0:
            print(f"已处理 {i+1}/{len(labeled_data)} 样本")
    
    # 输出最终指标
    metrics.print_metrics()

if __name__ == "__main__":
    evaluate_snort_rules()