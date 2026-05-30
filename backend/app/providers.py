from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from dotenv import dotenv_values, load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROVIDER_ID = "wanjie_ark"


class LLMProvider(Protocol):
    async def generate_json(self, system: str, user: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    api_key_env: str
    model_env: str
    base_url_env: str
    default_model: str
    default_base_url: str
    chat_completions_path: str
    supports_response_format: bool = True
    api_key_aliases: tuple[str, ...] = ()


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="deepseek",
        name="DeepSeek",
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_MODEL",
        base_url_env="DEEPSEEK_BASE_URL",
        default_model="deepseek-v4-flash",
        default_base_url="https://api.deepseek.com",
        chat_completions_path="/chat/completions",
        api_key_aliases=("deepseek_api_key",),
    ),
    ProviderSpec(
        id="wanjie_ark",
        name="万界方舟",
        api_key_env="WANJIE_ARK_API_KEY",
        model_env="WANJIE_ARK_MODEL",
        base_url_env="WANJIE_ARK_BASE_URL",
        default_model="glm-5.1",
        default_base_url="https://maas-openapi.wanjiedata.com/api",
        chat_completions_path="/v1/chat/completions",
        supports_response_format=False,
        api_key_aliases=("wjark_api_key", "WJARK_API_KEY"),
    ),
)
PROVIDER_SPEC_BY_ID = {spec.id: spec for spec in PROVIDER_SPECS}


class OpenAICompatibleProvider:
    def __init__(self, spec: ProviderSpec) -> None:
        env_file = _env_file()
        load_dotenv(env_file, override=False)
        values = _env_values(env_file)
        self.spec = spec
        self.api_key = _first_env((spec.api_key_env, *spec.api_key_aliases), values)
        self.model = _env_value(spec.model_env, values, spec.default_model)
        self.base_url = _env_value(spec.base_url_env, values, spec.default_base_url).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.api_key:
            key_name = "wjark_api_key" if self.spec.id == "wanjie_ark" else self.spec.api_key_env
            raise RuntimeError(f"{self.spec.name} 未配置 API Key，请在主 worktree 的 .env 中配置 {key_name}。")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if self.spec.supports_response_format:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=45) as client:
            try:
                response = await client.post(
                    _join_api_url(self.base_url, self.spec.chat_completions_path),
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"{self.spec.name} API 调用失败：HTTP {exc.response.status_code}") from exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"{self.spec.name} API 调用失败：{exc}") from exc

        parsed = _parse_json_object(content)
        if not parsed:
            raise RuntimeError(f"{self.spec.name} API 未返回可解析 JSON。")
        return parsed


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(PROVIDER_SPEC_BY_ID["deepseek"])


def build_provider_from_env() -> LLMProvider:
    values = _env_values(_env_file())
    spec = PROVIDER_SPEC_BY_ID[_active_provider_id(values)]
    return OpenAICompatibleProvider(spec)


def llm_config_payload() -> dict[str, Any]:
    values = _env_values(_env_file())
    return {
        "active_provider": _active_provider_id(values),
        "providers": [_provider_payload(spec, values) for spec in PROVIDER_SPECS],
    }


def _provider_payload(spec: ProviderSpec, values: dict[str, str]) -> dict[str, Any]:
    api_key = _first_env((spec.api_key_env, *spec.api_key_aliases), values)
    return {
        "id": spec.id,
        "name": spec.name,
        "api_key_env": spec.api_key_env,
        "model_env": spec.model_env,
        "base_url_env": spec.base_url_env,
        "configured": bool(api_key),
        "api_key_mask": _mask_secret(api_key),
        "model": _env_value(spec.model_env, values, spec.default_model),
        "base_url": _env_value(spec.base_url_env, values, spec.default_base_url),
    }


def _active_provider_id(values: dict[str, str]) -> str:
    selected = _env_value("LLM_PROVIDER", values, "")
    if selected in PROVIDER_SPEC_BY_ID:
        return selected
    default_spec = PROVIDER_SPEC_BY_ID[DEFAULT_PROVIDER_ID]
    if _first_env((default_spec.api_key_env, *default_spec.api_key_aliases), values):
        return default_spec.id
    for spec in PROVIDER_SPECS:
        if _first_env((spec.api_key_env, *spec.api_key_aliases), values):
            return spec.id
    return DEFAULT_PROVIDER_ID


def _env_file() -> Path:
    if explicit := os.getenv("SPRINTDUCK_ENV_FILE"):
        return Path(explicit)
    main_env = _main_worktree_env()
    if main_env and main_env.exists():
        return main_env
    return REPO_ROOT / ".env"


def _main_worktree_env() -> Path | None:
    git_file = REPO_ROOT / ".git"
    if not git_file.is_file():
        return None
    try:
        content = git_file.read_text().strip()
    except OSError:
        return None
    if not content.startswith("gitdir:"):
        return None
    git_dir = Path(content.removeprefix("gitdir:").strip())
    if not git_dir.is_absolute():
        git_dir = (REPO_ROOT / git_dir).resolve()
    if git_dir.parent.name != "worktrees":
        return None
    return git_dir.parent.parent.parent / ".env"


def _env_values(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    return {key: value for key, value in dotenv_values(env_file).items() if value is not None}


def _env_value(key: str, values: dict[str, str], default: str = "") -> str:
    return os.getenv(key) or values.get(key) or default


def _first_env(keys: tuple[str, ...], values: dict[str, str]) -> str:
    for key in keys:
        value = _env_value(key, values, "")
        if value:
            return value
    return ""


def _mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "configured"
    return f"{secret[:4]}...{secret[-4:]}"


def _join_api_url(base_url: str, path: str) -> str:
    if path.startswith("/v1/") and base_url.endswith("/v1"):
        path = path[3:]
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{suffix}"


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
