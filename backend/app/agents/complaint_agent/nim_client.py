"""NVIDIA NIM implementation of the `LLMClient` protocol (OpenAI-compatible Chat Completions).

This is the ONLY file that knows about the provider. To switch models/providers later,
write another class with `complete(system, user) -> str` and change `build_llm_client`.

Safety rules kept here:
- the API key is never logged, never put in an error message;
- prompts/complaint text are never logged (only exception class and HTTP status);
- no SDK retries (`max_retries=0`): retries with backoff are the Orchestrator's job.
"""

import logging

import openai

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {"", "changeme", "your-nvidia-nim-api-key"}


class LLMConfigError(Exception):
    """Missing/placeholder API key or unsupported provider. Raised when building the client."""


class LLMProviderError(Exception):
    """A provider call failed. `transient` tells the caller whether a retry makes sense
    (timeouts, connection problems, 429, 5xx) or not (bad key, bad request)."""

    def __init__(self, message: str, *, transient: bool, status_code: int | None = None):
        super().__init__(message)
        self.transient = transient
        self.status_code = status_code


class NvidiaNimClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 15.0,
        max_tokens: int = 4096,
        client: openai.OpenAI | None = None,  # injected in tests
    ):
        if client is None:
            if api_key.strip().lower() in _PLACEHOLDER_KEYS:
                raise LLMConfigError("LLM_API_KEY is missing or still a placeholder")
            client = openai.OpenAI(
                api_key=api_key, base_url=base_url, timeout=timeout_seconds, max_retries=0
            )
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        """Return the model's text. Returns "" for an empty answer (the agent treats that as
        a malformed response). Raises LLMProviderError for any provider/network failure."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,  # deterministic classification
                max_tokens=self._max_tokens,
            )
        except openai.APITimeoutError as exc:
            raise self._wrap(exc, transient=True) from None
        except openai.APIConnectionError as exc:
            raise self._wrap(exc, transient=True) from None
        except openai.APIStatusError as exc:
            status = exc.status_code
            raise self._wrap(exc, transient=status == 429 or status >= 500, status=status) from None
        except Exception as exc:  # SDK bug, bad response shape, anything unexpected
            raise self._wrap(exc, transient=False) from None

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            return ""
        return content if isinstance(content, str) else ""

    @staticmethod
    def _wrap(exc: Exception, *, transient: bool, status: int | None = None) -> LLMProviderError:
        # Only the exception class and status code: no message text (could echo request data).
        logger.warning(
            "llm call failed: %s status=%s transient=%s", type(exc).__name__, status, transient
        )
        return LLMProviderError(
            f"NVIDIA NIM call failed ({type(exc).__name__})",
            transient=transient,
            status_code=status,
        )


def build_llm_client(settings: Settings | None = None) -> NvidiaNimClient:
    """Build the client from settings (LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY)."""
    settings = settings or get_settings()
    if settings.llm_provider != "nvidia_nim":
        raise LLMConfigError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")
    return NvidiaNimClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=float(settings.llm_timeout_seconds),
    )
