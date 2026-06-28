from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenMetrics:
    total: int = 0
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0


@dataclass(frozen=True, slots=True)
class ToolCallEvidence:
    ordinal: int
    call_id: str
    tool: str
    status: str
    title: str
    input: dict[str, Any]
    metadata: dict[str, Any]
    output_chars: int
    output_preview: str
    output_sha256: str
    failed: bool


@dataclass(slots=True)
class TrialMetrics:
    step_count: int = 0
    tool_call_count: int = 0
    failed_tool_call_count: int = 0
    tool_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    tokens: TokenMetrics = dataclasses.field(default_factory=TokenMetrics)
    cost: float = 0.0
    unknown_event_count: int = 0
    tool_calls: list[ToolCallEvidence] = dataclasses.field(default_factory=list)


def _int(value: object, *, default: int = 0) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    return default


def _float(value: object, *, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _str(value: object, *, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _add_tokens(current: TokenMetrics, new: TokenMetrics) -> TokenMetrics:
    return TokenMetrics(
        total=current.total + new.total,
        input=current.input + new.input,
        output=current.output + new.output,
        reasoning=current.reasoning + new.reasoning,
        cache_read=current.cache_read + new.cache_read,
        cache_write=current.cache_write + new.cache_write,
    )


def _normalize_tool_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize both flat and nested OpenCode tool_use event formats.

    Flat format (test fixtures):
        {"type": "tool_use", "tool": "read", "status": "success",
         "call_id": "c1", "input": {"path": "foo.py"}, ...}

    Nested format (real OpenCode JSONL):
        {"type": "tool_use", "part": {"tool": "read", "callID": "c1",
         "state": {"status": "success", "input": {"path": "foo.py"}, ...}}}
    """
    part = event.get("part")
    if not isinstance(part, dict):
        return event

    tool_name = _str(part.get("tool"))
    if not tool_name:
        tool_name = _str(event.get("tool"), default="unknown")

    state = _dict(part.get("state"))
    status = _str(
        state.get("status"), default=_str(event.get("status"), default="unknown")
    )
    title = _str(state.get("title"), default=_str(event.get("title")))
    output_raw = _str(state.get("output"), default=_str(event.get("output")))
    metadata = _dict(state.get("metadata"))
    if not metadata:
        metadata = _dict(event.get("metadata"))

    call_id = _str(part.get("callID"))
    if not call_id:
        call_id = _str(event.get("call_id"))

    tool_input = _dict(state.get("input"))
    if not tool_input:
        tool_input = _dict(event.get("input"))

    merged = dict(event)
    merged["tool"] = tool_name
    merged["status"] = status
    merged["title"] = title
    merged["output"] = output_raw
    merged["metadata"] = metadata
    merged["call_id"] = call_id
    merged["input"] = tool_input
    return merged


def extract_trial_metrics(
    stdout: str | None, *, preview_chars: int = 500
) -> TrialMetrics:
    metrics = TrialMetrics()
    ordinal = 0

    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            metrics.unknown_event_count += 1
            continue

        if not isinstance(event, dict):
            metrics.unknown_event_count += 1
            continue

        event_type = _str(event.get("type"))

        if event_type == "step_start":
            metrics.step_count += 1

        elif event_type == "tool_use":
            ordinal += 1
            normalized = _normalize_tool_event(event)
            tool_name = _str(normalized.get("tool"), default="unknown")
            status = _str(normalized.get("status"), default="unknown")
            failed = status in ("error", "failed")

            output_raw = _str(normalized.get("output"))
            output_sha256 = hashlib.sha256(output_raw.encode("utf-8")).hexdigest()
            output_chars = len(output_raw)
            output_preview = output_raw[:preview_chars]

            metrics.tool_call_count += 1
            if failed:
                metrics.failed_tool_call_count += 1
            metrics.tool_counts[tool_name] = metrics.tool_counts.get(tool_name, 0) + 1

            call_id = _str(normalized.get("call_id"), default=f"call-{ordinal}")
            metrics.tool_calls.append(
                ToolCallEvidence(
                    ordinal=ordinal,
                    call_id=call_id,
                    tool=tool_name,
                    status=status,
                    title=_str(normalized.get("title")),
                    input=_dict(normalized.get("input")),
                    metadata=_dict(normalized.get("metadata")),
                    output_chars=output_chars,
                    output_preview=output_preview,
                    output_sha256=output_sha256,
                    failed=failed,
                )
            )

        elif event_type == "step_finish":
            part = _dict(event.get("part"))
            payload = part or event
            tokens = _dict(payload.get("tokens"))
            cache = _dict(tokens.get("cache"))
            step_tokens = TokenMetrics(
                total=_int(tokens.get("total")),
                input=_int(tokens.get("input")),
                output=_int(tokens.get("output")),
                reasoning=_int(tokens.get("reasoning")),
                cache_read=_int(cache.get("read")),
                cache_write=_int(cache.get("write")),
            )
            metrics.tokens = _add_tokens(metrics.tokens, step_tokens)
            metrics.cost += _float(payload.get("cost"))

        else:
            metrics.unknown_event_count += 1

    return metrics


def metrics_payload(metrics: TrialMetrics) -> dict[str, Any]:
    payload = dataclasses.asdict(metrics)
    payload["tool_counts"] = dict(sorted(payload["tool_counts"].items()))
    return payload
