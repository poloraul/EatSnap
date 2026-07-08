"""图片存储：落盘到 iCloud 目录 + 扫描 + 文件名解析归位。

路径布局（save_upload / iter_images）：
    {images_root}/{YYYY-MM-DD}/{餐别}/{时间戳}_{随机串}.jpg

扁平目录（ingest_pending 扫描）：
    {images_root}/{YYYY-MM-DD}_{meal}_{note_hash}_{HHMMSS}.jpg
    —— 由 tools/shot.html（iOS 端直接拍照存 iCloud）产生，归位到子目录结构。
"""

from __future__ import annotations

import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from .config import AppConfig, VALID_MEALS

FILENAME_DATE = "%Y-%m-%d"
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")

# shot.html 拍出的文件名：{YYYY-MM-DD}_{meal}_{note6}_{HHMMSS}.jpg
# 餐别用 VALID_MEALS 严格校验
FLAT_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<meal>"
    + "|".join(re.escape(m) for m in VALID_MEALS)
    + r")_[A-Za-z0-9]{1,8}_\d{6}\.(?P<ext>jpg|jpeg|png|webp|heic|heif)$"
)


@dataclass(frozen=True)
class SavedImage:
    """落盘后的一张图片信息。"""

    abs_path: Path
    rel_path: str  # 相对 images_root，存进 records
    date: str
    meal: str
    filename: str


def _safe_ext(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
        return ".jpg" if ext in {".jpeg", ".heic", ".heif"} else ext
    return ".jpg"


def _random_suffix() -> str:
    return secrets.token_hex(4)


def save_upload(
    cfg: AppConfig,
    *,
    file_bytes: bytes,
    original_name: str,
    meal: str,
    when: datetime | None = None,
) -> SavedImage:
    if meal not in VALID_MEALS:
        raise ValueError(f"未知餐别: {meal!r}（仅支持 {VALID_MEALS}）")

    when = when or datetime.now()
    date = when.strftime(FILENAME_DATE)
    safe_base = SAFE_NAME_RE.sub("_", Path(original_name).stem)[:40] or "image"
    filename = f"{when.strftime('%H%M%S')}_{safe_base}_{_random_suffix()}{_safe_ext(original_name)}"

    day_dir = cfg.images_root / date / meal
    day_dir.mkdir(parents=True, exist_ok=True)
    dest = day_dir / filename
    dest.write_bytes(file_bytes)

    rel = dest.relative_to(cfg.images_root).as_posix()
    return SavedImage(
        abs_path=dest,
        rel_path=rel,
        date=date,
        meal=meal,
        filename=filename,
    )


def iter_images(cfg: AppConfig, date: str) -> Iterable[SavedImage]:
    """列出指定日所有图片（含各餐别）。"""
    day_dir = cfg.images_root / date
    if not day_dir.exists():
        return
    for meal_dir in sorted(day_dir.iterdir()):
        if not meal_dir.is_dir() or meal_dir.name not in VALID_MEALS:
            continue
        for f in sorted(meal_dir.iterdir()):
            if f.is_file():
                yield SavedImage(
                    abs_path=f,
                    rel_path=f.relative_to(cfg.images_root).as_posix(),
                    date=date,
                    meal=meal_dir.name,
                    filename=f.name,
                )


def copy_into_reports(cfg: AppConfig, rel_path: str, dest_dir: Path) -> Path:
    """把图片复制到 reports 下的静态目录，使报告离线可看。"""
    src = cfg.images_root / rel_path
    dest = dest_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(src, dest)
    return dest


# ----- 扁平文件归位：shot.html 直接写 iCloud 根目录的产物 -----

def parse_flat_filename(name: str) -> tuple[str, str] | None:
    """解析 shot.html 风格的文件名，返回 (date, meal) 或 None。"""
    m = FLAT_NAME_RE.match(name)
    if not m:
        return None
    return m.group("date"), m.group("meal")


def iter_flat_files(cfg: AppConfig) -> Iterator[Path]:
    """扫描 images 根目录下、所有非子目录里的 .jpg/.png/.webp/.heic 文件。"""
    if not cfg.images_root.exists():
        return
    for p in cfg.images_root.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
            continue
        yield p


def ingest_pending(cfg: AppConfig, *, dry_run: bool = False) -> list[dict[str, str]]:
    """把根目录下的扁平图片按文件名归位到 {date}/{meal}/ 子目录。

    Returns: 实际归位的 [{from, to, date, meal}] 列表。
    """
    results: list[dict[str, str]] = []
    for src in list(iter_flat_files(cfg)):
        parsed = parse_flat_filename(src.name)
        if not parsed:
            continue
        date, meal = parsed
        dest_dir = cfg.images_root / date / meal
        dest = dest_dir / src.name
        if dest.exists():
            # 同名已存在，跳过避免覆盖
            continue
        results.append(
            {
                "from": src.relative_to(cfg.images_root).as_posix(),
                "to": dest.relative_to(cfg.images_root).as_posix(),
                "date": date,
                "meal": meal,
            }
        )
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
    return results
