"""OpenAI 多模态识别实现（占位，需 openai 库 + OPENAI_API_KEY）。"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from ..config import ModelConfig
from ..identify import IDENTIFY_PROMPT, IdentifyResult, parse_result_text


class OpenAIIdentifier:
    def __init__(self, spec: ModelConfig):
        self.spec = spec
        self._client: Any | None = None

    def _client_lazy(self) -> Any:
        if self._client is None:
            api_key = self.spec.api_key()
            if not api_key:
                raise RuntimeError(
                    f"未设置 {self.spec.api_key_env}，请在 .env 中填入 OpenAI API Key"
                )
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as e:
                raise RuntimeError("请先 pip install openai") from e
            self._client = OpenAI(api_key=api_key)
        return self._client

    def identify(self, image_path: str, remark: str) -> IdentifyResult:
        path = Path(image_path)
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        data_url = f"data:image/jpeg;base64,{data}"

        client = self._client_lazy()
        resp = client.chat.completions.create(
            model=self.spec.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": IDENTIFY_PROMPT.format(remark=remark or "（无）")},
                    ],
                }
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        items, total = parse_result_text(raw)
        return IdentifyResult(items=items, total_kcal=total, raw_text=raw, model_name=self.spec.name)
