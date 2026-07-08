"""Anthropic Claude 多模态识别实现（需 anthropic 库 + ANTHROPIC_API_KEY）。

依赖：pip install anthropic
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from ..config import ModelConfig
from ..identify import IDENTIFY_PROMPT, IdentifyResult, parse_result_text


class ClaudeIdentifier:
    def __init__(self, spec: ModelConfig):
        self.spec = spec
        self._client: Any | None = None

    def _client_lazy(self) -> Any:
        if self._client is None:
            api_key = self.spec.api_key()
            if not api_key:
                raise RuntimeError(
                    f"未设置 {self.spec.api_key_env}，请在 .env 中填入 Anthropic API Key"
                )
            try:
                from anthropic import Anthropic  # type: ignore
            except ImportError as e:
                raise RuntimeError("请先 pip install anthropic") from e
            self._client = Anthropic(api_key=api_key)
        return self._client

    def identify(self, image_path: str, remark: str) -> IdentifyResult:
        path = Path(image_path)
        mime, _ = mimetypes.guess_type(path.name)
        mime = mime or "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")

        client = self._client_lazy()
        resp = client.messages.create(
            model=self.spec.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": data,
                            },
                        },
                        {"type": "text", "text": IDENTIFY_PROMPT.format(remark=remark or "（无）")},
                    ],
                }
            ],
        )

        text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        raw = "\n".join(text_parts).strip()
        items, total = parse_result_text(raw)
        return IdentifyResult(items=items, total_kcal=total, raw_text=raw, model_name=self.spec.name)
