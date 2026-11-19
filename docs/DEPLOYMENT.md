# Cloudflare Pages 免费部署与维护

状态（2026-11-19）：所有者已明确授权，独立[公开仓库](https://github.com/Issac0797/us-macro-intelligence)、[GitHub quality](https://github.com/Issac0797/us-macro-intelligence/actions/runs/44430086339)及 [Pages 正式站](https://us-macro-intelligence.pages.dev/)已成功。Cloudflare 账户及 GitHub App 授权由所有者完成。首次部署采用 Git Integration，以下教程可用于复建与维护；PR Preview、回滚和失败构建保留均已实测，证据见 ACCEPTANCE。

## 发布前

1. 阅读 [SECURITY_AUDIT](SECURITY_AUDIT.md) 和 [ACCEPTANCE](ACCEPTANCE.md)。保留原工作目录及旧 Git 对象为私有备份，不把旧 `.git` 复制到新仓库。
2. 若继续公开原开发仓库，先解决口令暴露及历史对象问题；本轮推荐只使用独立、干净的候选目录。轮换本地数据库口令的步骤见安全报告。
3. 从候选目录在新环境执行 `npm run build:showcase`，运行下列 CI 等效命令。检查快照来源、时间、覆盖和通知文件；确认项目所有者有权以 MIT 许可原创代码。
4. 在此阶段只做本地准备。**创建公开仓库、推送 GitHub、连接 Cloudflare 和首次部署均须所有者明确授权。**

## 授权后：建立独立 GitHub 仓库

在 GitHub 创建一个新的公开空仓库，建议名称 `us-macro-intelligence`，默认分支 `main`。不要修改开发备份仓库的可见性。不要从旧开发仓库 fork、mirror 或 push `--all`。

当前公开代码已在独立仓库的 `main`，且 `origin` 指向新的公开仓库。复建时，核对目录和文件清单后，添加**你刚创建的新仓库**作为 `origin`，只推送 `main`。如果重新初始化，请先复核 `.gitignore` 和 `docs/FILE_MANIFEST.json`，不要在原工作区执行 `git add .`。

启用 GitHub 私密漏洞报告、Secret scanning / Push protection（按账户可用功能）；配置 `main` 的规则集：必须 PR、至少一名 reviewer（适合协作时）、要求 `quality` 成功、禁止 force push / 删除分支，并限制绕过。原前后端测试仍属于必需检查。仅文档或网站变更也不应删除后端测试。

## 授权后：连接 Cloudflare Pages Git Integration

在 Cloudflare Dashboard 的 Workers & Pages 创建 Pages 项目，选择 **Import an existing Git repository / Connect to Git**。不要选择 Direct Upload。授权 Cloudflare GitHub App 时，仅授予这个新仓库的访问权限。

| 设置 | 值 |
| --- | --- |
| Repository | 新建的 GitHub Public Repository |
| Production branch | `main` |
| Framework preset | `None`（项目脚本管理 Next.js Static Export） |
| Root directory | 仓库根目录（留空或 `/`，取决于界面） |
| Build command | `npm run build:showcase` |
| Build output directory | `showcase/out` |
| Node.js version | `NODE_VERSION=24.22.3` |
| Disable default dependency install | `SKIP_DEPENDENCY_INSTALL=true` |
| Optional telemetry setting | `NEXT_TELEMETRY_DISABLED=1` |
| Production automatic deployments | Enabled：`main` |
| Preview branch deployments | 启用受信任的非 `main` 分支 |

不要填写 FRED Key、数据库 URL、Cloudflare API Token 或个人环境变量。构建脚本按 `showcase/package-lock.json` 自行 `npm ci`，同步仓库中终端共享组件、样式、字典和许可文件，然后构建、扫描。不会安装/启动 Python 后端，不下载宏观数据，不访问 PostgreSQL，不读取 `.env`。无需 Pages Functions、Worker、R2、D1 或付费附加产品。

首次上线已获授权并成功完成：https://us-macro-intelligence.pages.dev/。已验证十条主要路由、真实 404、快照/许可字节一致及安全响应头。双语 README 通过 PR 更新正式链接；后续变更仍经必需 quality 门禁。

## PR 预览和正式更新

同一仓库的受信任功能分支 PR 可生成 Pages Preview；在预览上核对图表、主题、语言、快照时间和来源后合并。Fork PR 可能不自动获得预览，应由维护者审核后建立受信任分支；不要为了预览引入 `pull_request_target` 执行外部代码。只有 `main` 更新正式网站。GitHub branch rules 负责合并门禁；Cloudflare Git Integration 不自动等待任意 GitHub CI，因此必须禁止未通过检查的直接推送。

构建失败不会替换最后一次成功的生产部署。故障时先查看 Pages 构建日志和 GitHub `quality`；恢复上次已验证的 commit 或在 Pages 使用 Rollback。保留最后成功的部署记录。2026-11-19 已实测生产回滚、恢复与失败构建保留：正式页面哈希随回滚/恢复切换，受控失败构建不会替换成功版本；正常构建命令已还原，见 RECOVERY_RESULTS.json。

## 深层路由

`output: 'export'` + `trailingSlash: true` 已导出 `/inflation/index.html` 等文件；没有将完整版的 API 或动态会议页面塞进静态构建。直接打开或刷新 `/workspace/`、`/yield-curve/` 等路径均有物理文件。`404.html` 让未知页面返回 404，不使用全站 SPA rewrite 掩盖路由问题。`_headers` 限定同源连接并保留安全响应头。

## 免费额度与上线复核

截至 2026-11-18 核查，[Pages Free 限制](https://developers.cloudflare.com/pages/platform/limits/) 包括每月构建次数等配额；使用前以账户和官方页面的实时值为准。本项目只需静态 Pages 和默认 `pages.dev` 域名，不要求购买域名。避免启用付费服务，快照变更集中通过 PR 提交以控制构建次数。

上线后必须检查正式 URL 的十个页面与真实 404、浏览器网络记录无本机 API、响应头生效、PR Preview、失败构建保留旧版、main 成功部署和回滚。将证据补入 [ACCEPTANCE](ACCEPTANCE.md)，把对应 NOT TESTED 改成 PASS 后才能宣称云端验收完成。

官方依据：[Build image / NODE_VERSION / SKIP_DEPENDENCY_INSTALL](https://developers.cloudflare.com/pages/configuration/build-image/)、[GitHub Integration](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/)、[Build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/)、[Serving Pages](https://developers.cloudflare.com/pages/configuration/serving-pages/)、[Preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)、[Rollbacks](https://developers.cloudflare.com/pages/configuration/rollbacks/)。
