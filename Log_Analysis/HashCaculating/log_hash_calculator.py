import json
import hashlib
import numpy as np
from datasets import load_dataset

def calculate_log_hash(log_data: dict) -> str:
    """
    计算日志数据的SHA-256哈希值
    确保字典键值排序序一致，避免因字段顺序序导致哈希差异
    """
    # 将字典转换为排序的JSON字符串（去除空格以保证唯一性）
    normalized_log = json.dumps(
        log_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':')  # 紧凑格式，无额外空格
    ).encode('utf-8')
    
    # 计算SHA-256哈希
    return hashlib.sha256(normalized_log).hexdigest()

def load_and_sample_dataset(dataset_name: str = "tiangler/cybersecurity_alarm_analysis", sample_size: int = 5) -> list:
    """加载数据集并随机抽取样本"""
    try:
        print(f"正在加载数据集: {dataset_name}...")
        dataset = load_dataset(dataset_name)
        # 取训练集的日志数据（根据实际数据集结构调整字段名）
        logs = dataset['train']['input']
        total_count = len(logs)
        print(f"数据集加载完成，共包含 {total_count} 条日志记录")
        
        # 确保抽样数量不超过数据集大小
        sample_size = min(sample_size, total_count)
        # 固定随机种子，保证结果可复现
        np.random.seed(42)
        sample_indices = np.random.choice(total_count, size=sample_size, replace=False)
        return [logs[i] for i in sample_indices]
        
    except Exception as e:
        print(f"数据集加载失败: {str(e)}")
        return []

def parse_log(log_entry) -> dict:
    """解析日志条目为字典（兼容字符串和字典格式）"""
    if isinstance(log_entry, dict):
        return log_entry
    elif isinstance(log_entry, str):
        try:
            return json.loads(log_entry)
        except json.JSONDecodeError:
            # 处理非JSON格式的字符串日志
            return {"raw_log": log_entry}
    else:
        return {"raw_log": str(log_entry)}

def display_results(sampled_logs: list):
    """展示抽样日志及其哈希值"""
    if not sampled_logs:
        print("没有可用的日志样本")
        return
    
    print("\n" + "="*50)
    print(f"随机抽取 {len(sampled_logs)} 条日志的哈希计算结果")
    print("="*50 + "\n")
    
    for i, log_entry in enumerate(sampled_logs, 1):
        try:
            log_dict = parse_log(log_entry)
            log_hash = calculate_log_hash(log_dict)
            
            # 提取关键信息用于展示（根据实际日志结构调整字段）
            key_info = {
                "日志类型": log_dict.get("vuln_type", "未知"),
                "请求路径": log_dict.get("uri", log_dict.get("url_path", "未知"))[:60] + "..." if log_dict.get("uri") or log_dict.get("url_path") else "未知",
                "原始格式": type(log_entry).__name__
            }
            
            print(f"样本 {i}:")
            print(f"  关键信息: {key_info}")
            print(f"  SHA-256哈希: {log_hash}")
            print("-"*80)
            
        except Exception as e:
            print(f"样本 {i} 处理失败: {str(e)}")
            print("-"*80)

if __name__ == "__main__":
    # 配置参数
    DATASET_NAME = "tiangler/cybersecurity_alarm_analysis"  # 公开安全日志数据集
    SAMPLE_SIZE = 5  # 抽取样本数量
    
    # 执行流程
    sampled_logs = load_and_sample_dataset(DATASET_NAME, SAMPLE_SIZE)
    display_results(sampled_logs)