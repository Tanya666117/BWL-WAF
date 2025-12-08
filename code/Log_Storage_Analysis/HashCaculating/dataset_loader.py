import os
from dotenv import load_dotenv
from datasets import load_dataset

# 加载配置
load_dotenv()

def load_raw_dataset():
    """
    加载原始安全日志数据集
    返回：datasets.Dataset实例（训练集/指定拆分）
    异常：RuntimeError（加载失败时抛出）
    """
    # 从配置读取参数
    dataset_name = os.getenv("DATASET_NAME", "tiangler/cybersecurity_alarm_analysis")
    dataset_split = os.getenv("DATASET_SPLIT", "train")

    try:
        print(f"\n📥 开始加载数据集：{dataset_name}（拆分：{dataset_split}）")
        # 加载数据集（自动缓存到本地）
        ds = load_dataset(dataset_name, split=dataset_split)
        
        # 打印数据集基本信息
        print(f"📊 数据集加载完成：")
        print(f"   - 总条数：{len(ds)}")
        print(f"   - 字段列表：{ds.column_names}")
        print(f"   - 第一条样本预览：{ds[0]}")
        
        return ds
    
    except Exception as e:
        raise RuntimeError(f"❌ 数据集加载失败：{str(e)}")