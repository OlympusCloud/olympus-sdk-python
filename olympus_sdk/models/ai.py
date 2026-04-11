"""AI models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AiResponse:
    """Response from an AI query or chat completion."""

    content: str
    model: str | None = None
    tier: str | None = None
    tokens_used: int | None = None
    finish_reason: str | None = None
    request_id: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AiResponse:
        usage = data.get("usage") or {}
        return AiResponse(
            content=data.get("content") or data.get("response") or data.get("text", ""),
            model=data.get("model"),
            tier=data.get("tier"),
            tokens_used=data.get("tokens_used") or usage.get("total_tokens"),
            finish_reason=data.get("finish_reason"),
            request_id=data.get("request_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"content": self.content}
        if self.model is not None:
            result["model"] = self.model
        if self.tier is not None:
            result["tier"] = self.tier
        if self.tokens_used is not None:
            result["tokens_used"] = self.tokens_used
        if self.finish_reason is not None:
            result["finish_reason"] = self.finish_reason
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result


@dataclass
class AgentStep:
    """A single step executed by an agent during task processing."""

    action: str
    observation: str | None = None
    thought: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AgentStep:
        return AgentStep(
            action=data["action"],
            observation=data.get("observation"),
            thought=data.get("thought"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"action": self.action}
        if self.observation is not None:
            result["observation"] = self.observation
        if self.thought is not None:
            result["thought"] = self.thought
        return result


@dataclass
class AgentResult:
    """Result from invoking a LangGraph agent."""

    output: str
    agent_name: str | None = None
    steps: list[AgentStep] = field(default_factory=list)
    tokens_used: int | None = None
    request_id: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AgentResult:
        steps_raw = data.get("steps") or []
        return AgentResult(
            output=data.get("output") or data.get("result", ""),
            agent_name=data.get("agent_name"),
            steps=[AgentStep.from_dict(s) for s in steps_raw],
            tokens_used=data.get("tokens_used"),
            request_id=data.get("request_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"output": self.output}
        if self.agent_name is not None:
            result["agent_name"] = self.agent_name
        if self.steps:
            result["steps"] = [s.to_dict() for s in self.steps]
        if self.tokens_used is not None:
            result["tokens_used"] = self.tokens_used
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result


@dataclass
class AgentTask:
    """An asynchronous agent task with status tracking."""

    id: str
    status: str = "unknown"
    agent_name: str | None = None
    task: str | None = None
    result: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AgentTask:
        return AgentTask(
            id=data.get("id") or data.get("task_id", ""),
            status=data.get("status", "unknown"),
            agent_name=data.get("agent_name") or data.get("agent"),
            task=data.get("task"),
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        r: dict[str, Any] = {"id": self.id, "status": self.status}
        if self.agent_name is not None:
            r["agent_name"] = self.agent_name
        if self.task is not None:
            r["task"] = self.task
        if self.result is not None:
            r["result"] = self.result
        if self.error is not None:
            r["error"] = self.error
        if self.created_at is not None:
            r["created_at"] = self.created_at.isoformat()
        if self.completed_at is not None:
            r["completed_at"] = self.completed_at.isoformat()
        return r

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_pending(self) -> bool:
        return self.status in ("pending", "running")


@dataclass
class Classification:
    """Text classification result."""

    label: str
    confidence: float
    scores: dict[str, float] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Classification:
        scores_raw = data.get("scores")
        return Classification(
            label=data.get("label") or data.get("category", ""),
            confidence=float(data.get("confidence") or data.get("score", 0.0)),
            scores={k: float(v) for k, v in scores_raw.items()} if scores_raw else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"label": self.label, "confidence": self.confidence}
        if self.scores is not None:
            result["scores"] = self.scores
        return result


@dataclass
class AspectSentiment:
    """Sentiment for a specific aspect of the analyzed text."""

    aspect: str
    sentiment: str
    score: float

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AspectSentiment:
        return AspectSentiment(
            aspect=data["aspect"],
            sentiment=data["sentiment"],
            score=float(data["score"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"aspect": self.aspect, "sentiment": self.sentiment, "score": self.score}


@dataclass
class SentimentResult:
    """Sentiment analysis result."""

    sentiment: str
    score: float
    aspects: list[AspectSentiment] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SentimentResult:
        aspects_raw = data.get("aspects") or []
        return SentimentResult(
            sentiment=data.get("sentiment", "neutral"),
            score=float(data.get("score", 0.0)),
            aspects=[AspectSentiment.from_dict(a) for a in aspects_raw],
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"sentiment": self.sentiment, "score": self.score}
        if self.aspects:
            result["aspects"] = [a.to_dict() for a in self.aspects]
        return result
