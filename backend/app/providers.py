from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv


class LLMProvider(Protocol):
    async def generate_json(self, system: str, user: str) -> dict[str, Any] | None: ...


class FakeLLMProvider:
    async def generate_json(self, system: str, user: str) -> dict[str, Any] | None:
        return None


class DeepSeekProvider:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("deepseek_api_key")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def generate_json(self, system: str, user: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return _parse_json_object(content)


def _parse_json_object(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

