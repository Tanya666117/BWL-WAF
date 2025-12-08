import json
import numpy as np
import joblib
import os
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_recall_curve,
    average_precision_score,
    precision_recall_fscore_support,
    confusion_matrix
)

# 与其他模块保持一致的常量定义
POS_LABEL = '攻击'
NEG_LABEL = '误报'

# 复用scorer.py中的核心工具函数（保持特征提取逻辑一致）
def to_logit(p: float) -> float:
    """将概率转换为logit（复用训练时的逻辑）"""
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return np.log(p / (1 - p))

def maybe_decode(v):
    """处理字段解码（复用特征构建逻辑）"""
    if v is None:
        return ''
    if isinstance(v, dict):
        parts = []
        for k, val in v.items():
            s = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
            parts.append(f"{k}:{s}")
        return " ".join(parts)
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)

def build_text_feature(a: dict) -> str:
    """构建文本特征（与scorer.py完全一致）"""
    g = a.get
    payload_txt = maybe_decode(g('payload'))
    fields = [
        g('vuln_type', ''), g('attack_type', ''), g('vuln_name', ''), g('rule_desc', ''),
        g('uri', '') or g('url_path', '') or g('h_url', ''),
        f"rsp_status:{g('rsp_status', '')}",
        f"h_method:{g('h_method', '')}",
        f"confidence:{g('confidence', '')}",
        f"hazard_rating:{g('hazard_rating', '')}",
        f"user-agent:{g('user-agent', '') or g('User-Agent', '')}",
        f"rsp_body:{maybe_decode(g('rsp_body'))[:500]}",
        f"req_header:{maybe_decode(g('req_header'))[:500]}",
        f"req_body:{maybe_decode(g('req_body'))[:500]}",
        f"payload:{payload_txt[:800]}",
    ]
    return " ".join([x for x in fields if x])

def rule_flags(a: dict):
    """规则特征（与rule_fusion_train.py一致）"""
    rb = (str(a.get('rsp_body', '')) or '').lower()
    ua = (str(a.get('user-agent', '') or a.get('User-Agent', '')) or '').lower()
    conf = str(a.get('confidence', '')).lower()
    hazard = str(a.get('hazard_rating', '')).lower()
    f_resp = int(any(k in rb for k in ['非法路径', '仅提供public', '未授权', 'access denied', 'forbidden']))
    f_ua = int(any(k in ua for k in ['ivre-masscan', 'sqlmap', 'go-http-client/1.1', 'curl/', 'nmap']))
    f_low = int(any(k in conf for k in ['低', '中', 'low', 'medium']) and any(k in hazard for k in ['低危', 'low']))
    return np.array([f_resp, f_ua, f_low], dtype=np.float32)

def calculate_metrics(y_true, y_pred, scores):
    """计算所有需要的指标"""
    # 精确率、召回率、F1（针对正类“攻击”）
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=[1], average='binary', zero_division=0
    )
    # 平均精度AP
    ap = average_precision_score(y_true, scores)
    # 混淆矩阵计算FPR（误报率 = FP / (FP + TN)）
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) != 0 else 0.0  # 避免除零
    
    return {
        "精确率(Precision)": round(prec, 4),
        "召回率(Recall)": round(rec, 4),
        "F1分数(F1-Score)": round(f1, 4),
        "平均精度(AP)": round(ap, 4),
        "误报率(FPR)": round(fpr, 4),
        "混淆矩阵": {"TP": tp, "FP": fp, "TN": tn, "FN": fn}
    }

def parse_raw(x):
    """将原始数据（可能是字符串或字典）统一解析为字典（与test/quick_eval.py的ensure_dict逻辑一致）"""
    if isinstance(x, str):
        try:
            return json.loads(x)  # 尝试解析JSON字符串
        except json.JSONDecodeError:
            return {}  # 解析失败返回空字典
    elif isinstance(x, dict):
        return x  # 已为字典直接返回
    else:
        return {}  # 其他类型返回空字典

def get_best_threshold(scores, y_true):
    """获取F1最优阈值（与bench.py和rule_fusion_train.py逻辑一致）"""
    prec, rec, ths = precision_recall_curve(y_true, scores)
    if len(ths) == 0:
        return 0.5  # 数据异常时的默认阈值
    F1 = 2 * prec[:-1] * rec[:-1] / (prec[:-1] + rec[:-1] + 1e-12)
    return float(ths[np.nanargmax(F1)])  # F1最优阈值

def main():
    # 1. 加载数据集并划分测试集（与bench.py和rule_fusion_train.py保持一致）
    print("加载数据集...")
    ds = load_dataset("tiangler/cybersecurity_alarm_analysis")
    raw_data = ds['train']['input']
    labels = np.array(ds['train']['output'])
    
    # 构建文本特征（先解析raw_data为字典）
    texts = [build_text_feature(parse_raw(x)) for x in raw_data]
    
    # 修复：train_test_split返回6个值（3个输入数组→每个拆分为train/test）
    X_tr, X_te, y_tr, y_te, raw_tr, raw_te = train_test_split(
        texts, labels, raw_data,
        test_size=0.2, stratify=labels, random_state=42
    )
    y_true = (y_te == POS_LABEL).astype(int)  # 转换为0-1标签（1为“攻击”，0为“误报”）

    # 2. 加载模型（基模型+融合器，与offline_calibrate_threshold.py逻辑一致）
    print("加载模型...")
    try:
        vec = joblib.load('tfidf_vec.pkl')
        clf = joblib.load('logreg_model.pkl')
        # 尝试加载融合器（可选）
        try:
            fuser = joblib.load('rule_fuser.pkl')
        except Exception:
            fuser = None
            print("未找到融合器模型，仅评估基模型")
        # 读取融合器配置（判断是否使用logit）
        use_logit = False
        meta_path = 'fuser_metrics.json'
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            use_logit = meta.get('args', {}).get('use_logit', False)
    except Exception as e:
        print(f"模型加载失败: {e}")
        return

    # 3. 生成预测分数（基模型+融合模型）
    print("生成预测分数...")
    pos_idx = list(clf.classes_).index(POS_LABEL)
    
    # 基模型分数
    X_te_vec = vec.transform(X_te)
    base_scores = clf.predict_proba(X_te_vec)[:, pos_idx]  # 基模型对“攻击”的概率
    
    # 融合模型分数（基模型+规则特征，若融合器存在）
    fuse_scores = None
    if fuser is not None:
        fuse_scores = []
        for text, raw in zip(X_te, raw_te):
            a = parse_raw(raw)
            # 基模型特征
            x_vec = vec.transform([text])
            base_prob = float(clf.predict_proba(x_vec)[:, pos_idx][0])
            # 规则特征
            feat0 = to_logit(base_prob) if use_logit else base_prob
            feats = np.array([[feat0, *rule_flags(a)]], dtype=np.float32)
            # 融合分数
            fuse_prob = float(fuser.predict_proba(feats)[:, 1][0])
            fuse_scores.append(fuse_prob)
        fuse_scores = np.array(fuse_scores)

    # 4. 确定阈值（使用F1最优阈值）
    base_th = get_best_threshold(base_scores, y_true) if len(base_scores) > 0 else 0.5
    fuse_th = get_best_threshold(fuse_scores, y_true) if (fuse_scores is not None and len(fuse_scores) > 0) else 0.5

    # 5. 生成预测标签（基于最优阈值）
    base_pred = (base_scores >= base_th).astype(int)
    fuse_pred = (fuse_scores >= fuse_th).astype(int) if fuse_scores is not None else None

    # 6. 计算并输出指标
    print("\n===== 基模型（TF-IDF + LR）指标 =====")
    base_metrics = calculate_metrics(y_true, base_pred, base_scores)
    for k, v in base_metrics.items():
        print(f"{k}: {v}")

    if fuse_scores is not None:
        print("\n===== 融合模型（基模型 + 规则）指标 =====")
        fuse_metrics = calculate_metrics(y_true, fuse_pred, fuse_scores)
        for k, v in fuse_metrics.items():
            print(f"{k}: {v}")

if __name__ == "__main__":
    main()