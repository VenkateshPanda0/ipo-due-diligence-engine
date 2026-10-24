"""One model-agnostic client: hard cost cap, on-disk cache, validated structured output.

No provider is bundled. A provider is any object with `name` and `complete()`; the client adds
what the project requires of every call: a spending cap enforced *before* a request is sent, a
cache keyed by the exact prompt, JSON that must validate against a Pydantic schema (bounded
retries, failures never cached), and a JSONL log of model, prompt hash, tokens and cost.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from redherring.llm.prompts import Prompt

CHARS_PER_TOKEN = 4  # rough input-size estimate used only for the pre-call budget check


class BudgetExceeded(RuntimeError):
    """The next call could push spending over the cap; it was not made."""


class StructuredOutputError(RuntimeError):
    """The model never produced output that validates against the schema."""


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, user: str, *, max_output_tokens: int) -> Completion: ...


@dataclass(frozen=True)
class ModelPrice:
    input_per_million_usd: float
    output_per_million_usd: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_per_million_usd + output_tokens * self.output_per_million_usd
        ) / 1_000_000


@dataclass
class CostLedger:
    """Running spend against a hard cap in US dollars.

    `check` is called with a pessimistic estimate before a request. Actual usage can differ from
    the estimate, so a single call can overshoot the cap; the next call is then refused.
    """

    cap_usd: float
    spent_usd: float = 0.0

    def check(self, estimate_usd: float) -> None:
        if self.spent_usd + estimate_usd > self.cap_usd:
            raise BudgetExceeded(
                f"estimated ${estimate_usd:.4f} on top of ${self.spent_usd:.4f} "
                f"exceeds the ${self.cap_usd:.2f} cap"
            )

    def charge(self, usd: float) -> None:
        self.spent_usd += usd


class DiskCache:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, key: str) -> str | None:
        p = self._path(key)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def put(self, key: str, text: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(text, encoding="utf-8")


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _parse[T: BaseModel](text: str, model: type[T]) -> T:
    return model.model_validate(json.loads(_FENCE.sub("", text)))


class LLMClient:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        price: ModelPrice,
        ledger: CostLedger,
        cache: DiskCache,
        log_path: Path,
        max_output_tokens: int = 1024,
    ) -> None:
        self.provider = provider
        self.price = price
        self.ledger = ledger
        self.cache = cache
        self.log_path = log_path
        self.max_output_tokens = max_output_tokens

    def _log(self, **record: object) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **record}) + "\n")

    def _cache_key(self, prompt: Prompt, model: type[BaseModel]) -> str:
        raw = f"{self.provider.name}|{model.__name__}|{prompt.hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def structured[T: BaseModel](self, prompt: Prompt, model: type[T], *, retries: int = 2) -> T:
        key = self._cache_key(prompt, model)
        if (cached := self.cache.get(key)) is not None:
            try:
                result = _parse(cached, model)
            except (ValidationError, ValueError):
                pass  # a corrupt or outdated entry is simply a miss
            else:
                self._log(model=self.provider.name, prompt_hash=prompt.hash, input_tokens=0,
                          output_tokens=0, cost_usd=0.0, cached=True, attempt=0)  # fmt: skip
                return result

        user = prompt.user
        last_error = "no attempt made"
        for attempt in range(retries + 1):
            est_in = (len(prompt.system) + len(user)) // CHARS_PER_TOKEN
            self.ledger.check(self.price.cost(est_in, self.max_output_tokens))
            done = self.provider.complete(
                prompt.system, user, max_output_tokens=self.max_output_tokens
            )
            cost = self.price.cost(done.input_tokens, done.output_tokens)
            self.ledger.charge(cost)
            self._log(model=done.model, prompt_hash=prompt.hash, input_tokens=done.input_tokens,
                      output_tokens=done.output_tokens, cost_usd=cost, cached=False,
                      attempt=attempt)  # fmt: skip
            try:
                result = _parse(done.text, model)
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:300]
                user = (
                    f"{prompt.user}\n\nYour previous reply did not validate: {last_error}\n"
                    "Reply with JSON only, matching the schema exactly."
                )
                continue
            self.cache.put(key, done.text)
            return result
        raise StructuredOutputError(f"no valid output after {retries + 1} attempts: {last_error}")
