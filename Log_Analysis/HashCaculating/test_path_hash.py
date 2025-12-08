import json
import os
from dotenv import load_dotenv
from tqdm import tqdm  # 进度条显示
from db_utils import get_mongo_collection, close_mongo_client

def get_all_path_and_hash(collection, batch_size=1000):
    """
    分批读取数据库中**所有数据**的「存储路径+哈希值」
    :param collection: MongoDB集合对象
    :param batch_size: 每批处理的数据量（避免大内存占用）
    :return: 全量数据列表
    """
    total_count = collection.count_documents({})
    if total_count == 0:
        raise RuntimeError("❌ 数据库中无数据，请先执行main.py插入全量数据")
    
    print(f"📊 开始读取全量数据（共 {total_count} 条，每批处理 {batch_size} 条）")
    all_evidence = []
    
    # 分批查询（用游标+skip/limit避免一次性加载全量数据）
    for skip in tqdm(range(0, total_count, batch_size), desc="读取进度"):
        # 每批查询batch_size条数据
        batch_docs = collection.find().skip(skip).limit(batch_size)
        
        for doc in batch_docs:
            # 生成存储路径（优先用入库时的，无则动态生成）
            storage_path = doc.get("storage_path") or (
                f"mongodb://{os.getenv('MONGO_HOST', 'localhost')}:{os.getenv('MONGO_PORT', '27017')}/"
                f"{os.getenv('MONGO_DB_NAME', 'aegisense_dataset')}/{os.getenv('MONGO_COLLECTION', 'raw_logs')}/"
                f"{str(doc['_id'])}"
            )
            
            all_evidence.append({
                "storage_path": storage_path,  # 链下存储路径（唯一）
                "log_hash": doc["log_hash"],    # 日志SHA-256哈希（存证核心）
                "doc_id": str(doc["_id"])       # 文档ID（链下溯源用）
            })
    
    print(f"✅ 全量数据读取完成，共 {len(all_evidence)} 条")
    return all_evidence

def generate_full_evidence_json(output_dir="output", filename="evidence_full_data.json"):
    """生成长安链存证用的**全量数据**JSON文件"""
    # 1. 加载配置+连接数据库
    load_dotenv()
    collection, _, _, _, _ = get_mongo_collection()
    
    try:
        # 2. 获取所有数据的「路径+哈希」
        full_evidence_data = get_all_path_and_hash(collection)
        
        # 3. 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        
        # 4. 写入全量JSON（UTF-8编码，确保跨系统兼容性）
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(full_evidence_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 全量存证JSON已生成：{output_path}")
        print(f"📄 文件大小：{os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
        
    except Exception as e:
        print(f"\n❌ 生成全量JSON失败：{str(e)}")
    finally:
        # 5. 关闭数据库连接
        close_mongo_client(collection)

if __name__ == "__main__":
    print("="*60)
    print("📝 开始生成长安链存证用的全量数据JSON")
    print("="*60)
    generate_full_evidence_json()
    print("\n🏁 生成完成（将output/evidence_full_data.json同步到Ubuntu虚拟机即可）")