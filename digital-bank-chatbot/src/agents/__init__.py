"""
Agent implementations for Digital Bank Chatbot.

Each agent handles a specific domain:
- RAGAgent: General knowledge and FAQ
- AccountAgent: Account information
- TransactionAgent: Financial operations
- LoanAgent: Loan management
- SupportAgent: Customer support
- AnalyticsAgent: Financial insights
"""

from .base_agent import (
    BaseAgent,
    AgentConfig,
    AgentResponse,
    AGENT_SYSTEM_PROMPTS,
)

from .rag_agent import RAGAgent

# Placeholder imports for other agents
# These would be implemented similarly to RAGAgent

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentResponse",
    "AGENT_SYSTEM_PROMPTS",
    "RAGAgent",
]


# Agent factory for dynamic agent creation
def create_agent(agent_type: str, **kwargs):
    """
    Factory function to create agents.

    Args:
        agent_type: Type of agent to create.
        **kwargs: Agent-specific configuration.

    Returns:
        Configured agent instance.
    """
    agents = {
        "rag_agent": RAGAgent,
        # Add other agents as they are implemented
    }

    agent_class = agents.get(agent_type)
    if agent_class is None:
        raise ValueError(f"Unknown agent type: {agent_type}")

    return agent_class(**kwargs)
