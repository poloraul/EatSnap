"""配置加载：config.yaml + .env。

支持路径中的 ~ 展开；路径统一在加载时展开为绝对路径，方便后续使用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# PyYAML 延迟到 load_config 时再加载，避免在只需要 AppConfig 类型的环境下被强制依赖。
# 外部也可以用 dataclass 构造 AppConfig 来跑测试。

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
DEFAULT_ENV_PATH = ROOT / ".env"

VALID_MEALS = ("早", "午", "晚", "加餐")


@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    model: str
    api_key_env: str
    base_url: str | None = None  # 可选：覆盖默认 base URL

    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


@dataclass(frozen=True)
class AppConfig:
    default_model: str
    models: dict[str, ModelConfig]
    images_root: Path
    records_dir: Path
    reports_dir: Path
    meals: tuple[str, ...]

    def get_model(self, name: str | None = None) -> ModelConfig:
        name = name or self.default_model
        if name not in self.models:
            raise KeyError(f"model not configured: {name}")
        return self.models[name]


def _expand(p: str | os.PathLike[str]) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(p)))).resolve()


def load_config(
    config_path: str | os.PathLike[str] = DEFAULT_CONFIG_PATH,
    env_path: str | os.PathLike[str] = DEFAULT_ENV_PATH,
) -> AppConfig:
    try:
        import yaml
    except ImportError as e:
        raise ImportError("缺少 PyYAML，请 pip install -r requirements.txt") from e

    try:
        from dotenv import load_dotenv
    except ImportError as e:
        raise ImportError("缺少 python-dotenv，请 pip install -r requirements.txt") from e

    config_path = Path(config_path)
    env_path = Path(env_path)

    if env_path.exists():
        load_dotenv(env_path, override=False)

    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")

    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    models_raw = raw.get("models") or {}
    if not models_raw:
        raise ValueError("config.models 不能为空")

    models: dict[str, ModelConfig] = {}
    for name, spec in models_raw.items():
        if not isinstance(spec, dict):
            raise ValueError(f"models.{name} 必须是字典")
        for key in ("provider", "model", "api_key_env"):
            if key not in spec:
                raise ValueError(f"models.{name} 缺少字段: {key}")
        models[name] = ModelConfig(
            name=name,
            provider=str(spec["provider"]),
            model=str(spec["model"]),
            api_key_env=str(spec["api_key_env"]),
            base_url=(str(spec["base_url"]) if spec.get("base_url") else None),
        )

    default_model = str(raw.get("default_model") or next(iter(models)))
    if default_model not in models:
        raise ValueError(f"default_model {default_model!r} 不在 models 中")

    paths = raw.get("paths") or {}
    images_root = _expand(paths.get("images_root", "~/Library/Mobile Documents/com~apple~CloudDocs/EatSnap/images"))
    records_dir = _expand(paths.get("records_dir", "./records"))
    reports_dir = _expand(paths.get("reports_dir", "./reports"))

    meals_raw = raw.get("meals") or list(VALID_MEALS)
    meals = tuple(str(m) for m in meals_raw)
    for m in meals:
        if m not in VALID_MEALS:
            raise ValueError(f"未知的餐别: {m!r}（仅支持 {VALID_MEALS}）")

    return AppConfig(
        default_model=default_model,
        models=models,
        images_root=images_root,
        records_dir=records_dir,
        reports_dir=reports_dir,
        meals=meals,
    )
