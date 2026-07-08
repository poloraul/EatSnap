"""CLI 入口：python -m server.identify / python -m server.report"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date

from .config import load_config
from .identify_runner import identify_date
from .report import render_all, render_day


def _add_date_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--date", default=_date.today().isoformat(), help="YYYY-MM-DD（默认今天）")


def main_identify(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m server.identify")
    _add_date_arg(p)
    p.add_argument("--model", default=None)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    cfg = load_config()
    result = identify_date(cfg, args.date, model_name=args.model, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main_report(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m server.report")
    p.add_argument("--date", default=None, help="YYYY-MM-DD；不传则全部")
    args = p.parse_args(argv)

    cfg = load_config()
    if args.date:
        out = render_day(cfg, args.date)
        print(str(out))
    else:
        outs = [str(x) for x in render_all(cfg)]
        print("\n".join(outs))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        sys.exit(main_report(sys.argv[2:]))
    sys.exit(main_identify(sys.argv[1:]))
