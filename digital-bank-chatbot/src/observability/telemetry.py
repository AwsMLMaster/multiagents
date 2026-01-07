"""
Observability Layer for Digital Bank Chatbot.

Provides:
- OpenTelemetry distributed tracing
- LangSmith LLM tracing
- Metrics collection
- Structured logging
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic decorator
F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class TelemetryConfig:
    """Configuration for telemetry."""
    service_name: str = "digital-bank-chatbot"
    environment: str = "development"
    otel_endpoint: Optional[str] = None
    otel_enabled: bool = True
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "digital-bank-chatbot"
    langsmith_enabled: bool = True
    cloudwatch_enabled: bool = True
    log_level: str = "INFO"


@dataclass
class SpanContext:
    """Context for a trace span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "OK"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)


class OpenTelemetryTracer:
    """
    OpenTelemetry-based distributed tracing.
    """

    def __init__(self, config: TelemetryConfig):
        """Initialize OTel tracer."""
        self.config = config
        self._tracer = None
        self._meter = None
        self._initialized = False

    def initialize(self):
        """Initialize OpenTelemetry SDK."""
        if self._initialized or not self.config.otel_enabled:
            return

        try:
            from opentelemetry import trace, metrics
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.metrics import MeterProvider

            # Create resource
            resource = Resource.create({
                "service.name": self.config.service_name,
                "deployment.environment": self.config.environment,
            })

            # Set up tracer
            tracer_provider = TracerProvider(resource=resource)

            # Add OTLP exporter if endpoint configured
            if self.config.otel_endpoint:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                otlp_exporter = OTLPSpanExporter(endpoint=self.config.otel_endpoint)
                tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

            trace.set_tracer_provider(tracer_provider)
            self._tracer = trace.get_tracer(self.config.service_name)

            # Set up meter
            meter_provider = MeterProvider(resource=resource)
            metrics.set_meter_provider(meter_provider)
            self._meter = metrics.get_meter(self.config.service_name)

            self._initialized = True
            logger.info("OpenTelemetry initialized successfully")

        except ImportError:
            logger.warning("OpenTelemetry packages not available")
            self._tracer = MockTracer()

    @property
    def tracer(self):
        """Get tracer instance."""
        if not self._initialized:
            self.initialize()
        return self._tracer or MockTracer()

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Start a new span.

        Args:
            name: Span name.
            attributes: Optional span attributes.

        Yields:
            Span context.
        """
        if self._tracer is None:
            self.initialize()

        try:
            from opentelemetry import trace
            with self.tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                yield span
        except Exception:
            # Fallback for mock tracer
            yield MockSpan(name, attributes)

    def record_exception(self, exception: Exception, span=None):
        """Record an exception on current or provided span."""
        try:
            if span:
                span.record_exception(exception)
            else:
                from opentelemetry import trace
                current_span = trace.get_current_span()
                if current_span:
                    current_span.record_exception(exception)
        except Exception as e:
            logger.warning(f"Failed to record exception: {e}")


class MockTracer:
    """Mock tracer for when OTel is not available."""

    def start_as_current_span(self, name: str):
        return MockSpanContext(name)


class MockSpanContext:
    """Mock span context manager."""

    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        return MockSpan(self.name, {})

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockSpan:
    """Mock span for when OTel is not available."""

    def __init__(self, name: str, attributes: Optional[Dict] = None):
        self.name = name
        self.attributes = attributes or {}

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict] = None):
        pass

    def record_exception(self, exception: Exception):
        pass


class LangSmithTracer:
    """
    LangSmith-based LLM tracing.
    """

    def __init__(self, config: TelemetryConfig):
        """Initialize LangSmith tracer."""
        self.config = config
        self._client = None
        self._initialized = False

    def initialize(self):
        """Initialize LangSmith client."""
        if self._initialized or not self.config.langsmith_enabled:
            return

        try:
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = self.config.langsmith_project

            if self.config.langsmith_api_key:
                os.environ["LANGCHAIN_API_KEY"] = self.config.langsmith_api_key

            from langsmith import Client
            self._client = Client()
            self._initialized = True
            logger.info("LangSmith initialized successfully")

        except ImportError:
            logger.warning("LangSmith packages not available")

    @property
    def client(self):
        """Get LangSmith client."""
        if not self._initialized:
            self.initialize()
        return self._client

    def trace_llm_call(
        self,
        model: str,
        messages: List[Dict],
        response: str,
        latency_ms: int,
        tokens_in: int,
        tokens_out: int,
        metadata: Optional[Dict] = None
    ):
        """
        Trace an LLM call.

        Args:
            model: Model identifier.
            messages: Input messages.
            response: Model response.
            latency_ms: Call latency.
            tokens_in: Input tokens.
            tokens_out: Output tokens.
            metadata: Additional metadata.
        """
        if not self.client:
            return

        try:
            # LangSmith auto-traces via LangChain callbacks
            # This is for explicit tracing if needed
            logger.debug(
                f"LLM call traced: {model}, "
                f"latency={latency_ms}ms, "
                f"tokens_in={tokens_in}, "
                f"tokens_out={tokens_out}"
            )
        except Exception as e:
            logger.warning(f"Failed to trace LLM call: {e}")


class MetricsCollector:
    """
    Metrics collection for monitoring.
    """

    def __init__(self, config: TelemetryConfig):
        """Initialize metrics collector."""
        self.config = config
        self._counters: Dict[str, int] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}
        self._cloudwatch_client = None

    @property
    def cloudwatch(self):
        """Lazy initialization of CloudWatch client."""
        if self._cloudwatch_client is None and self.config.cloudwatch_enabled:
            try:
                import boto3
                self._cloudwatch_client = boto3.client('cloudwatch')
            except Exception as e:
                logger.warning(f"CloudWatch client not available: {e}")
        return self._cloudwatch_client

    def increment(self, name: str, value: int = 1, tags: Optional[Dict] = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def record_latency(
        self,
        name: str,
        latency_ms: float,
        tags: Optional[Dict] = None
    ):
        """Record a latency measurement."""
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(latency_ms)

        # Publish to CloudWatch if available
        self._publish_cloudwatch_metric(name, latency_ms, "Milliseconds", tags)

    def set_gauge(self, name: str, value: float, tags: Optional[Dict] = None):
        """Set a gauge metric."""
        key = self._make_key(name, tags)
        self._gauges[key] = value

    def _make_key(self, name: str, tags: Optional[Dict]) -> str:
        """Create unique key from name and tags."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}:{tag_str}"

    def _publish_cloudwatch_metric(
        self,
        name: str,
        value: float,
        unit: str,
        tags: Optional[Dict] = None
    ):
        """Publish metric to CloudWatch."""
        if not self.cloudwatch:
            return

        try:
            dimensions = [
                {"Name": "Service", "Value": self.config.service_name},
                {"Name": "Environment", "Value": self.config.environment},
            ]

            if tags:
                dimensions.extend([
                    {"Name": k, "Value": str(v)} for k, v in tags.items()
                ])

            self.cloudwatch.put_metric_data(
                Namespace="DigitalBankChatbot",
                MetricData=[{
                    "MetricName": name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": dimensions
                }]
            )
        except Exception as e:
            logger.warning(f"Failed to publish CloudWatch metric: {e}")

    def get_percentile(
        self,
        name: str,
        percentile: float,
        tags: Optional[Dict] = None
    ) -> Optional[float]:
        """Get percentile value for a histogram."""
        key = self._make_key(name, tags)
        values = self._histograms.get(key, [])

        if not values:
            return None

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


class Telemetry:
    """
    Unified telemetry interface combining all observability components.
    """

    _instance = None

    def __init__(self, config: Optional[TelemetryConfig] = None):
        """Initialize telemetry system."""
        self.config = config or TelemetryConfig()
        self.otel = OpenTelemetryTracer(self.config)
        self.langsmith = LangSmithTracer(self.config)
        self.metrics = MetricsCollector(self.config)
        self._setup_logging()

    @classmethod
    def get_instance(cls, config: Optional[TelemetryConfig] = None) -> "Telemetry":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    def _setup_logging(self):
        """Configure structured logging."""
        log_format = (
            '{"timestamp": "%(asctime)s", '
            '"level": "%(levelname)s", '
            '"logger": "%(name)s", '
            '"message": "%(message)s", '
            '"service": "' + self.config.service_name + '"}'
        )
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format=log_format
        )

    def initialize(self):
        """Initialize all telemetry components."""
        self.otel.initialize()
        self.langsmith.initialize()
        logger.info("Telemetry system initialized")

    @contextmanager
    def trace_request(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """
        Trace an incoming request.

        Args:
            request_id: Unique request identifier.
            user_id: Optional user ID.
            session_id: Optional session ID.

        Yields:
            Request context for adding events/attributes.
        """
        start_time = time.time()

        attributes = {
            "request.id": request_id,
            "user.id": user_id or "anonymous",
            "session.id": session_id or "none",
        }

        with self.otel.start_span("request", attributes) as span:
            self.metrics.increment("requests_total")

            try:
                yield span

                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency("request_latency", latency_ms)
                span.set_attribute("latency_ms", latency_ms)

            except Exception as e:
                self.metrics.increment("requests_error")
                self.otel.record_exception(e, span)
                raise

    @contextmanager
    def trace_llm_call(self, model: str, operation: str = "invoke"):
        """
        Trace an LLM call.

        Args:
            model: Model identifier.
            operation: Operation type (invoke, stream, etc.)

        Yields:
            LLM call context.
        """
        start_time = time.time()

        with self.otel.start_span(
            f"llm.{operation}",
            {"llm.model": model}
        ) as span:
            self.metrics.increment("llm_calls_total", tags={"model": model})

            try:
                yield span

                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(
                    "llm_latency",
                    latency_ms,
                    tags={"model": model}
                )

            except Exception as e:
                self.metrics.increment(
                    "llm_calls_error",
                    tags={"model": model}
                )
                self.otel.record_exception(e, span)
                raise

    @contextmanager
    def trace_agent(self, agent_name: str):
        """
        Trace an agent execution.

        Args:
            agent_name: Name of the agent.

        Yields:
            Agent execution context.
        """
        start_time = time.time()

        with self.otel.start_span(
            f"agent.{agent_name}",
            {"agent.name": agent_name}
        ) as span:
            self.metrics.increment(
                "agent_executions_total",
                tags={"agent": agent_name}
            )

            try:
                yield span

                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(
                    "agent_latency",
                    latency_ms,
                    tags={"agent": agent_name}
                )

            except Exception as e:
                self.metrics.increment(
                    "agent_executions_error",
                    tags={"agent": agent_name}
                )
                self.otel.record_exception(e, span)
                raise

    @contextmanager
    def trace_tool(self, tool_name: str):
        """
        Trace a tool execution.

        Args:
            tool_name: Name of the tool.

        Yields:
            Tool execution context.
        """
        start_time = time.time()

        with self.otel.start_span(
            f"tool.{tool_name}",
            {"tool.name": tool_name}
        ) as span:
            try:
                yield span

                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(
                    "tool_latency",
                    latency_ms,
                    tags={"tool": tool_name}
                )

            except Exception as e:
                self.otel.record_exception(e, span)
                raise


def traced(span_name: Optional[str] = None):
    """
    Decorator to trace function execution.

    Args:
        span_name: Optional span name (defaults to function name).

    Returns:
        Decorated function.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            telemetry = Telemetry.get_instance()
            name = span_name or func.__name__

            with telemetry.otel.start_span(name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            telemetry = Telemetry.get_instance()
            name = span_name or func.__name__

            with telemetry.otel.start_span(name):
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global telemetry instance
def get_telemetry(config: Optional[TelemetryConfig] = None) -> Telemetry:
    """Get the global telemetry instance."""
    return Telemetry.get_instance(config)
