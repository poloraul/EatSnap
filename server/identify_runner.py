"""批量识别扫描：扫描当日未处理图片，逐张调用识别，结果写回 records。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import AppConfig
from .identify import IdentifyResult, make_identifier
from .records import (
    STATUS_ERROR,
    STATUS_OK,
    add_meal_entry,
    is_image_processed,
    load_record,
)
from .storage import iter_images


def identify_date(
    cfg: AppConfig,
    date: str,
    *,
    model_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """扫描并识别指定日所有未处理图片。

    Returns: {date, processed, skipped, failed, entries: [...]}
    """
    record = load_record(cfg, date)
    identifier = make_identifier(cfg, model_name)
    processed: list[dict[str, Any]] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []

    for img in iter_images(cfg, date):
        if not force and is_image_processed(record, img.rel_path):
            skipped.append(img.rel_path)
            continue
        try:
            result: IdentifyResult = identifier.identify(str(img.abs_path), remark="")
            entry = add_meal_entry(
                cfg,
                date=date,
                meal=img.meal,
                image_rel_path=img.rel_path,
                remark="",
                items=result.items,
                model=result.model_name,
                status=STATUS_OK,
            )
            processed.append(
                {
                    "image": img.rel_path,
                    "meal": img.meal,
                    "total_kcal": entry["total_kcal"],
                    "items_count": len(result.items),
                }
            )
            # 同一张图识别后写入记录，后续同批次图片不应再被重复处理
            record = load_record(cfg, date)
        except Exception as e:  # noqa: BLE001 - 记录错误后继续
            failed.append({"image": img.rel_path, "error": str(e)})
            add_meal_entry(
                cfg,
                date=date,
                meal=img.meal,
                image_rel_path=img.rel_path,
                remark=f"识别失败: {e}",
                items=[],
                model=(model_name or cfg.default_model),
                status=STATUS_ERROR,
            )
            record = load_record(cfg, date)

    return {
        "date": date,
        "triggered_at": datetime.now().isoformat(timespec="seconds"),
        "model": model_name or cfg.default_model,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    }
