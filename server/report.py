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


def render_day(cfg: AppConfig, date: str, *, out_dir: Path | None = None, base: str = "") -> Path:
    record = load_record(cfg, date)
    env = _env()
    tpl = env.get_template("day.html")
    html = tpl.render(record=record, base=base, generated_at=datetime.now().isoformat(timespec="seconds"))

    target = out_dir or cfg.reports_dir
    target.mkdir(parents=True, exist_ok=True)
    out = target / f"{date}.html"
    out.write_text(html, encoding="utf-8")

    # 复制图片到 reports/images/，使报告离线可看
    dest_root = _images_dest(cfg)
    for meal_entries in record.get("meals", {}).values():
        for entry in meal_entries:
            rel = entry.get("image")
            if rel:
                copy_into_reports(cfg, rel, dest_root)
    return out


def render_index(
    cfg: AppConfig, recent: int = 14, *, out_dir: Path | None = None,
    base: str = "", shot_base: str = "",
) -> Path:
    """渲染概览页。
    base      — 日明细链接前缀（如 'reports/' 或 ''）
    shot_base — shot.html 链接前缀（如 '../' 或 ''）
    """
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
        base=base,
        shot_base=shot_base,
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
    target = out_dir or cfg.reports_dir
    target.mkdir(parents=True, exist_ok=True)
    out = target / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def render_all(cfg: AppConfig) -> list[Path]:
    paths: list[Path] = [render_index(cfg)]
    for d in list_record_dates(cfg):
        paths.append(render_day(cfg, d))
    return paths


def render_pages(cfg: AppConfig) -> list[Path]:
    """生成 GitHub Pages 静态资源：docs/index.html（根入口）+ docs/reports/{index,*.html}。

    不依赖 cfg.reports_dir，直接写到项目内的 docs/ 下。

    三个入口的相对前缀：
    - docs/index.html         : 明细链接前缀 'reports/'、shot.html 链接 'shot.html'
    - docs/reports/index.html : 明细链接 'X.html'（同目录）、shot.html 链接 '../shot.html'
    - docs/reports/X.html     : 返回 'index.html'（reports 内概览）
    """
    ROOT = Path(__file__).resolve().parent.parent
    pages_root = ROOT / "docs"
    pages_reports = pages_root / "reports"
    out: list[Path] = []

    # 1) docs/reports/{date}.html
    dates = list_record_dates(cfg)
    for d in dates:
        rec = load_record(cfg, d)
        env = _env()
        # 明细页 "← 概览" 指向 Pages 根 docs/index.html
        html = env.get_template("day.html").render(
            record=rec, base="../", generated_at=datetime.now().isoformat(timespec="seconds")
        )
        dest = pages_reports / f"{d}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        out.append(dest)
        for meal_entries in rec.get("meals", {}).values():
            for entry in meal_entries:
                rel = entry.get("image")
                if rel:
                    copy_into_reports(cfg, rel, pages_reports / "images")

    # 2) docs/index.html（Pages 根入口）
    #    明细链接前缀 'reports/'、shot.html 链接 'shot.html'
    out.append(render_index(cfg, out_dir=pages_root, base="reports/", shot_base=""))
    return out
