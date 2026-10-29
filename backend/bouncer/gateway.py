"""Model gateway: the single path for every Nemotron call.

All calls go to Nebius Token Factory through its OpenAI-compatible API. Each call
is logged with stage, model, tokens, latency and cost so the dashboard can show
which model did what. Responses must be JSON matching a pydantic schema; malformed
responses are rejected and retried.

When NEBIUS_API_KEY is not set (or the daily budget is spent) the gateway raises
ModelUnavailable and callers fall back to deterministic rule-based code. Those
fallbacks are logged with provider "offline-rules" so the UI never presents them
as model output.
"""
from __future__ import annotations

import json
import re
import time
from typing import TypeVar

from openai import APIError, AsyncOpenAI, BadRequestError
from pydantic import BaseModel, ValidationError

from .config import Settings
from .db import Store

T = TypeVar("T", bound=BaseModel)

THINK_RE = re.compile(r"<think>.*?</think>", re.S)
FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


class ModelUnavailable(Exception):
    """Raised when no live model can be called; callers must use their fallback."""


def extract_json(text: str) -> dict:
    text = THINK_RE.sub("", text or "").strip()
    fenced = FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in model output")
        text = text[start : end + 1]
    return json.loads(text)


class Gateway:
    def __init__(self, store: Store, settings: Settings):
        self.store = store
        self.settings = settings
        self._client: AsyncOpenAI | None = None
        self._json_mode = True

    @property
    def live(self) -> bool:
        return self.settings.models_live

    def _client_or_raise(self) -> AsyncOpenAI:
        if not self.live:
            raise ModelUnavailable("NEBIUS_API_KEY is not set")
        day_start = time.time() - 86400
        if self.store.spend_since(day_start) >= self.settings.daily_budget_usd:
            raise ModelUnavailable("daily model budget reached")
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.nebius_api_key,
                base_url=self.settings.nebius_base_url,
                timeout=self.settings.model_timeout_s,
                max_retries=2,
            )
        return self._client

    async def json(
        self,
        *,
        report_id: str | None,
        stage: str,
        tier: str,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 2048,
        temperature: float = 0.2,
        attempts: int = 3,
    ) -> T:
        client = self._client_or_raise()
        model = self.settings.tiers[tier]
        messages = [
            {"role": "system", "content": system + "\n\nRespond with a single JSON object only."},
            {"role": "user", "content": user},
        ]
        last_error = "unknown error"
        for _ in range(attempts):
            started = time.perf_counter()
            kwargs = {"response_format": {"type": "json_object"}} if self._json_mode else {}
            try:
                resp = await client.chat.completions.create(
                    model=model.model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
            except BadRequestError as exc:
                if self._json_mode:
                    # Some deployments reject response_format; retry once in plain mode.
                    self._json_mode = False
                    last_error = f"json mode rejected: {exc}"
                    continue
                self._log(report_id, stage, model, started, None, ok=False, error=str(exc)[:500])
                raise ModelUnavailable(str(exc)) from exc
            except APIError as exc:
                self._log(report_id, stage, model, started, None, ok=False, error=str(exc)[:500])
                raise ModelUnavailable(str(exc)) from exc

            content = resp.choices[0].message.content or ""
            try:
                parsed = schema.model_validate(extract_json(content))
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)[:800]
                self._log(report_id, stage, model, started, resp.usage, ok=False, error=f"malformed: {last_error}")
                messages = [
                    *messages,
                    {"role": "assistant", "content": content[:4000]},
                    {
                        "role": "user",
                        "content": "That response was rejected because it did not match the required JSON "
                        f"schema: {last_error}\nReturn only the corrected JSON object.",
                    },
                ]
                continue
            self._log(report_id, stage, model, started, resp.usage, ok=True)
            return parsed
        raise ModelUnavailable(f"{tier} returned malformed output {attempts} times: {last_error}")

    def record_offline(self, report_id: str | None, stage: str, tier: str, note: str) -> None:
        """Logs a step that ran deterministic fallback code instead of a model."""
        self.store.log_model_call(
            report_id=report_id,
            stage=stage,
            tier=tier,
            model="rule-based fallback",
            provider="offline-rules",
            ok=1,
            error=note,
        )

    def _log(self, report_id, stage, model, started, usage, *, ok: bool, error: str | None = None) -> None:
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        cost = tokens_in / 1e6 * model.usd_per_m_input + tokens_out / 1e6 * model.usd_per_m_output
        self.store.log_model_call(
            report_id=report_id,
            stage=stage,
            tier=model.tier,
            model=model.model_id,
            provider="nebius-token-factory",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=int((time.perf_counter() - started) * 1000),
            cost_usd=round(cost, 6),
            ok=1 if ok else 0,
            error=error,
        )
