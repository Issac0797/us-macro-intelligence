# 静态展示覆盖范围

| 页面 / 能力 | 状态 | 交付行为与范围 |
| --- | --- | --- |
| Overview `/` | PASS | 官方 CPI 同比、失业率、非农月度变化、10Y 指标卡；真实观测日期；两幅历史图 |
| Inflation `/inflation/` | PASS | CPI / Core CPI 同比，原始指数与环比可在 Workspace 选择 |
| Labor `/labor/` | PASS | 失业率及月度非农变化，保留百分比与千人原单位 |
| Treasury Yield Curve `/yield-curve/` | PASS | 八个名义国债期限、两日期比较、完整共同观测日期选择、10Y−2Y 历史利差 |
| Chart Workspace `/workspace/` | PASS | 四图、独立系列/口径、统一 UTC 时间轴、缩放重置、浏览器配置与 CSV/JSON/PNG 导出 |
| Macro Analytics `/analytics/` | PARTIAL | 浏览器内原始值/同比/环比/绝对变化与按日期匹配 Pearson；原项目其他分析保留在本地完整版 |
| Fed Policy `/fed/` | PARTIAL | 五个已核验历史决策及 DFF 图；明确不提供完整决策年表、SEP、点阵图或实时政策判断 |
| 来源与许可 `/sources/` | PASS | 13 系列逐项归因、覆盖/单位/原生编号、许可链接、Schema/快照/软件声明下载 |
| 英文 / 简体中文 | PASS | 浏览器切换实测，导航/正文/图表主题/数字格式随语言变化；机构名称与原始单位在来源表保留原文 |
| Light / Dark / System | PARTIAL | 明暗及跟随当前系统偏好实测通过；未改变宿主 OS 偏好来实测运行中系统切换 |
| ECharts 图表缩放 | PASS | 拖动一幅国债图的左缩放手柄，四图共同时间范围由完整历史变为 2023–2026 |
| ECharts 光标联动 | PASS | 按 UTC 轴值同步四图；2024-06-14 两个月频图明确缺失，日频图显示 4.67 / 4.20；静默目标动作避免反馈循环 |
| 研究配置保存 | PASS | DGS10 / DGS2、原始值、联动设置保存后整页刷新仍恢复 |
| 移动适配 | PASS | 390px 视口下就业页图表正常，文档宽度等于可视宽度，无页面横向溢出；Sources 表格局部滚动 |
| 实时数据 / 后台日历 / ALFRED / 数据库写入 | BLOCKED in static mode | 页面明确列为限制；未加入后端调用或伪实时回退，本地完整版仍保留 |

使用 `PresentationProvider`、`Preferences`、`chart-presentation`、`chart-theme`、`presentation` 和双语词典的原始源码；构建时复制到忽略的共享目录，避免 Cloudflare 安装整个后端或完整版依赖。计算先按完整原生历史完成，再筛选展示范围；不前填、不插值，不将百分率误算为通胀增速。

Business Cycle 页面明确标注未获许可数据和动态分析限制；About / Data Status 显示快照状态。系统主题实际切换仍为 NOT TESTED，尚未完成的导出/搜索浏览器验收为 PARTIAL。
