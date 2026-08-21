"""
AWS Bedrock Knowledge Base Integration.

Provides retrieval-augmented generation (RAG) over a real estate glossary,
buying/renting process guides, and FAQ documents.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeBaseConfig:
    """Configuration for Knowledge Base client."""
    knowledge_base_id: str
    region: str = "us-east-1"
    model_arn: str = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
    max_results: int = 5
    retrieval_confidence_threshold: float = 0.5
    timeout: int = 30
    max_retries: int = 3


@dataclass
class RetrievalResult:
    """Single retrieval result from Knowledge Base."""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeBaseResponse:
    """Response from Knowledge Base query."""
    answer: str
    citations: List[RetrievalResult]
    latency_ms: int
    model_response: Optional[str] = None


class KnowledgeBaseClient:
    """
    AWS Bedrock Knowledge Base client for real estate reference content.
    """

    def __init__(self, config: KnowledgeBaseConfig):
        self.config = config

        boto_config = Config(
            region_name=self.config.region,
            retries={"max_attempts": self.config.max_retries, "mode": "adaptive"},
            connect_timeout=self.config.timeout,
            read_timeout=self.config.timeout * 2,
        )

        self.client = boto3.client("bedrock-agent-runtime", config=boto_config)

    async def retrieve(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Retrieve relevant documents from the Knowledge Base."""
        import asyncio
        import time

        start_time = time.time()

        try:
            retrieval_config = {
                "vectorSearchConfiguration": {
                    "numberOfResults": max_results or self.config.max_results,
                }
            }
            if filters:
                retrieval_config["vectorSearchConfiguration"]["filter"] = filters

            request_params = {
                "knowledgeBaseId": self.config.knowledge_base_id,
                "retrievalQuery": {"text": query},
                "retrievalConfiguration": retrieval_config,
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.retrieve(**request_params)
            )

            results = []
            for result in response.get("retrievalResults", []):
                score = result.get("score", 0.0)
                if score >= self.config.retrieval_confidence_threshold:
                    results.append(RetrievalResult(
                        content=result.get("content", {}).get("text", ""),
                        source=result.get("location", {}).get("s3Location", {}).get("uri", ""),
                        score=score,
                        metadata=result.get("metadata", {})
                    ))

            logger.info(
                f"Knowledge Base retrieval completed in "
                f"{int((time.time() - start_time) * 1000)}ms, found {len(results)} results"
            )
            return results

        except Exception as e:
            logger.error(f"Knowledge Base retrieval error: {e}")
            raise KnowledgeBaseError(f"Failed to retrieve from Knowledge Base: {e}") from e

    async def retrieve_and_generate(
        self,
        query: str,
        session_id: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> KnowledgeBaseResponse:
        """Retrieve documents and generate an answer using the LLM."""
        import asyncio
        import time

        start_time = time.time()

        try:
            retrieval_config = {
                "vectorSearchConfiguration": {
                    "numberOfResults": max_results or self.config.max_results,
                }
            }

            request_params = {
                "input": {"text": query},
                "retrieveAndGenerateConfiguration": {
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": self.config.knowledge_base_id,
                        "modelArn": self.config.model_arn,
                        "retrievalConfiguration": retrieval_config,
                    }
                }
            }
            if session_id:
                request_params["sessionId"] = session_id

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.retrieve_and_generate(**request_params)
            )

            citations = []
            for citation in response.get("citations", []):
                for ref in citation.get("retrievedReferences", []):
                    citations.append(RetrievalResult(
                        content=ref.get("content", {}).get("text", ""),
                        source=ref.get("location", {}).get("s3Location", {}).get("uri", ""),
                        score=ref.get("score", 1.0),
                        metadata=ref.get("metadata", {})
                    ))

            latency_ms = int((time.time() - start_time) * 1000)

            return KnowledgeBaseResponse(
                answer=response.get("output", {}).get("text", ""),
                citations=citations,
                latency_ms=latency_ms,
                model_response=response.get("output", {}).get("text", "")
            )

        except Exception as e:
            logger.error(f"Knowledge Base retrieve and generate error: {e}")
            raise KnowledgeBaseError(f"Failed to retrieve and generate: {e}") from e

    async def semantic_search(
        self,
        query: str,
        document_type: Optional[str] = None
    ) -> List[RetrievalResult]:
        """Semantic search with optional document type filter (e.g., 'glossary', 'guide', 'faq')."""
        filters = None
        if document_type:
            filters = {"equals": {"key": "document_type", "value": document_type}}
        return await self.retrieve(query, filters=filters)


class KnowledgeBaseError(Exception):
    """Exception raised when Knowledge Base operations fail."""
    pass


# Pre-defined Knowledge Base document categories
KB_CONFIGS = {
    "glossary": {
        "description": "Real estate terminology and definitions",
        "document_types": ["glossary"],
    },
    "process_guides": {
        "description": "Home buying, selling, and renting process guides",
        "document_types": ["guide", "how-to"],
    },
    "faq": {
        "description": "Frequently asked questions",
        "document_types": ["faq"],
    },
}


def create_knowledge_base_client(
    knowledge_base_id: str,
    region: Optional[str] = None
) -> KnowledgeBaseClient:
    """Factory function to create a Knowledge Base client."""
    config = KnowledgeBaseConfig(
        knowledge_base_id=knowledge_base_id,
        region=region or "us-east-1",
    )
    return KnowledgeBaseClient(config)
