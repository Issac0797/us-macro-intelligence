# US Macro Intelligence

[English](README.md) · [免费部署教程](docs/DEPLOYMENT.md) · [数据许可](docs/DATA_LICENSES.md)

独立的美国宏观经济研究终端，以及无需后端的静态展示版。项目以官方真实观测、明确的数据口径、可追溯来源和保留缺失值为基础，支持通胀、就业、国债曲线与政策历史研究。

**Public Preview** · [在线体验](https://us-macro-intelligence.pages.dev/) · [GitHub CI](https://github.com/Issac0797/us-macro-intelligence/actions/runs/44430086339)。静态网站通过 Cloudflare Pages Git Integration 自动部署，不托管实时后端；实际状态见 [发布报告](docs/ITERATION9_PUBLIC_RELEASE.md)。

![英文浅色总览](docs/screenshots/overview-en-light.jpg)
![四图工作区](docs/screenshots/release/four-linked-cursor-zh-light.jpg)

## 选择使用方式

| 使用方式 | 是否需要自己的 FRED API key | 数据与功能 |
| --- | --- | --- |
| [在线体验](https://us-macro-intelligence.pages.dev/)或自行部署静态展示版 | 不需要 | 已审核历史快照、图表、搜索与导出；不实时更新 |
| 本地完整版，使用默认 `fred_csv` | 不需要 | 从 FRED 公开 CSV 服务下载受支持的普通观测；元数据与修订研究能力有限 |
| 本地完整版，使用 `fred_api` | **需要** | FRED API 观测与元数据，以及 ALFRED 历史版本/修订研究，具体取决于来源可用性 |

**API 模式请自行申请并配置密钥。** 项目不附带或共享维护者的个人密钥。请使用自己的 FRED 账户申请，将密钥保存在本地后端配置中。公开演示站没有密钥输入入口；在 Cloudflare Pages 添加密钥也不会启用本地完整版功能。

## 功能与研究目标

- 共用终端的分组导航、可选指标卡、历史图、指标简报和观测明细。
- 总览、通胀、劳动力市场、国债收益率曲线及指定日期比较。
- 图表联动光标与缩放、日期筛选、原生单位、同比/环比/绝对变化。
- 四图 UTC 时间对齐、浏览器保存研究配置、CSV/JSON/PNG 导出及 Ctrl+K 搜索。
- 按完全匹配日期计算描述性皮尔逊相关系数，不插值、不生成人造观测。
- 选定且已核验的美联储历史决策，提供官方原文链接。
- 简体中文 / English；浅色 / 深色 / 跟随系统。
- 本地完整版保留 PostgreSQL 观测与修订、经济日历监控、ALFRED、图表工作区、宏观分析和 Fed Policy。

本轮不新增预测模型或交易功能。

## 技术架构

```text
Windows 完整版：Next.js / React / ECharts → FastAPI → PostgreSQL
静态展示：      Next.js Static Export → HTML / JS / 已审核 JSON
快照更新：      官方原始来源 → 许可白名单及 Schema → PR
自动部署：  GitHub main → Cloudflare Pages Git Integration
```

独立 `showcase/` 入口通过 `sync-shared.mjs` 复用终端外框、分组导航、指标卡、主题和双语偏好组件。历史图在浏览器读取已审核快照，可以把所选序列、时间范围和转换方式带入图表工作区。每条公开路由生成对应的 `index.html`，未知路由使用独立的 `404.html`。

## 静态版本地启动

需要 Node.js **24 LTS**、npm 和 Git；构建不需要 Python、PostgreSQL 或 API Key。

```powershell
git clone https://github.com/Issac0797/us-macro-intelligence.git
cd us-macro-intelligence
npm.cmd run build:showcase
npx.cmd --yes http-server@14.1.1 showcase/out -a 127.0.0.1 -p 3100
```

访问 [本地展示](http://127.0.0.1:3100)。构建命令会按 lockfile 安装静态依赖，输出 `showcase/out`，并检查路由、链接与产物敏感信息。开发使用 `npm.cmd ci --prefix showcase` 后运行 `npm.cmd run dev --prefix showcase`。

## Windows 本地完整研究终端

需要 Git 和 Docker Desktop（Linux containers）。按上面的命令克隆仓库后，在项目根目录操作。已有 `.env` 时不要覆盖。

```powershell
Copy-Item .env.example .env   # 仅在不存在时执行
```

编辑 `.env`，将 `POSTGRES_PASSWORD` 替换为独立的本地数据库口令。Docker Compose 会提供容器内的数据库连接；原生开发还需要按 [LOCAL_DEVELOPMENT](docs/LOCAL_DEVELOPMENT.md) 更新 `DATABASE_URL`。

### 配置数据来源

暂时不申请 API key，可以保留以下默认配置：

```dotenv
DATA_PROVIDER=fred_csv
FRED_API_KEY=
```

如需完整 API 元数据与 ALFRED 研究功能：

1. 登录自己的 FRED 账户，按 [FRED 官方密钥申请说明](https://fred.stlouisfed.org/docs/api/api_key.html)申请 key。
2. 修改本地 `.env` 中已有的对应配置项：

   ```dotenv
   DATA_PROVIDER=fred_api
   FRED_API_KEY=your_key_here
   ```

   将占位文字替换为自己的真实 key。数据库口令和 FRED API key 是两项不同的凭据。

### 启动终端

选择上述任一数据来源后，启动服务并下载数据：

```powershell
docker compose up --build -d --wait
docker compose exec -T backend python -m app.sync --full
```

访问 [研究终端](http://localhost:3000) 或 [API 文档](http://localhost:8000/docs)。`fred_csv` 是普通观测的显式替代路径，不能替代所有 ALFRED 与元数据功能。密钥只供后端读取。普通 `docker compose down` 保留命名数据卷。原生开发与完整测试步骤见 [LOCAL_DEVELOPMENT](docs/LOCAL_DEVELOPMENT.md)。

### 密钥保护与常见问题

- `.env` 已被 Git 忽略。仅提交空白/示例配置 `.env.example`；真实 key 不应放入前端代码、`NEXT_PUBLIC_*` 变量、截图、公开 issue 或静态托管设置中。
- 提示 `FRED_API_KEY is required for fred_api`：填写自己的 key，或明确改用 `DATA_PROVIDER=fred_csv`。API 模式需要密钥，不会静默切换到 CSV。
- 修改 `.env` 后，重新运行 `docker compose up --build -d --wait`，让后端容器读取新环境，再执行同步命令；原生启动则重启后端进程。
- 密钥被拒绝或请求受限：检查自己的 FRED 账户、密钥和适用的 [API 使用条款](https://fred.stlouisfed.org/docs/api/terms_of_use.html)。拥有 key 不保证所有序列或历史版本均可获取。
- 如密钥泄露，请通过 FRED 撤销/更换，并更新本地 `.env`；仅从最新提交中删除不足以保护密钥。详见 [SECURITY](SECURITY.md)。

## 数据来源、使用与版权

公开快照仅纳入 [许可白名单](data/licenses.json) 中 13 个已审核系列：BLS 的 CPI、核心 CPI、失业率、非农就业，以及美联储 Board H.15 的有效联邦基金利率和八个名义国债期限。数据直接取自原始机构，FRED Series ID 仅作为熟悉的别名，不再分发 FRED/ALFRED 数据集。

快照包含 Series ID / 原生编号、真实观测日期、值、单位、频率、季调、来源、生成日期、覆盖范围、许可说明及下载校验值。月度日期代表统计月份，不是发布时间；缺失值保留为空；最新修订后的观测不冒充历史 vintage。所有页面显式标为“历史快照 · 非实时”。

**MIT 仅适用于原创项目代码和文档，不自动覆盖政府数据、测试来源摘录、商标或依赖软件。** 数据按 [BLS 政策](https://www.bls.gov/bls/linksite.htm) 和 [美联储 Board 声明](https://www.federalreserve.gov/disclaimer.htm) 核查并保留来源；不分发官方徽章、标志、照片或外部插图。详见 [数据许可说明](docs/DATA_LICENSES.md)、[依赖许可说明](docs/DEPENDENCIES.md) 和 [第三方许可原文](THIRD_PARTY_NOTICES.txt)。

## 已知限制与验证

静态版不提供实时更新、经济日历监控、ALFRED 修订、服务器研究账户、数据库写入、自定义来源导入、完整 FOMC 年表或 SEP/点阵图。PCE、GDP、NBER 及所有未审核系列被排除。浏览器配置只在当前来源内保存，可能被浏览器清除。相关性是描述性统计，不代表因果。

CI 保留原前后端全部测试，加入双项目 TypeScript、PostgreSQL 隔离 schema、快照 Schema/许可、源码/产物扫描、静态构建及 HTTP 链接路由检查。CI 不执行发布；后续通过 Cloudflare Git Integration 在 `main` 成功构建后更新正式站。实际结果与未完成的云端检查见 [验收表](docs/ACCEPTANCE.md)。

## 参与与安全

通过 PR 贡献，遵守 [CONTRIBUTING](CONTRIBUTING.md)。安全问题按 [SECURITY](SECURITY.md) 私下报告，不在公开 issue 粘贴密钥、数据库连接或个人研究资料。

## 免责声明

本项目是独立研究软件，不作任何担保，也不代表数据机构背书。数据可能延迟、缺失或修订，不构成投资、交易、法律或税务建议。使用前应再次核对官方来源及适用条款。
