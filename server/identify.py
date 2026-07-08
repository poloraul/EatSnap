"""多模态识别抽象。

初版仅定义接口与 JSON schema，不接真实 API——需要 API key 时再按 provider
实现 identify_image()。前端提示词约束沿用本项目已验证流程。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .config import AppConfig, ModelConfig

IDENTIFY_PROMPT = """你是一个严谨的AI营养分析专家，擅长通过视觉估算食物分量并计算热量。

请分析我上传的这张食物图片，完成以下动作，**不要输出任何多余的解释、问候或评价**：

1. **识别与拆分**：识别图片中所有独立的、可食用的食物种类。如果是混合食物（如盖浇饭、拌面），视作一个整体条目输出。
2. **重量预估（克）**：根据视觉比例（参考标准餐具尺寸、拳头大小等常识），估算每种食物的可食部分净重，单位精确到"g"。无法确定时请基于常识合理推测，并在数值后加"约"字。
3. **热量计算（千卡）**：基于通用中国食物营养成分表，计算每种食物的估算热量，单位"kcal"。
4. **合计总数**：计算本张图片中所有食物的总热量。

# 强制输出格式（严格遵守）
- 每一行仅输出一种食物，使用**中文逗号"，"**分隔三个字段。
- 顺序必须为：`食物名称，重量数值g，热量数值kcal`
- **最后一行**必须输出总热量，格式为：`总热量，xxx kcal`
- 单位缩写必须使用小写英文字母（g 和 kcal）。

# 附加上下文（用户可填的备注）
{remark}

请直接给出结果，**不要**包在 JSON/Markdown/代码块里。
"""


@dataclass
class IdentifyResult:
    items: list[dict[str, Any]]  # [{name, weight_g, calories_kcal, weight_approx?}]
    total_kcal: int
    raw_text: str
    model_name: str


class Identifier(Protocol):
    def identify(self, image_path: str, remark: str) -> IdentifyResult: ...


# 行：名称，约 80g，约 18kcal  （"约"在数字前后可选）
_LINE_RE = re.compile(
    r"^\s*([^，,]+?)\s*[,，]\s*约?\s*(\d+(?:\.\d+)?)\s*g\s*[,，]\s*约?\s*(\d+(?:\.\d+)?)\s*kcal\s*$"
)
# 总热量行：总热量，约 18 kcal
_TOTAL_RE = re.compile(r"总热量[，,]\s*约?\s*(\d+(?:\.\d+)?)\s*kcal")


def parse_result_text(text: str) -> tuple[list[dict[str, Any]], int]:
    """解析多模态按固定格式输出的纯文本。"""
    items: list[dict[str, Any]] = []
    total: int | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _TOTAL_RE.match(line)
        if m:
            total = int(round(float(m.group(1))))
            continue
        m = _LINE_RE.match(line)
        if m:
            name = m.group(1).strip()
            weight_g = float(m.group(2))
            kcal = float(m.group(3))
            item: dict[str, Any] = {
                "name": name,
                "weight_g": weight_g,
                "calories_kcal": int(round(kcal)),
            }
            # 文本里有"约"或重量含小数，标记为约值
            has_approx = ("约" in name) or (not weight_g.is_integer()) or ("约" in line)
            if has_approx:
                item["name"] = name.replace("约", "").strip()
                item["weight_approx"] = True
            items.append(item)
    if total is None:
        total = int(round(sum(it["calories_kcal"] for it in items)))
    return items, total


def make_identifier(cfg: AppConfig, model_name: str | None = None) -> Identifier:
    """按配置选择具体识别实现。

    实际调用在 .env 填入对应 API key 后由 ClaudeIdentifier/OpenAIIdentifier 负责。
    """
    spec = cfg.get_model(model_name)
    if spec.provider == "anthropic":
        from .providers.claude import ClaudeIdentifier  # type: ignore
        return ClaudeIdentifier(spec)
    if spec.provider == "openai":
        from .providers.openai import OpenAIIdentifier  # type: ignore
        return OpenAIIdentifier(spec)
    raise NotImplementedError(f"provider {spec.provider!r} 未实现")
