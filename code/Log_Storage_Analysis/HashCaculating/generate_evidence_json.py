import json
import os
from dotenv import load_dotenv
from db_utils import get_mongo_collection, close_mongo_client

# 复用之前的路径+哈希获取逻辑
def get_path_and_hash(collection, sample_size=5):
    """获取指定数量的「存储路径+哈希」数据"""
    all_doc_ids = [doc["_id"] for doc in collection.find({}, {"_id": 1})]
    total = len(all_doc_ids)
    if total == 0:
        raise RuntimeError("❌ 数据库中无数据，请先执行main.py插入数据")
    
    sample_size = min(sample_size, total)
    # 取前N条（或随机，这里用前N条更稳定）
    sample_ids = all_doc_ids[:sample_size]
    
    result = []
    for doc_id in sample_ids:
        doc = collection.find_one({"_id": doc_id})
        if not doc:
            continue
        
        # 生成存储路径（优先用入库时的，无则动态生成）
        storage_path = doc.get("storage_path") or f"mongodb://{os.getenv('MONGO_HOST', 'localhost')}:{os.getenv('MONGO_PORT', '27017')}/{os.getenv('MONGO_DB_NAME', 'aegisense_dataset')}/{os.getenv('MONGO_COLLECTION', 'raw_logs')}/{str(doc_id)}"
        
        result.append({
            "storage_path": storage_path,  # 链下存储路径
            "log_hash": doc["log_hash"],    # 日志哈希值
            "doc_id": str(doc_id)           # 文档ID（溯源用）
        })
    return result

def generate_json(output_dir="output", filename="evidence_data.json"):
    """生成长安链存证用的JSON文件"""
    # 1. 加载配置+连接数据库
    load_dotenv()
    collection, _, _, _, _ = get_mongo_collection()
    
    try:
        # 2. 获取5条存证数据（可修改sample_size调整数量）
        evidence_data = get_path_and_hash(collection, sample_size=5)
        
        # 3. 创建输出目录（不存在则自动创建）
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        
        # 4. 写入JSON文件（UTF-8编码，确保兼容性）
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 存证JSON文件已生成：{output_path}")
        print(f"📄 包含 {len(evidence_data)} 条数据（存储路径+哈希值）")
        
    except Exception as e:
        print(f"❌ 生成JSON失败：{str(e)}")
    finally:
        # 5. 关闭数据库连接
        close_mongo_client(collection)

if __name__ == "__main__":
    print("="*60)
    print("📝 开始生成长安链存证用的evidence_data.json")
    print("="*60)
    generate_json()
    print("\n🏁 生成完成（可将output/evidence_data.json共享给Ubuntu虚拟机）")