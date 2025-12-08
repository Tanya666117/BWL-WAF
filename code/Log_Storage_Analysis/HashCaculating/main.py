import json
import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm

# 导入修改后的db_utils
from db_utils import get_mongo_collection, close_mongo_client, generate_storage_path
from dataset_loader import load_raw_dataset

load_dotenv()

# 保留原有calculate_log_hash、preprocess_log函数（无修改）
def calculate_log_hash(log_dict: dict) -> str:
    normalized_log = json.dumps(
        log_dict,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':')
    ).encode("utf-8")
    return hashlib.sha256(normalized_log).hexdigest()

def preprocess_log(log_entry: any, label: str) -> dict:
    if isinstance(log_entry, dict):
        log_dict = log_entry
    elif isinstance(log_entry, str):
        try:
            log_dict = json.loads(log_entry)
        except json.JSONDecodeError:
            log_dict = {"raw_log": log_entry}
    else:
        log_dict = {"raw_log": str(log_entry)}
    
    log_hash = calculate_log_hash(log_dict)
    
    return {
        "log_hash": log_hash,          
        "log_data": log_dict,          
        "label": label,                
        "source": os.getenv("DATASET_NAME"),  
        "insert_time": datetime.utcnow()      
        # 存储路径在插入后生成，此处不预设
    }

def batch_insert_to_db(dataset, collection, host, port, db_name, collection_name):
    """升级：插入后补全存储路径"""
    batch_size = int(os.getenv("BATCH_SIZE", 1000))
    total = len(dataset)
    success = 0

    print(f"\n🔄 开始批量插入数据（总条数：{total}，批次大小：{batch_size}）")
    
    for start_idx in tqdm(range(0, total, batch_size), desc="插入进度"):
        end_idx = min(start_idx + batch_size, total)
        batch_data = dataset[start_idx:end_idx]
        
        docs = []
        for log_entry, label in zip(batch_data["input"], batch_data["output"]):
            try:
                doc = preprocess_log(log_entry, label)
                docs.append(doc)
            except Exception as e:
                print(f"\n⚠️ 预处理失败（索引{start_idx + len(docs)}）：{str(e)}")
                continue
        
        if docs:
            try:
                # 插入数据并获取插入的ID
                result = collection.insert_many(docs, ordered=False)
                success += len(result.inserted_ids)
                
                # 为每条插入的文档补全存储路径
                for doc_id in result.inserted_ids:
                    storage_path = generate_storage_path(host, port, db_name, collection_name, doc_id)
                    collection.update_one(
                        {"_id": doc_id},
                        {"$set": {"storage_path": storage_path}}  # 新增存储路径字段
                    )
            except Exception as e:
                print(f"\n⚠️ 批次插入警告（{start_idx}-{end_idx}）：{str(e)}")

    print(f"\n📈 批量插入完成：")
    print(f"   - 总数据条数：{total}")
    print(f"   - 成功插入：{success}")
    print(f"   - 插入失败：{total - success}")
    return success

# 保留verify_db_data、main函数（仅修改main中调用逻辑）
def verify_db_data(collection):
    print("\n🔍 验证数据存储结果：")
    total_count = collection.count_documents({})
    print(f"   - 集合总条数：{total_count}")
    
    sample_docs = list(collection.find().limit(1))
    if sample_docs:
        sample = sample_docs[0]
        sample_str = json.dumps(
            sample,
            ensure_ascii=False,
            indent=2,
            default=str
        )
        if len(sample_str) > 800:
            sample_str = sample_str[:800] + "\n      ...（内容过长，已截断）"
        print(f"   - 样本数据：\n{sample_str}")
    else:
        print("   - 未查询到样本数据")

def main():
    try:
        # 修改：获取连接信息+集合
        collection, host, port, db_name, collection_name = get_mongo_collection()
        
        clear_confirm = input("\n是否清空集合现有数据？(y/N) ").strip().lower()
        if clear_confirm == "y":
            collection.delete_many({})
            print("🗑️ 已清空集合所有数据")
        
        dataset = load_raw_dataset()
        
        # 修改：传入连接信息用于生成路径
        batch_insert_to_db(dataset, collection, host, port, db_name, collection_name)
        
        verify_db_data(collection)
        
    except RuntimeError as e:
        print(f"\n❌ 程序执行失败：{str(e)}")
    finally:
        if 'collection' in locals():
            close_mongo_client(collection)

if __name__ == "__main__":
    print("="*60)
    print("📝 开始执行：原始数据集链下存储流程（含唯一路径生成）")
    print("="*60)
    main()
    print("\n="*60)
    print("🏁 程序执行结束")
    print("="*60)