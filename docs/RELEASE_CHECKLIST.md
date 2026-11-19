# 公开发布前最终检查清单

所有者已于 2026-11-19 明确授权：先创建并推送独立公开仓库，再部署静态网站。以下云端状态按实际结果更新。

| 检查 | 状态 | 下一步 |
| --- | --- | --- |
| 安全审计及独立源码导出 | PASS | 复核 SECURITY_AUDIT 与 FILE_MANIFEST |
| 原仓库直接公开 | BLOCKED | 不复用旧对象；口令轮换、不可见远端/备份另行核查 |
| 数据库口令轮换 | PASS | 新口令成功、旧/错误/空口令拒绝；私人环境与服务已更新 |
| FRED Key / 数据库 / 私人配置不进入产物 | PASS | 继续只从独立候选/干净 clone 发布 |
| 数据许可与软件许可证 | PASS | 新增数据或依赖时重新审核，保留声明 |
| 双语 README、截图、MIT、贡献与安全政策 | PASS | 上线后再填写真实体验链接 |
| 本地测试、静态构建、路由、来源与配置保存 | PASS | 具体计数与限制见 ACCEPTANCE |
| 跨 OS / 云端等效运行 | PASS | Windows 公网克隆、GitHub Ubuntu quality、Cloudflare Linux 构建通过 |
| 原创代码及 MIT 发布授权 | PASS | 所有者已明确授权独立仓库及网站发布；第三方数据和依赖保持各自许可 |
| 公开仓库与网页的明确发布授权 | PASS | 2026-11-19 所有者明确批准；Cloudflare 账户连接与 GitHub App 授权仍由所有者完成 |
| GitHub Public Repository 与分支保护 | PASS | 独立公开仓库、必需 quality/PR、管理员适用、禁止 force push 和删除 |
| GitHub 私密漏洞报告 / Secret scanning 账户设置 | NOT TESTED | 尚未核实账户可用功能与启用状态 |
| GitHub 托管 Actions 成功 | PASS | [quality](https://github.com/Issac0797/us-macro-intelligence/actions/runs/44430086339)：325 项测试及全部检查通过 |
| Pages Git Integration / main 正式站 | PASS | https://us-macro-intelligence.pages.dev/；生产 main 自动部署启用 |
| Pages PR Preview | NOT TESTED | 非正式分支预览已启用，待实际 PR 构建验证 |
| 失败构建保留旧版本及 Rollback | NOT TESTED | 授权上线后演练，不用猜测结果替代实测 |
| 正式域名深层路由及响应头 | PASS | 10 条 HTTPS 路由、真实 404、CSP/同源连接与安全头已验证 |
| 正式体验链接回填 | PASS | 已验证正式 URL 并回填双语 README，经 PR 发布 |

发布已获所有者明确授权。继续保留原开发备份的私有状态；未实测项不能因首次上线成功而标为 PASS。
