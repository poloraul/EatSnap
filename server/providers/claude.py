"""Anthropic Messages 协议多模态识别实现。

支持自定义 base_url（用于 OpenCode Zen 等代理/兼容服务）。
不依赖 anthropic 库，用 httpx 直调。
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from ..config import ModelConfig
from ..identify import IDENTIFY_PROMPT, IdentifyResult, parse_result_text

DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeIdentifier:
    def __init__(self, spec: ModelConfig):
        self.spec = spec
        self.base_url = (spec.base_url or DEFAULT_BASE_URL).rstrip("/")

    def identify(self, image_path: str, remark: str) -> IdentifyResult:
        path = Path(image_path)
        mime, _ = mimetypes.guess_type(path.name)
        mime = mime or "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")

        api_key = self.spec.api_key()
        if not api_key:
            raise RuntimeError(
                f"未设置 {self.spec.api_key_env}，请在 .env 中填入 API Key"
            )

        url = f"{self.base_url}/v1/messages"
        body = {
            "model": self.spec.model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": mime, "data": data},
                        },
                        {"type": "text", "text": IDENTIFY_PROMPT.format(remark=remark or "（无）")},
                    ],
                }
            ],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()

        text_parts: list[str] = []
        for block in payload.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        raw = "\n".join(text_parts).strip()
        items, total = parse_result_text(raw)
        return IdentifyResult(items=items, total_kcal=total, raw_text=raw, model_name=self.spec.name)
