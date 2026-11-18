"""RAG Agent for citizen inquiries.

Provides RAG-powered Arabic answers using the knowledge base.
"""

from app.agents.rag_agent.agent import run_rag_agent

__all__ = ["run_rag_agent"]
