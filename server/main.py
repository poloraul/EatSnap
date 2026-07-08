"""FastAPI 主入口。

接口：
- GET  /              采集单页（web/index.html）
- POST /upload        上传一张食物图（multipart: meal, remark, file）
- GET  /healthz       健康检查
- GET  /records/{date} 查看当日记录 JSON
- GET  /records       列出已有记录的日期
- POST /identify      手动触发识别（query: date, model?, force?）
- POST /report        生成报告（query: date? 不传则全部）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .identify_runner import identify_date
from .records import list_record_dates, load_record
from .report import render_all, render_day, render_index
from .storage import save_upload

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

cfg = load_config()
cfg.images_root.mkdir(parents=True, exist_ok=True)
cfg.records_dir.mkdir(parents=True, exist_ok=True)
cfg.reports_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="EatSnap", version="0.1.0")

if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/")
def root() -> Any:
    index = WEB_DIR / "index.html"
    if not index.exists():
        return {"name": "EatSnap", "web": "missing", "docs": "/docs"}
    from fastapi.responses import FileResponse

    return FileResponse(str(index))


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "images_root": str(cfg.images_root),
        "records_dir": str(cfg.records_dir),
        "default_model": cfg.default_model,
    }


@app.post("/upload")
async def upload(
    meal: str = Form(...),
    remark: str = Form(""),
    file: UploadFile = File(...),
) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        saved = save_upload(
            cfg,
            file_bytes=data,
            original_name=file.filename or "image.jpg",
            meal=meal,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return JSONResponse(
        {
            "ok": True,
            "image": saved.rel_path,
            "date": saved.date,
            "meal": saved.meal,
            "remark": remark,
        }
    )


@app.get("/records")
def records_index() -> dict[str, Any]:
    return {"dates": list_record_dates(cfg)}


@app.get("/records/{date}")
def get_record(date: str) -> dict[str, Any]:
    return load_record(cfg, date)


@app.post("/identify")
def trigger_identify(
    date: str = Query(..., description="YYYY-MM-DD"),
    model: str | None = Query(None),
    force: bool = Query(False),
) -> dict[str, Any]:
    return identify_date(cfg, date, model_name=model, force=force)


@app.post("/report")
def trigger_report(date: str | None = Query(None)) -> dict[str, Any]:
    if date:
        out = render_day(cfg, date)
        return {"ok": True, "files": [str(out)]}
    outs = render_all(cfg)
    return {"ok": True, "files": [str(p) for p in outs]}
