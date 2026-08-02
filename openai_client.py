import json
import os
from dataclasses import dataclass
from typing import Callable

from openai import OpenAI

import openai_quota_guard as quotaguard
from app_settings import settings


class OpenAIClientError(RuntimeError):
    def __init__(self, message: str, *, error_class: str | None = None) -> None:
        super().__init__(message)
        self.error_class = error_class  # 'quota_billing' | 'rate_limit' | 'timeout' | 'other' | None


@dataclass
class OpenAIJsonResult:
    payload: dict
    input_tokens: int
    output_tokens: int


def _api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def is_openai_enabled() -> bool:
    return bool(_api_key()) and not bool(settings.USE_MOCK_PROVIDERS)


def _client() -> OpenAI:
    key = _api_key()
    if not key:
        raise OpenAIClientError("OPENAI_API_KEY is not configured")
    timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
    return OpenAI(api_key=key, timeout=timeout_seconds)


def _extract_text(response) -> str:
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise OpenAIClientError("OpenAI returned empty response")
    return text


def generate_json_with_retry(
    *,
    system_prompt: str,
    user_prompt: str,
    validator: Callable[[dict], None],
    max_output_tokens: int = 1800,
    temperature: float = 0.5,
) -> OpenAIJsonResult:
    if not is_openai_enabled():
        raise OpenAIClientError("OpenAI is disabled")

    model = (os.getenv("OPENAI_MODEL") or settings.OPENAI_MODEL or "gpt-4o-mini").strip()
    cli = _client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error = "unknown_error"
    last_error_class = "other"

    for attempt in range(2):
        try:
            response = cli.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_output_tokens,
                response_format={"type": "json_object"},
            )
            payload = json.loads(_extract_text(response))
            if not isinstance(payload, dict):
                raise ValueError("Model returned non-object JSON")
            validator(payload)
            usage = response.usage
            quotaguard.record_event("openai_success")
            return OpenAIJsonResult(
                payload=payload,
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            )
        except Exception as exc:
            last_error = str(exc)
            last_error_class = quotaguard.classify_openai_error(exc)
            # A quota/billing failure won't resolve itself on an immediate
            # retry (unlike a transient parse error) -- stop wasting the
            # second attempt (and the API budget) once we already know.
            if last_error_class == "quota_billing":
                break
            if attempt == 0:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"{user_prompt}\n\n"
                            "Fix the previous response. Return only valid JSON object that strictly matches the schema. "
                            "No markdown, no comments, no extra text."
                        ),
                    },
                ]

    if last_error_class == "quota_billing":
        quotaguard.record_event("openai_quota_error")
    elif last_error_class == "timeout":
        quotaguard.record_event("openai_timeout")
    elif last_error_class == "rate_limit":
        quotaguard.record_event("openai_rate_limit")

    raise OpenAIClientError(f"OpenAI JSON generation failed: {last_error}", error_class=last_error_class)
