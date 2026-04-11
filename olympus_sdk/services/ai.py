"""AI inference, agent orchestration, embeddings, and NLP.

Wraps the Olympus AI Gateway (Python) via the Go API Gateway.
Routes: ``/ai/*``, ``/agent/*``, ``/translation/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from olympus_sdk.models.ai import (
    AgentResult,
    AgentTask,
    AiResponse,
    Classification,
    SentimentResult,
)
from olympus_sdk.models.common import SearchResult

if TYPE_CHECKING:
    from collections.abc import Iterator

    from olympus_sdk.http import OlympusHttpClient


class AiService:
    """AI inference, agent orchestration, embeddings, and NLP."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Chat / Completion
    # ------------------------------------------------------------------

    def query(
        self,
        prompt: str,
        *,
        tier: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AiResponse:
        """Send a single-turn prompt to the AI gateway.

        ``tier`` selects the model tier (T1-T6). Defaults to server-selected.
        """
        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
        }
        if tier is not None:
            payload["tier"] = tier
        if context is not None:
            payload["context"] = context
        data = self._http.post("/ai/chat", json=payload)
        return AiResponse.from_dict(data)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
    ) -> AiResponse:
        """Multi-turn chat completion.

        ``messages`` is a list of ``{"role": ..., "content": ...}`` dicts
        following the OpenAI-compatible format.
        """
        payload: dict[str, Any] = {"messages": messages}
        if model is not None:
            payload["model"] = model
        data = self._http.post("/ai/chat", json=payload)
        return AiResponse.from_dict(data)

    def stream(self, prompt: str) -> Iterator[str]:
        """Stream a prompt response chunk-by-chunk via SSE.

        Yields content delta strings as they arrive from the server.
        """
        import json as json_mod

        response = self._http.stream_post(
            "/ai/chat",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
        )
        try:
            for line in response.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    payload_str = line[6:]
                    try:
                        parsed = json_mod.loads(payload_str)
                        content = ""
                        choices = parsed.get("choices")
                        if choices and len(choices) > 0:
                            delta = choices[0].get("delta") or {}
                            content = delta.get("content", "")
                        if not content:
                            content = parsed.get("content", "")
                        if content:
                            yield content
                    except (ValueError, KeyError):
                        pass
        finally:
            response.close()

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def invoke_agent(
        self,
        agent_name: str,
        task: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Invoke a LangGraph agent synchronously."""
        payload: dict[str, Any] = {"agent": agent_name, "task": task}
        if params is not None:
            payload["params"] = params
        data = self._http.post("/agent/invoke", json=payload)
        return AgentResult.from_dict(data)

    def create_task(
        self,
        agent: str,
        task: str,
        *,
        requires_approval: bool | None = None,
        notify_on_complete: bool | None = None,
    ) -> AgentTask:
        """Create an asynchronous agent task."""
        payload: dict[str, Any] = {"agent": agent, "task": task}
        if requires_approval is not None:
            payload["requires_approval"] = requires_approval
        if notify_on_complete is not None:
            payload["notify_on_complete"] = notify_on_complete
        data = self._http.post("/agent/tasks", json=payload)
        return AgentTask.from_dict(data)

    def get_task_status(self, task_id: str) -> AgentTask:
        """Poll the status of an async agent task."""
        data = self._http.get(f"/agent/tasks/{task_id}")
        return AgentTask.from_dict(data)

    # ------------------------------------------------------------------
    # Embeddings & Search
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for *text*."""
        data = self._http.post("/ai/embeddings", json={"input": text})
        vec_data = data.get("data")
        if vec_data and len(vec_data) > 0:
            embedding = vec_data[0].get("embedding") or []
            return [float(v) for v in embedding]
        embedding = data.get("embedding") or []
        return [float(v) for v in embedding]

    def search(
        self,
        query: str,
        *,
        index: str | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Semantic search over indexed content."""
        payload: dict[str, Any] = {"query": query}
        if index is not None:
            payload["index"] = index
        if limit is not None:
            payload["limit"] = limit
        data = self._http.post("/ai/search", json=payload)
        results_raw = data.get("results") or []
        return [SearchResult.from_dict(r) for r in results_raw]

    # ------------------------------------------------------------------
    # NLP Utilities
    # ------------------------------------------------------------------

    def classify(self, text: str) -> Classification:
        """Classify text into categories."""
        data = self._http.post("/ai/classify", json={"text": text})
        return Classification.from_dict(data)

    def translate(self, text: str, target_lang: str) -> str:
        """Translate text to *target_lang* (ISO 639-1 code)."""
        data = self._http.post(
            "/translation/translate",
            json={"text": text, "target_language": target_lang},
        )
        return data.get("translated_text") or data.get("translation", "")

    def sentiment(self, text: str) -> SentimentResult:
        """Analyze sentiment of text."""
        data = self._http.post("/ai/sentiment", json={"text": text})
        return SentimentResult.from_dict(data)

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    def stt(self, audio_bytes: bytes) -> str:
        """Speech-to-text: transcribe audio bytes."""
        import base64

        data = self._http.post(
            "/ai/stt",
            json={"audio": base64.b64encode(audio_bytes).decode()},
        )
        return data.get("text") or data.get("transcript", "")

    def tts(self, text: str, *, voice_id: str | None = None) -> bytes:
        """Text-to-speech: synthesize audio bytes from text."""
        import base64

        payload: dict[str, str] = {"text": text}
        if voice_id is not None:
            payload["voice_id"] = voice_id
        data = self._http.post("/ai/tts", json=payload)
        audio_b64 = data.get("audio")
        if audio_b64:
            return base64.b64decode(audio_b64)
        return b""
