"""
AWS Bedrock Client for LLM interactions.

This module provides a unified interface to AWS Bedrock for:
- Foundation model inference (Claude)
- Guardrails application
- Streaming responses
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


@dataclass
class BedrockConfig:
    """Configuration for Bedrock client."""
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    region: str = "us-east-1"
    max_tokens: int = 4096
    temperature: float = 0.1
    top_p: float = 0.9
    guardrail_id: Optional[str] = None
    guardrail_version: str = "DRAFT"
    timeout: int = 30
    max_retries: int = 3


@dataclass
class BedrockResponse:
    """Response from Bedrock inference."""
    content: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    latency_ms: int
    guardrail_action: Optional[str] = None
    guardrail_outputs: List[Dict[str, Any]] = field(default_factory=list)


class BedrockClient:
    """
    AWS Bedrock client for LLM inference.

    Supports both synchronous and streaming inference with
    optional guardrails integration.
    """

    def __init__(self, config: Optional[BedrockConfig] = None):
        """
        Initialize the Bedrock client.

        Args:
            config: Optional BedrockConfig, uses defaults if not provided.
        """
        self.config = config or BedrockConfig()

        # Configure boto3 client with retries and timeouts
        boto_config = Config(
            region_name=self.config.region,
            retries={"max_attempts": self.config.max_retries, "mode": "adaptive"},
            connect_timeout=self.config.timeout,
            read_timeout=self.config.timeout * 2,
        )

        self.client = boto3.client("bedrock-runtime", config=boto_config)
        self._runtime_client = None

    @property
    def runtime_client(self):
        """Lazy initialization of runtime client for streaming."""
        if self._runtime_client is None:
            self._runtime_client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.region
            )
        return self._runtime_client

    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Build the request body for Claude model."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        return body

    async def invoke(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> BedrockResponse:
        """
        Invoke the Bedrock model.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            system_prompt: Optional system prompt.
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            BedrockResponse with model output.
        """
        import time
        import asyncio

        start_time = time.time()

        try:
            body = self._build_request_body(messages, system_prompt, **kwargs)

            # Build request parameters
            request_params = {
                "modelId": self.config.model_id,
                "contentType": "application/json",
                "accept": "application/json",
                "body": json.dumps(body),
            }

            # Add guardrail if configured
            if self.config.guardrail_id:
                request_params["guardrailIdentifier"] = self.config.guardrail_id
                request_params["guardrailVersion"] = self.config.guardrail_version

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.invoke_model(**request_params)
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content from Claude response format
            content = ""
            if "content" in response_body:
                for block in response_body["content"]:
                    if block.get("type") == "text":
                        content += block.get("text", "")

            return BedrockResponse(
                content=content,
                input_tokens=response_body.get("usage", {}).get("input_tokens", 0),
                output_tokens=response_body.get("usage", {}).get("output_tokens", 0),
                stop_reason=response_body.get("stop_reason", ""),
                latency_ms=latency_ms,
                guardrail_action=response.get("ResponseMetadata", {}).get(
                    "HTTPHeaders", {}
                ).get("x-amzn-bedrock-guardrail-action"),
            )

        except Exception as e:
            logger.error(f"Bedrock invocation error: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            raise BedrockInvocationError(f"Failed to invoke Bedrock: {e}") from e

    async def invoke_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> BedrockResponse:
        """
        Invoke model with tool definitions.

        Args:
            messages: List of message dicts.
            tools: List of tool definitions.
            system_prompt: Optional system prompt.
            **kwargs: Additional parameters.

        Returns:
            BedrockResponse with potential tool calls.
        """
        import time
        import asyncio

        start_time = time.time()

        try:
            body = self._build_request_body(messages, system_prompt, **kwargs)
            body["tools"] = tools

            request_params = {
                "modelId": self.config.model_id,
                "contentType": "application/json",
                "accept": "application/json",
                "body": json.dumps(body),
            }

            if self.config.guardrail_id:
                request_params["guardrailIdentifier"] = self.config.guardrail_id
                request_params["guardrailVersion"] = self.config.guardrail_version

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.invoke_model(**request_params)
            )

            response_body = json.loads(response["body"].read())
            latency_ms = int((time.time() - start_time) * 1000)

            # Handle tool use in response
            content = ""
            tool_calls = []

            if "content" in response_body:
                for block in response_body["content"]:
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_calls.append(block)

            response_obj = BedrockResponse(
                content=content,
                input_tokens=response_body.get("usage", {}).get("input_tokens", 0),
                output_tokens=response_body.get("usage", {}).get("output_tokens", 0),
                stop_reason=response_body.get("stop_reason", ""),
                latency_ms=latency_ms,
            )

            # Attach tool calls as additional data
            if tool_calls:
                response_obj.guardrail_outputs = tool_calls

            return response_obj

        except Exception as e:
            logger.error(f"Bedrock tool invocation error: {e}")
            raise BedrockInvocationError(f"Failed to invoke Bedrock with tools: {e}") from e

    async def stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream response from Bedrock model.

        Args:
            messages: List of message dicts.
            system_prompt: Optional system prompt.
            **kwargs: Additional parameters.

        Yields:
            Text chunks as they arrive.
        """
        import asyncio

        try:
            body = self._build_request_body(messages, system_prompt, **kwargs)

            request_params = {
                "modelId": self.config.model_id,
                "contentType": "application/json",
                "accept": "application/json",
                "body": json.dumps(body),
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.runtime_client.invoke_model_with_response_stream(
                    **request_params
                )
            )

            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield delta.get("text", "")

        except Exception as e:
            logger.error(f"Bedrock streaming error: {e}")
            raise BedrockInvocationError(f"Failed to stream from Bedrock: {e}") from e


class BedrockInvocationError(Exception):
    """Exception raised when Bedrock invocation fails."""
    pass


# Hebrew-optimized prompts
HEBREW_SYSTEM_PROMPT = """אתה עוזר בנקאי וירטואלי מקצועי ואדיב של בנק דיגיטלי.

הנחיות:
- ענה תמיד בעברית תקנית ומכובדת
- היה קצר ותמציתי אך מלא
- אם אתה לא בטוח במשהו, אמור זאת בבירור
- לעולם אל תמציא מידע על חשבונות או פעולות
- שמור על פרטיות המשתמש ואל תחשוף מידע רגיש
- אם נדרש אימות נוסף, הסבר למשתמש מה נדרש

כללים לפעולות בנקאיות:
- לפני כל פעולה כספית, וודא שהמשתמש מאושר
- הצג תמיד סיכום לפני ביצוע העברה
- אם יש ספק, בקש אישור מפורש
"""


def create_bedrock_client(
    model_id: Optional[str] = None,
    guardrail_id: Optional[str] = None,
    region: Optional[str] = None
) -> BedrockClient:
    """
    Factory function to create a configured Bedrock client.

    Args:
        model_id: Optional model ID override.
        guardrail_id: Optional guardrail ID.
        region: Optional AWS region.

    Returns:
        Configured BedrockClient.
    """
    config = BedrockConfig(
        model_id=model_id or "anthropic.claude-3-5-sonnet-20241022-v2:0",
        guardrail_id=guardrail_id,
        region=region or "us-east-1",
    )
    return BedrockClient(config)
