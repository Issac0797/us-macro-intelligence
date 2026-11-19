# 更新与维护流程

## 每次代码更新

在功能分支修改；通过 PR 跑完整 `quality` 检查，保留后端回归。静态展示复用代码有变化时，构建脚本自动同步七份源文件；不要只修改生成的 `showcase/shared`。预览确认后合并到 `main`，由 Pages Git Integration 构建正式站。记录成功的 commit 与部署 URL；失败时保留旧站并修复或回滚。

提交前先 stage 已审核源码，运行 `python scripts/release/write_manifest.py` 更新文件清单与哈希，再 stage `docs/FILE_MANIFEST.json`。CI 会核对清单与仓库内容，避免遗漏来源文件或未说明的产物；不要 stage 私人运行时目录。

## 数据快照更新

快照不是实时服务。维护者按需主动刷新，建议集中批次提交，避免浪费免费构建与 BLS API 配额。先复核机构条款与 `data/licenses.json`；新增或变更来源必须先审核、再导出。执行 `export_snapshot.py --refresh-approved`、Schema/许可测试和静态构建。检查实际观测期、修订、缺失值、单位、覆盖、来源校验值和生成时间；只将获准的 JSON 快照提交 PR，不提交原始下载、数据库或日志。

在预览页面查看主要数值和来源。变化只更新明确的快照标识，不变成“实时”。如使用中断恢复的缓存模式，先复核每份原始证据的捕获时间；缓存不能冒充刚更新的源数据。源码 `showcase/public/data/snapshot.json` 是唯一静态数据输入。

## 依赖与安全

定期跑两份 `npm audit` 和 Python lock 的 `pip-audit`。升级时同时评估许可、上游公告和回归测试，更新两个 lock、依赖清单和必要的 LICENSE/NOTICE。若改为分发容器或冻结后端程序，重新检查 LGPL/MPL 和 native library 的分发义务。

发现凭据立即阻止发布，先撤销/轮换，再处理历史、PR 附件、部署产物和日志缓存。开发数据库与私人研究配置留在本机。不要将原开发工作区的 `.git`、`.local` 或 `.env` 同步到公开项目。受信任维护者开启私密漏洞报告并维护 supported-version 说明。

## 上线后监测与回滚

需要独立的公网验收时，在 GitHub Actions 手动运行 **Live HTTPS verification**。它从托管 Ubuntu 环境检查固定的正式域名、十条路由、真实 404、快照字节和安全响应头；只执行公开 GET，无数据库或密钥，也不参与静态构建。可本地运行 `python scripts/release/verify_live.py` 对比本机链路与托管环境的结果。连接失败时分别记录网络错误和部署状态，不把一次失败请求误写为构建失败。

查看 GitHub 检查和 Cloudflare 构建结果；仅在成功后更新文档中的站点链接/版本。若页面异常，先访问 `sources` 检查快照是否可读，再检查路由、控制台和安全响应头。使用已记录的上次成功部署回滚，修复后通过新 PR 发布。不要在生产预览上粘贴 API Key 来“临时修复”静态页面。

## 必须由所有者完成的首次上线验收

确认最终代码授权和安全整改，明确允许公开仓库及网页；创建独立公开仓库与 Git Integration；验证 PR Preview、main 部署、失败保留、回滚、正式 URL、响应头和配额。将证据写回验收表。独立公开仓库、GitHub quality 和首次 Pages 正式构建已成功；正式站为 https://us-macro-intelligence.pages.dev/。PR 预览、生产回滚/恢复、失败构建保留均已有实测证据，见验收表与 RECOVERY_RESULTS.json。
