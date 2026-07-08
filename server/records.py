"""每日 JSON 记录的读写。

records/{YYYY-MM-DD}.json 结构见《产品设计文档》第 5 节。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig, VALID_MEALS

STATUS_OK = "ok"
STATUS_REVIEW = "review"
STATUS_ERROR = "error"


def _empty_record(date: str) -> dict[str, Any]:
    return {"date": date, "meals": {m: [] for m in VALID_MEALS}, "daily_total_kcal": 0}


def record_path(cfg: AppConfig, date: str) -> Path:
    return cfg.records_dir / f"{date}.json"


def load_record(cfg: AppConfig, date: str) -> dict[str, Any]:
    path = record_path(cfg, date)
    if not path.exists():
        return _empty_record(date)
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def save_record(cfg: AppConfig, record: dict[str, Any]) -> Path:
    import json

    cfg.records_dir.mkdir(parents=True, exist_ok=True)
    path = record_path(cfg, record["date"])
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def is_image_processed(record: dict[str, Any], image_rel_path: str) -> bool:
    for meal_entries in record.get("meals", {}).values():
        for entry in meal_entries:
            if entry.get("image") == image_rel_path and entry.get("status") != STATUS_ERROR:
                return True
    return False


def _recalc_total(record: dict[str, Any]) -> None:
    total = 0
    for entries in record.get("meals", {}).values():
        for e in entries:
            total += int(e.get("total_kcal") or 0)
    record["daily_total_kcal"] = total


def add_meal_entry(
    cfg: AppConfig,
    *,
    date: str,
    meal: str,
    image_rel_path: str,
    remark: str,
    items: list[dict[str, Any]],
    model: str,
    status: str = STATUS_OK,
) -> dict[str, Any]:
    """追加一条识别/占位记录到当日 meal。"""
    if meal not in VALID_MEALS:
        raise ValueError(f"未知餐别: {meal!r}")

    record = load_record(cfg, date)
    total = sum(int(it.get("calories_kcal") or 0) for it in items)
    entry = {
        "image": image_rel_path,
        "remark": remark or "",
        "identified_at": datetime.now().isoformat(timespec="seconds"),
        "model": model or "",
        "items": items or [],
        "total_kcal": total,
        "status": status,
    }
    record["meals"].setdefault(meal, []).append(entry)
    _recalc_total(record)
    save_record(cfg, record)
    return entry


def list_record_dates(cfg: AppConfig) -> list[str]:
    if not cfg.records_dir.exists():
        return []
    return sorted(p.stem for p in cfg.records_dir.glob("*.json"))


def is_dirty_entry(entry: dict[str, Any]) -> bool:
    """判定为脏条目：识别失败且没有解析出条目（status=error 且 items 为空）。"""
    return entry.get("status") == STATUS_ERROR and not entry.get("items")


def clean_dirty_entries(cfg: AppConfig, date: str) -> dict[str, Any]:
    """删除指定日 records 中所有脏条目（is_dirty_entry 为真者），重算日合计。

    Returns: {date, removed: [{meal, image, identified_at}], kept}
    """
    record = load_record(cfg, date)
    removed: list[dict[str, Any]] = []
    for meal, entries in record.get("meals", {}).items():
        kept: list[dict[str, Any]] = []
        for e in entries:
            if is_dirty_entry(e):
                removed.append(
                    {
                        "meal": meal,
                        "image": e.get("image", ""),
                        "identified_at": e.get("identified_at", ""),
                    }
                )
            else:
                kept.append(e)
        record["meals"][meal] = kept
    _recalc_total(record)
    save_record(cfg, record)
    return {"date": date, "removed": removed, "kept": sum(len(v) for v in record["meals"].values())}


def clean_all_dirty(cfg: AppConfig) -> list[dict[str, Any]]:
    """清理所有日期的脏条目。"""
    results = []
    for d in list_record_dates(cfg):
        results.append(clean_dirty_entries(cfg, d))
    return results
