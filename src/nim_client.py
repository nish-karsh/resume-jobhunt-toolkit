"""OpenAI-compatible NVIDIA NIM client with model fallback and retry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Optional

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    OpenAI,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.settings_loader import load_settings, project_root

load_dotenv(project_root() / ".env")


class NimClientError(Exception):
    """Raised when all models in the chain fail."""


def _strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks some reasoning models emit before the answer."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # An unterminated <think> (truncated) - drop everything up to a later '{'.
    if re.search(r"<think>", text, flags=re.IGNORECASE):
        brace = text.find("{")
        think = re.search(r"<think>", text, flags=re.IGNORECASE)
        if brace != -1 and think is not None and brace > think.start():
            text = text[brace:]
        else:
            text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _first_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` object, ignoring braces inside strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


def _extract_json(text: str) -> dict[str, Any]:
    """Robustly extract a JSON object from model output."""
    text = _strip_reasoning(text.strip())
    if not text:
        raise ValueError("Empty response; expected JSON object")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    candidate = _first_json_object(text)
    if candidate:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Could not parse JSON object from model response")


class NimClient:
    """NVIDIA NIM chat client with primary + fallback model chain."""

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self.settings = settings or load_settings()
        api_key = __import__("os").environ.get("NVIDIA_API_KEY", "")
        if not api_key:
            raise NimClientError(
                "NVIDIA_API_KEY not set. Copy .env.example to .env and add your key."
            )
        self._client = OpenAI(
            base_url=self.settings.get(
                "base_url", "https://integrate.api.nvidia.com/v1"
            ),
            api_key=api_key,
            timeout=float(self.settings.get("request_timeout_s", 120)),
            max_retries=0,
        )
        models = self.settings.get("models", {})
        self._primary: str = models.get("primary", "")
        self._fallbacks: list[str] = list(models.get("fallbacks", []))
        self._utility: str = models.get("utility", "")
        self._max_retries = int(self.settings.get("max_retries", 4))

    @property
    def model_chain(self) -> list[str]:
        chain: list[str] = []
        if self._primary:
            chain.append(self._primary)
        chain.extend(self._fallbacks)
        return chain

    def _make_retry_decorator(self):
        return retry(
            retry=retry_if_exception_type(
                (RateLimitError, APITimeoutError, APIConnectionError)
            ),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self._max_retries),
            reraise=True,
        )

    def _chat_once(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> str:
        @self._make_retry_decorator()
        def _call() -> str:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            content = response.choices[0].message.content
            return content or ""

        return _call()

    def chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion; fall back through the model chain on failure."""
        chain = [model] if model else self.model_chain
        chain = [m for m in chain if m]
        if not chain:
            raise NimClientError("No models configured in settings.yaml")

        last_error: Exception | None = None
        for candidate in chain:
            try:
                return self._chat_once(
                    messages, candidate, temperature, max_tokens, **kwargs
                )
            except (
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                APIStatusError,
                NimClientError,
            ) as exc:
                last_error = exc
                continue
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status in (429, 408, 500, 502, 503, 504):
                    last_error = exc
                    continue
                raise

        raise NimClientError(
            f"All models failed ({', '.join(chain)}): {last_error}"
        ) from last_error

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema_hint: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat and parse a JSON object from the response."""
        if schema_hint:
            reminder = (
                "Respond with a single valid JSON object only, no markdown or commentary. "
                f"Schema hint: {schema_hint}"
            )
        else:
            reminder = (
                "Respond with a single valid JSON object only. No markdown fences, "
                "no commentary, no analysis."
            )
        base = list(messages) + [{"role": "user", "content": reminder}]
        raw = self.chat(
            base,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        try:
            return _extract_json(raw)
        except ValueError:
            # One repair attempt: show the model its own broken output and ask again.
            repair = base + [
                {"role": "assistant", "content": raw[:6000]},
                {
                    "role": "user",
                    "content": (
                        "That response was not valid JSON or was cut off. Reply again with "
                        "ONLY the complete, minified JSON object and nothing else."
                    ),
                },
            ]
            raw2 = self.chat(
                repair,
                model=model,
                temperature=0.0,
                max_tokens=max_tokens,
                **kwargs,
            )
            return _extract_json(raw2)

    def is_reachable(self, timeout: float = 10.0) -> bool:
        """Return True if the NIM endpoint responds to a models list request."""
        try:
            probe = OpenAI(
                base_url=self.settings.get(
                    "base_url", "https://integrate.api.nvidia.com/v1"
                ),
                api_key=self._client.api_key,
                timeout=timeout,
                max_retries=0,
            )
            probe.models.list()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """Return available model IDs from GET /v1/models."""
        response = self._client.models.list()
        ids: list[str] = []
        for item in response.data:
            model_id = getattr(item, "id", None)
            if model_id:
                ids.append(model_id)
        return sorted(ids)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="NVIDIA NIM client utility")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a minimal chat smoke test on the primary model",
    )
    args = parser.parse_args()

    try:
        client = NimClient()
    except NimClientError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    reachable = client.is_reachable()
    print(f"reachable: {reachable}")
    print(f"primary: {client._primary}")
    print(f"fallbacks: {', '.join(client._fallbacks)}")

    if reachable:
        models = client.list_models()
        print(f"available_models: {len(models)}")
        for slug in models[:15]:
            print(f"  - {slug}")
        if len(models) > 15:
            print(f"  ... and {len(models) - 15} more")

    if args.smoke and reachable:
        reply = client.chat(
            [{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=16,
            temperature=0.0,
        )
        print(f"smoke_reply: {reply.strip()!r}")

    return 0 if reachable else 2


if __name__ == "__main__":
    raise SystemExit(_cli())
