"""
RAG 服务
对接外部/内部 RAG 知识库服务，支持混合检索和自动重试
"""
from typing import List, Dict, Any
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from src.config.settings import settings
from src.state.schema import RAGResult
from src.utils.logger import get_logger
from src.utils.metrics import RAG_QUERY_DURATION, RAG_QUERY_ERRORS

logger = get_logger(__name__)


class RAGService:
    def __init__(self):
        self.external_rag_url = settings.external_rag_url
        self.internal_rag_url = settings.internal_rag_url
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def query(self, query: str) -> List[RAGResult]:
        results = []
        
        external_result = self._query_external_rag(query)
        if external_result:
            results.append(external_result)
        
        internal_result = self._query_internal_rag(query)
        if internal_result:
            results.append(internal_result)
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        return results[:3]
    
    def _query_external_rag(self, query: str) -> RAGResult | None:
        start_time = time.time()
        try:
            response = requests.post(
                self.external_rag_url,
                json={"query": query},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            
            RAG_QUERY_DURATION.labels(source="external").observe(time.time() - start_time)
            
            return RAGResult(
                source="external",
                query=query,
                answer=data.get("answer", ""),
                confidence=data.get("confidence", 0.0),
                sources=data.get("sources", []),
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            RAG_QUERY_ERRORS.labels(source="external", error_type=type(e).__name__).inc()
            logger.warn(
                "外部RAG查询失败",
                error=str(e),
                url=self.external_rag_url,
            )
            return None
    
    def _query_internal_rag(self, query: str) -> RAGResult | None:
        start_time = time.time()
        try:
            response = requests.post(
                self.internal_rag_url,
                json={"query": query},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            
            RAG_QUERY_DURATION.labels(source="internal").observe(time.time() - start_time)
            
            return RAGResult(
                source="internal",
                query=query,
                answer=data.get("answer", ""),
                confidence=data.get("confidence", 0.0),
                sources=data.get("sources", []),
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            RAG_QUERY_ERRORS.labels(source="internal", error_type=type(e).__name__).inc()
            logger.warn(
                "内部RAG查询失败",
                error=str(e),
                url=self.internal_rag_url,
            )
            return None