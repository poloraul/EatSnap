# EatSnap

拍食物照片 → 多模态大模型识别 → 记录每日热量。
完整设计见 `docs/` 目录下的三份文档：需求文档、产品设计文档、实现路径规划。

## 快速开始

```bash
# 1. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置 API Key（先把 .env.example 复制为 .env）
cp .env.example .env
# 编辑 .env，至少填入要用的模型 key（默认 claude → ANTHROPIC_API_KEY）

# 3. 启动服务
uvicorn server.main:app --host 0.0.0.0 --port 8765
# 浏览器打开 http://本机IP:8765/ 即可用手机/电脑拍照
```

## 目录布局

```
EatSnap/
├── docs/                  需求/设计/实现路径
├── server/                FastAPI 服务端
│   ├── main.py            接口入口
│   ├── config.py          配置加载（config.yaml + .env）
│   ├── storage.py         图片落盘到 iCloud 目录
│   ├── records.py         每日 JSON 记录
│   ├── identify.py        多模态识别抽象
│   ├── identify_runner.py 批量扫描与识别
│   ├── report.py          静态 HTML 报告
│   └── providers/         Claude / OpenAI 多模态实现
├── web/index.html         采集单页（getUserMedia 拍照）
├── templates/             报告 Jinja2 模板
├── config.yaml            模型与路径配置
├── .env.example           API Key 模板（不要提交 .env）
├── records/               运行期：每日 JSON（gitignore）
└── reports/               运行期：静态 HTML 报告（gitignore）
```

图片实际落盘到 `~/Library/Mobile Documents/com~apple~CloudDocs/EatSnap/images/{date}/{餐别}/`，
登录同一 Apple ID 后由 iCloud 自动云端备份。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/`              | 采集单页（手机/电脑浏览器） |
| GET  | `/healthz`       | 健康检查（包含 images_root/records_dir 等） |
| POST | `/upload`        | 上传图片：multipart，字段 `meal`、`remark`、`file` |
| GET  | `/records`       | 列出已有记录的所有日期 |
| GET  | `/records/{date}`| 查看某日记录 JSON |
| POST | `/identify?date=`| 手动触发批量识别（query: model?, force?） |
| POST | `/report?date=`  | 生成静态报告（不传 date 全部生成） |

## CLI

```bash
# 手动触发今日识别
python -m server.identify --date 2026-07-08

# 强制重跑（覆盖式重识别已有图）
python -m server.identify --date 2026-07-08 --force

# 生成报告
python -m server report
python -m server report --date 2026-07-08
```

## 多模型切换

`config.yaml` 中切换 `default_model` 即可（重启生效）。已内置 claude / openai 两个 provider，
未在 `models` 里的 provider 会在 `make_identifier` 抛 `NotImplementedError`。

> 注：实际 API 调用需要对应库。Claude 需要 `pip install anthropic`，OpenAI 需要 `pip install openai`。
> 不安装也能起服务，识别时再按需安装即可。

## 下一步（阶段 5 之后）

- 已处理图片状态文件，避免重复识别
- 报告趋势图、首页可视化
- 自动定时轮询（替代手动触发）
- 补录/编辑 UI
