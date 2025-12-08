import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def get_mongo_collection():
    """获取MongoDB集合连接对象（保留原有逻辑）"""
    host = os.getenv("MONGO_HOST", "localhost")
    port = int(os.getenv("MONGO_PORT", 27017))
    db_name = os.getenv("MONGO_DB_NAME", "aegisense_dataset")
    collection_name = os.getenv("MONGO_COLLECTION", "raw_logs")

    try:
        client = MongoClient(
            host=host,
            port=port,
            serverSelectionTimeoutMS=5000
        )
        client.admin.command("ping")
        db = client[db_name]
        collection = db[collection_name]
        
        # 保留原有索引
        collection.create_index("label")          
        collection.create_index("insert_time")    
        collection.create_index("log_hash", unique=True)
        
        print(f"✅ 成功连接MongoDB：{host}:{port}/{db_name}.{collection_name}")
        return collection, host, port, db_name, collection_name  # 新增返回连接信息
    except Exception as e:
        raise RuntimeError(f"❌ MongoDB连接失败：{str(e)}")

def close_mongo_client(collection):
    """关闭MongoDB客户端连接（保留原有逻辑）"""
    try:
        client = collection.database.client
        client.close()
        print("✅ MongoDB连接已关闭")
    except Exception as e:
        print(f"⚠️ 关闭MongoDB连接警告：{str(e)}")

def generate_storage_path(host, port, db_name, collection_name, doc_id):
    """
    生成单条数据的唯一存储路径
    :param host: MongoDB主机
    :param port: MongoDB端口
    :param db_name: 数据库名
    :param collection_name: 集合名
    :param doc_id: 文档唯一ID（ObjectId）
    :return: 唯一存储路径字符串
    """
    # 标准化路径格式（URI规范）
    return f"mongodb://{host}:{port}/{db_name}/{collection_name}/{str(doc_id)}"