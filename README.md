# EatSnap

手机拍照 → 直接写入 iCloud Drive → Mac 端识别 → 每日热量记录。
完整设计见 `docs/` 目录下的三份文档：需求文档、产品设计文档、实现路径规划。

## 架构

```
┌─────────────────┐    navigator.share     ┌──────────────────┐
│ 手机 Safari      │ ─────────────────────▶ │  iCloud Drive     │
│ tools/shot.html  │   "存储到文件"          │  EatSnap/         │
└─────────────────┘                          │  ├─ 早/ ...        │
                                              │  ├─ 午/ ...        │
                                              │  ├─ 晚/ ...        │
                                              │  └─ 加餐/ ...      │
                                              └────────┬─────────┘
                                                       │ iCloud 同步
                                                       ▼
                                              ┌──────────────────┐
                                              │ Mac 本机           │
                                              │ ~/Library/.../    │
                                              │ EatSnap/images/   │
                                              │   ├─ {date}/     │
                                              │   │   └─ {meal}/  │
                                              │   └─ 扁平.jpg     │◀── iOS 拍完未归位
                                              └────────┬─────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │ server/           │
                                              │  identify         │ ◀── ingest_pending 自动归位
                                              │  records / report │
                                              └──────────────────┘
```

**关键：手机端 `tools/shot.html` 完全独立，零服务端依赖。**

## 快速开始

### 1. 手机端：拍照页
把 `tools/shot.html` 放到你能打开的地方，三种方式任选：

```bash
# 方式 A：放到 iCloud Drive 任意位置，手机用「文件 App」打开
cp tools/shot.html ~/Library/Mobile\ Documents/com~apple~CloudDocs/

# 方式 B：丢到 GitHub Pages / 任意静态托管
# （注意：HTTPS 站点才能用摄像头，file:// 也能用）
# 方式 C：Mac 本机 uvicorn 起服务后，手机连同一 Wi-Fi 访问
```

iOS Safari（15.4+）打开后：
1. 选餐别 → 拍 → 备注（可选）→ 点「保存到 iCloud」
2. 系统弹分享面板 → 选「存储到文件」→ 选 `iCloud Drive/EatSnap/` 根目录
3. 文件名已编码日期与餐别（例：`2026-07-08_早_e3b0c4_153326.jpg`），Mac 端自动归位

### 2. Mac 端：识别与记录

```bash
# 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env，至少填入要用的模型 key（默认 claude → ANTHROPIC_API_KEY）

# 手动触发今日识别（自动 ingest 扁平文件 + 识别未处理图）
python -m server identify

# 生成静态报告（可发布到 GitHub Pages）
python -m server report
```

### 3. 可选：起 HTTP 服务（仅在 Mac 上看报告 / 调试用）

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8765
# http://localhost:8765/             -- 已上线的概览（移动适配）
# http://localhost:8765/healthz      -- 健康检查
# http://localhost:8765/records/2026-07-08  -- 原始记录 JSON
```

> 提示：Mac 上 `http://localhost:8765/web/index.html` 是旧版「上传到服务端」方案，
> 新版不需要再走这条路——直接用 `tools/shot.html` 拍照存 iCloud。

## 目录布局

```
EatSnap/
├── docs/                  需求/设计/实现路径
├── server/                FastAPI 服务端（识别 + 记录 + 报告）
│   ├── main.py            接口入口
│   ├── config.py          配置加载（config.yaml + .env）
│   ├── storage.py         图片落盘 / 扫描 / ingest_pending（归位）
│   ├── records.py         每日 JSON 记录
│   ├── identify.py        多模态识别抽象
│   ├── identify_runner.py 批量扫描与识别（自动先 ingest）
│   ├── report.py          静态 HTML 报告
│   └── providers/         Claude / OpenAI 多模态实现
├── tools/shot.html        手机端独立拍照页（navigator.share 写 iCloud）
├── web/index.html         旧版：浏览器拍照上传到 FastAPI（保留作 fallback）
├── templates/             报告 Jinja2 模板
├── docs/index.html        GitHub Pages 入口
├── docs/reports/          GitHub Pages 发布的报告
├── config.yaml            模型与路径配置
├── .env.example           API Key 模板（不要提交 .env）
├── records/               运行期：每日 JSON（gitignore）
└── reports/               运行期：静态 HTML 报告（gitignore）
```

图片实际落盘到 `~/Library/Mobile Documents/com~apple~CloudDocs/EatSnap/images/`：
- 子目录 `{date}/{meal}/` 是归位后的最终位置（被 server 扫描识别）
- 根目录的扁平 `.jpg` 是 iOS 端拍完未归位（下次 `identify` 时自动归位）

## 文件名编码规则

`tools/shot.html` 拍出的文件名格式：

```
{YYYY-MM-DD}_{餐别}_{note6}_{HHMMSS}.{ext}

例：2026-07-08_早_e3b0c4_153326.jpg
```

- 餐别：早/午/晚/加餐（严格匹配）
- `note6`：备注的 6 位 hex hash（无备注为 `x`）
- 时间：拍照时刻的时分秒

`server/storage.py` 的 `ingest_pending()` 在每次 `identify` 前自动调用：
- 扫描根目录扁平文件，按文件名解析 → 移到 `{date}/{meal}/` 子目录
- 文件名不匹配的（如 iOS 自带相机直接拍的）保留在根目录，**不移动**

## CLI

```bash
# 手动触发今日识别
python -m server identify --date 2026-07-08

# 强制重跑（覆盖式重识别已有图）
python -m server identify --date 2026-07-08 --force

# 仅归位扁平文件（不识别）
python -m server ingest
python -m server ingest --dry-run     # 只看不动

# 生成报告
python -m server report
python -m server report --date 2026-07-08
```

## 多模型切换

`config.yaml` 中切换 `default_model` 即可（重启生效）。已内置 claude / openai 两个 provider。

> 注：实际 API 调用需要对应库。Claude 需要 `pip install anthropic`，OpenAI 需要 `pip install openai`。
> 不安装也能起 ingest/report 部分，识别时再按需安装即可。

## 下一步

- 自动定时轮询（替代手动触发 `identify`）
- 补录/编辑 UI（在浏览器里改识别结果）
- 报告趋势图
- 多模型并行比对
