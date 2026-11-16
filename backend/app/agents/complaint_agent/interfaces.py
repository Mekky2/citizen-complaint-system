"""The two seams between the Complaint Agent and the outside world.

Both are plain Protocols: any object with the right method works, no inheritance needed.
The RAG teammate implements `RagRetriever`; whoever wires the LLM provider implements `LLMClient`.
"""

from typing import Protocol

from app.agents.complaint_agent.schemas import RagChunk


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the model's raw text answer. Raise any exception on provider failure.
        Timeouts and transient retries are the Orchestrator's job, not the agent's."""
        ...


class RagRetriever(Protocol):
    def retrieve(self, query: str, category: str, top_k: int = 5) -> list[RagChunk]:
        """Return the most relevant legal/regulatory passages, best first.

        - `query`: the complaint description (already free of citizen PII).
        - `category`: one of CATEGORIES, so the retriever can filter its knowledge base.
        - Return [] when nothing relevant is found (do NOT raise).
        - Raise only for real failures (database down, embedding error, ...).
        - Every item needs a non-empty `source` and `excerpt`, taken from the stored document.
        """
        ...
