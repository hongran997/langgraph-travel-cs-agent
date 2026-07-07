"""
Milvus 向量数据库服务
提供长期知识存储、向量相似度检索等功能
"""
from typing import List, Dict, Any
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MilvusService:
    def __init__(self):
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        self.collection_name = settings.milvus_collection_name
        self._connect()
        self._ensure_collection()
    
    def _connect(self):
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port,
                user=settings.milvus_user or None,
                password=settings.milvus_password or None,
            )
            logger.info("milvus_connection_successful", host=self.host, port=self.port)
        except Exception as e:
            logger.error("milvus_connection_failed", error=str(e))
            raise
    
    def _ensure_collection(self):
        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="timestamp", dtype=DataType.INT64),
            ]
            schema = CollectionSchema(fields=fields, description="Travel knowledge base")
            collection = Collection(name=self.collection_name, schema=schema)
            
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            logger.info("milvus_collection_created", collection_name=self.collection_name)
    
    def insert(self, embeddings: List[List[float]], contents: List[str], metadatas: List[Dict[str, Any]]) -> List[int]:
        try:
            collection = Collection(self.collection_name)
            data = [
                embeddings,
                contents,
                metadatas,
                [0] * len(contents),
            ]
            result = collection.insert(data)
            collection.flush()
            logger.info("milvus_insert_success", count=len(contents))
            return result.primary_keys
        except Exception as e:
            logger.error("milvus_insert_failed", error=str(e))
            return []
    
    def search(self, query_embedding: List[float], top_k: int = 5, filter: str = "") -> List[Dict[str, Any]]:
        try:
            collection = Collection(self.collection_name)
            collection.load()
            
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10},
            }
            
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter,
                output_fields=["content", "metadata"],
            )
            
            collection.release()
            
            hits = []
            for hit in results[0]:
                hits.append({
                    "id": hit.id,
                    "distance": hit.distance,
                    "content": hit.entity.get("content", ""),
                    "metadata": hit.entity.get("metadata", {}),
                })
            
            logger.info("milvus_search_success", hit_count=len(hits))
            return hits
        except Exception as e:
            logger.error("milvus_search_failed", error=str(e))
            return []
    
    def query(self, expr: str, output_fields: List[str] = None) -> List[Dict[str, Any]]:
        try:
            collection = Collection(self.collection_name)
            collection.load()
            
            results = collection.query(
                expr=expr,
                output_fields=output_fields or ["content", "metadata"],
            )
            
            collection.release()
            logger.info("milvus_query_success", result_count=len(results))
            return results
        except Exception as e:
            logger.error("milvus_query_failed", error=str(e))
            return []
    
    def delete(self, expr: str) -> int:
        try:
            collection = Collection(self.collection_name)
            result = collection.delete(expr)
            collection.flush()
            logger.info("milvus_delete_success", expr=expr)
            return result.delete_count
        except Exception as e:
            logger.error("milvus_delete_failed", error=str(e))
            return 0