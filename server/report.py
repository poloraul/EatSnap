"""静态 HTML 报告生成。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import AppConfig
from .records import list_record_dates, load_record
from .storage import copy_into_reports

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _images_dest(cfg: AppConfig) -> Path:
    return cfg.reports_dir / "images"


def render_day(cfg: AppConfig, date: str) -> Path:
    record = load_record(cfg, date)
    env = _env()
    tpl = env.get_template("day.html")
    html = tpl.render(record=record, generated_at=datetime.now().isoformat(timespec="seconds"))

    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.reports_dir / f"{date}.html"
    out.write_text(html, encoding="utf-8")

    # 复制图片到 reports/images/，使报告离线可看
    dest_root = _images_dest(cfg)
    for meal_entries in record.get("meals", {}).values():
        for entry in meal_entries:
            rel = entry.get("image")
            if rel:
                copy_into_reports(cfg, rel, dest_root)
    return out


def render_index(cfg: AppConfig, recent: int = 14) -> Path:
    dates = list_record_dates(cfg)
    dates_desc = list(reversed(dates))
    days = []
    for d in dates_desc[:recent]:
        rec = load_record(cfg, d)
        days.append(
            {
                "date": d,
                "total": rec.get("daily_total_kcal", 0),
                "meals": {m: sum((e.get("total_kcal") or 0) for e in rec.get("meals", {}).get(m, []))
                          for m in ("早", "午", "晚", "加餐")},
            }
        )

    env = _env()
    tpl = env.get_template("index.html")
    html = tpl.render(
        days=days,
        total_days=len(dates),
        recent=recent,
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.reports_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def render_all(cfg: AppConfig) -> list[Path]:
    paths: list[Path] = [render_index(cfg)]
    for d in list_record_dates(cfg):
        paths.append(render_day(cfg, d))
    return paths
