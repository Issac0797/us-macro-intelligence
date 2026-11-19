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
| 跨 OS / 云端等效运行 | NOT TESTED | GitHub Ubuntu CI / Pages 上验证 |
| 原创代码权利及 MIT 授权确认 | PARTIAL | 由项目所有者在批准发布时确认 |
| 公开仓库与网页的明确发布授权 | PASS | 2026-11-19 所有者明确批准；Cloudflare 账户连接与 GitHub App 授权仍由所有者完成 |
| GitHub Public Repository 与规则集 | NOT TESTED | 授权后创建独立仓库，配置必需检查与私密报告 |
| GitHub 托管 Actions 成功 | NOT TESTED | 首次推送后核对 quality 日志 |
| Pages Git Integration / PR Preview / main 正式站 | NOT TESTED | 按 DEPLOYMENT 执行并保存实际 URL |
| 失败构建保留旧版本及 Rollback | NOT TESTED | 授权上线后演练，不用猜测结果替代实测 |
| 正式域名深层路由及响应头 | NOT TESTED | 验证八条路由、404、CSP/同源连接和安全响应头 |
| 正式体验链接回填 | NOT TESTED | 验证 URL 后以 PR 更新双语 README |

不会因这些云端项尚未执行而擅自发布。后续批准应明确新的公开 GitHub 仓库、Cloudflare Pages Git Integration 和首次部署范围；保留原开发备份的私有状态。
