"""CLI 入口：python -m server identify|ingest|report"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date

from .config import load_config
from .identify_runner import identify_date
from .report import render_all, render_day
from .storage import ingest_pending


def _add_date_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--date", default=_date.today().isoformat(), help="YYYY-MM-DD（默认今天）")


def main_identify(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m server identify")
    _add_date_arg(p)
    p.add_argument("--model", default=None)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    cfg = load_config()
    result = identify_date(cfg, args.date, model_name=args.model, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main_ingest(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m server ingest")
    p.add_argument("--dry-run", action="store_true", help="只看不动")
    args = p.parse_args(argv)
    cfg = load_config()
    result = ingest_pending(cfg, dry_run=args.dry_run)
    print(json.dumps({"ingested": result}, ensure_ascii=False, indent=2))
    return 0


def main_report(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m server report")
    p.add_argument("--date", default=None, help="YYYY-MM-DD；不传则全部")
    p.add_argument("--pages", action="store_true", help="生成 GitHub Pages 静态资源（docs/index.html + docs/reports/）")
    args = p.parse_args(argv)

    cfg = load_config()
    if args.date:
        out = render_day(cfg, args.date)
        print(str(out))
    elif args.pages:
        from .report import render_pages
        outs = [str(x) for x in render_pages(cfg)]
        print("\n".join(outs))
    else:
        outs = [str(x) for x in render_all(cfg)]
        print("\n".join(outs))
    return 0


_DISPATCH = {"identify": main_identify, "ingest": main_ingest, "report": main_report}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in _DISPATCH:
        sys.exit(_DISPATCH[sys.argv[1]](sys.argv[2:]))
    # 兼容旧调用：python -m server.identify --date ...
    sys.exit(main_identify(sys.argv[1:]))

