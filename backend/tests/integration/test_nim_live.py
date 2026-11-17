"""OPT-IN live smoke test against the real NVIDIA NIM API.

Skipped automatically unless a real LLM_API_KEY is configured (backend/.env or environment).
Run only these:   pytest -m live -v
It sends three tiny, non-personal prompts. It checks the connection and that the model returns
parseable JSON in the shapes the agent expects. It does NOT measure quality (use run_eval).
"""

import pytest

from app.agents.complaint_agent import tools
from app.agents.complaint_agent.nim_client import build_llm_client
from app.core.config import Settings

_PLACEHOLDERS = {"", "changeme", "your-nvidia-nim-api-key"}
_KEY = Settings().llm_api_key.strip()

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(_KEY.lower() in _PLACEHOLDERS, reason="LLM_API_KEY is not configured"),
]


@pytest.fixture(scope="module")
def llm():
    return build_llm_client()


def test_live_connection_returns_text(llm):
    assert llm.complete("Reply with the single word: pong", "ping").strip() != ""


def test_live_categorize_returns_valid_taxonomy_value_for_arabic(llm):
    category, _ = tools.categorize(llm, "ماسورة المية مكسورة والشارع غرقان", "Water")
    assert category in {"Water", "Electricity", "Roads", "Environment"}


def test_live_severity_returns_valid_structured_answer(llm):
    answer = tools.classify_severity(
        llm, "Live wires are sparking over the playground", "Electricity"
    )
    assert answer.severity in {"Critical", "Medium", "Weak"}
