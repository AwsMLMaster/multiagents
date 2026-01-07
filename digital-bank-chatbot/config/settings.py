"""
Configuration settings for Digital Bank Chatbot.

Loads configuration from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BedrockSettings:
    """AWS Bedrock configuration."""
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    region: str = "us-east-1"
    max_tokens: int = 4096
    temperature: float = 0.1
    guardrail_id: Optional[str] = None
    guardrail_version: str = "DRAFT"

    @classmethod
    def from_env(cls) -> "BedrockSettings":
        return cls(
            model_id=os.getenv("BEDROCK_MODEL_ID", cls.model_id),
            region=os.getenv("AWS_REGION", cls.region),
            max_tokens=int(os.getenv("BEDROCK_MAX_TOKENS", cls.max_tokens)),
            temperature=float(os.getenv("BEDROCK_TEMPERATURE", cls.temperature)),
            guardrail_id=os.getenv("BEDROCK_GUARDRAIL_ID"),
            guardrail_version=os.getenv("BEDROCK_GUARDRAIL_VERSION", cls.guardrail_version),
        )


@dataclass
class KnowledgeBaseSettings:
    """AWS Bedrock Knowledge Base configuration."""
    knowledge_base_id: str = ""
    region: str = "us-east-1"
    max_results: int = 5
    confidence_threshold: float = 0.5

    @classmethod
    def from_env(cls) -> "KnowledgeBaseSettings":
        return cls(
            knowledge_base_id=os.getenv("KB_ID", ""),
            region=os.getenv("AWS_REGION", cls.region),
            max_results=int(os.getenv("KB_MAX_RESULTS", cls.max_results)),
            confidence_threshold=float(os.getenv("KB_CONFIDENCE_THRESHOLD", cls.confidence_threshold)),
        )


@dataclass
class TCSBancsSettings:
    """TCS Bancs integration configuration."""
    base_url: str = ""
    api_key: str = ""
    api_secret: str = ""
    client_id: str = ""
    timeout: int = 30
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> "TCSBancsSettings":
        return cls(
            base_url=os.getenv("TCS_BANCS_URL", ""),
            api_key=os.getenv("TCS_BANCS_API_KEY", ""),
            api_secret=os.getenv("TCS_BANCS_API_SECRET", ""),
            client_id=os.getenv("TCS_BANCS_CLIENT_ID", ""),
            timeout=int(os.getenv("TCS_BANCS_TIMEOUT", cls.timeout)),
            verify_ssl=os.getenv("TCS_BANCS_VERIFY_SSL", "true").lower() == "true",
        )


@dataclass
class CacheSettings:
    """Cache configuration."""
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    dynamodb_table: str = "chatbot-sessions"
    default_ttl: int = 3600
    session_ttl: int = 1800

    @classmethod
    def from_env(cls) -> "CacheSettings":
        return cls(
            redis_host=os.getenv("REDIS_HOST", cls.redis_host),
            redis_port=int(os.getenv("REDIS_PORT", cls.redis_port)),
            redis_db=int(os.getenv("REDIS_DB", cls.redis_db)),
            redis_password=os.getenv("REDIS_PASSWORD"),
            dynamodb_table=os.getenv("DYNAMODB_SESSION_TABLE", cls.dynamodb_table),
            default_ttl=int(os.getenv("CACHE_DEFAULT_TTL", cls.default_ttl)),
            session_ttl=int(os.getenv("SESSION_TTL", cls.session_ttl)),
        )


@dataclass
class ObservabilitySettings:
    """Observability configuration."""
    service_name: str = "digital-bank-chatbot"
    environment: str = "development"
    otel_endpoint: Optional[str] = None
    otel_enabled: bool = True
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "digital-bank-chatbot"
    langsmith_enabled: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "ObservabilitySettings":
        return cls(
            service_name=os.getenv("SERVICE_NAME", cls.service_name),
            environment=os.getenv("ENVIRONMENT", cls.environment),
            otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            otel_enabled=os.getenv("OTEL_ENABLED", "true").lower() == "true",
            langsmith_api_key=os.getenv("LANGCHAIN_API_KEY"),
            langsmith_project=os.getenv("LANGCHAIN_PROJECT", cls.langsmith_project),
            langsmith_enabled=os.getenv("LANGSMITH_ENABLED", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
        )


@dataclass
class SecuritySettings:
    """Security configuration."""
    max_input_length: int = 2000
    enable_pii_detection: bool = True
    enable_injection_detection: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    mfa_required_amount: float = 1000.0  # ILS

    @classmethod
    def from_env(cls) -> "SecuritySettings":
        return cls(
            max_input_length=int(os.getenv("MAX_INPUT_LENGTH", cls.max_input_length)),
            enable_pii_detection=os.getenv("ENABLE_PII_DETECTION", "true").lower() == "true",
            enable_injection_detection=os.getenv("ENABLE_INJECTION_DETECTION", "true").lower() == "true",
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", cls.rate_limit_requests)),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", cls.rate_limit_window)),
            mfa_required_amount=float(os.getenv("MFA_REQUIRED_AMOUNT", cls.mfa_required_amount)),
        )


@dataclass
class AppSettings:
    """Main application settings."""
    bedrock: BedrockSettings = field(default_factory=BedrockSettings)
    knowledge_base: KnowledgeBaseSettings = field(default_factory=KnowledgeBaseSettings)
    tcs_bancs: TCSBancsSettings = field(default_factory=TCSBancsSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Load all settings from environment variables."""
        return cls(
            bedrock=BedrockSettings.from_env(),
            knowledge_base=KnowledgeBaseSettings.from_env(),
            tcs_bancs=TCSBancsSettings.from_env(),
            cache=CacheSettings.from_env(),
            observability=ObservabilitySettings.from_env(),
            security=SecuritySettings.from_env(),
        )


# Singleton settings instance
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = AppSettings.from_env()
    return _settings


def reload_settings() -> AppSettings:
    """Reload settings from environment."""
    global _settings
    _settings = AppSettings.from_env()
    return _settings
