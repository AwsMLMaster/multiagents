"""
AWS Bedrock Knowledge Base Integration.

This module provides integration with AWS Bedrock Knowledge Base for
retrieval-augmented generation (RAG) capabilities.
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
    AWS Bedrock Knowledge Base client.

    Provides methods for:
    - Direct retrieval (RAG)
    - Retrieve and generate (RAG + LLM)
    - Semantic search
    """

    def __init__(self, config: KnowledgeBaseConfig):
        """
        Initialize the Knowledge Base client.

        Args:
            config: KnowledgeBaseConfig with required settings.
        """
        self.config = config

        # Configure boto3 client
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
        """
        Retrieve relevant documents from Knowledge Base.

        Args:
            query: Search query.
            max_results: Maximum number of results.
            filters: Optional metadata filters.

        Returns:
            List of RetrievalResult objects.
        """
        import asyncio
        import time

        start_time = time.time()

        try:
            retrieval_config = {
                "vectorSearchConfiguration": {
                    "numberOfResults": max_results or self.config.max_results,
                }
            }

            # Add filters if provided
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

                # Filter by confidence threshold
                if score >= self.config.retrieval_confidence_threshold:
                    results.append(RetrievalResult(
                        content=result.get("content", {}).get("text", ""),
                        source=result.get("location", {}).get("s3Location", {}).get("uri", ""),
                        score=score,
                        metadata=result.get("metadata", {})
                    ))

            logger.info(
                f"Knowledge Base retrieval completed in {int((time.time() - start_time) * 1000)}ms, "
                f"found {len(results)} results"
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
        generation_config: Optional[Dict[str, Any]] = None
    ) -> KnowledgeBaseResponse:
        """
        Retrieve documents and generate answer using LLM.

        Args:
            query: User query.
            session_id: Optional session ID for conversation context.
            max_results: Maximum retrieval results.
            generation_config: Optional generation configuration.

        Returns:
            KnowledgeBaseResponse with answer and citations.
        """
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

            # Add session ID for conversation memory
            if session_id:
                request_params["sessionId"] = session_id

            # Add generation config if provided
            if generation_config:
                request_params["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]["generationConfiguration"] = generation_config

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.retrieve_and_generate(**request_params)
            )

            # Parse citations
            citations = []
            for citation in response.get("citations", []):
                for ref in citation.get("retrievedReferences", []):
                    citations.append(RetrievalResult(
                        content=ref.get("content", {}).get("text", ""),
                        source=ref.get("location", {}).get("s3Location", {}).get("uri", ""),
                        score=ref.get("score", 0.0) if "score" in ref else 1.0,
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
        """
        Perform semantic search with optional document type filter.

        Args:
            query: Search query.
            document_type: Optional document type filter (e.g., "faq", "policy", "product").

        Returns:
            List of relevant documents.
        """
        filters = None
        if document_type:
            filters = {
                "equals": {
                    "key": "document_type",
                    "value": document_type
                }
            }

        return await self.retrieve(query, filters=filters)


class KnowledgeBaseError(Exception):
    """Exception raised when Knowledge Base operations fail."""
    pass


# Pre-defined Knowledge Base configurations for different document types
KB_CONFIGS = {
    "general": {
        "description": "General banking knowledge, FAQs, and policies",
        "document_types": ["faq", "policy", "general"],
    },
    "products": {
        "description": "Banking products and services",
        "document_types": ["product", "service", "offering"],
    },
    "procedures": {
        "description": "Banking procedures and how-to guides",
        "document_types": ["procedure", "guide", "how-to"],
    },
}


def create_knowledge_base_client(
    knowledge_base_id: str,
    region: Optional[str] = None
) -> KnowledgeBaseClient:
    """
    Factory function to create a Knowledge Base client.

    Args:
        knowledge_base_id: The Knowledge Base ID.
        region: Optional AWS region.

    Returns:
        Configured KnowledgeBaseClient.
    """
    config = KnowledgeBaseConfig(
        knowledge_base_id=knowledge_base_id,
        region=region or "us-east-1",
    )
    return KnowledgeBaseClient(config)


class MultiKnowledgeBaseClient:
    """
    Client for querying multiple Knowledge Bases.

    Useful when banking knowledge is split across multiple KBs.
    """

    def __init__(self, kb_configs: Dict[str, KnowledgeBaseConfig]):
        """
        Initialize with multiple Knowledge Base configurations.

        Args:
            kb_configs: Dictionary of name -> KnowledgeBaseConfig.
        """
        self.clients = {
            name: KnowledgeBaseClient(config)
            for name, config in kb_configs.items()
        }

    async def query_all(
        self,
        query: str,
        max_results_per_kb: int = 3
    ) -> Dict[str, List[RetrievalResult]]:
        """
        Query all Knowledge Bases in parallel.

        Args:
            query: Search query.
            max_results_per_kb: Max results from each KB.

        Returns:
            Dictionary of KB name -> results.
        """
        import asyncio

        tasks = {
            name: client.retrieve(query, max_results=max_results_per_kb)
            for name, client in self.clients.items()
        }

        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Error querying KB {name}: {e}")
                results[name] = []

        return results

    async def query_best(
        self,
        query: str,
        kb_name: Optional[str] = None
    ) -> KnowledgeBaseResponse:
        """
        Query the best matching Knowledge Base.

        Args:
            query: Search query.
            kb_name: Optional specific KB to query.

        Returns:
            KnowledgeBaseResponse from the best matching KB.
        """
        if kb_name and kb_name in self.clients:
            client = self.clients[kb_name]
        else:
            # Use first client as default (could be enhanced with routing logic)
            client = list(self.clients.values())[0]

        return await client.retrieve_and_generate(query)
