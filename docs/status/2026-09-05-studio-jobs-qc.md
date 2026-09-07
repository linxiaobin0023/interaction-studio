# 本地处理任务与五维 QC 进度 — 2026-09-05

> 用户已确认本地可用版交付范围；最新状态见 [本地版交付](2026-09-05-local-delivery.md)。

状态：`MODEL DEFERRED / DEVELOPMENT JOBS AND QC DELIVERED`。

**项目整体尚未完成。** 本轮在现有 Studio 上打通“提交当前参数 → 后台处理 → 查看持久结果
→ 五维人工审核 → 保存版本/导出记录”，不代表生产模型、正式 QC 或最终验收完成。

## 本轮完成

- PostgreSQL 持久任务队列；UUID 幂等提交、独立后台工作进程、租约接续和最多 3 次执行。
- 多工作进程跳过已锁任务，旧租约结果不能覆盖重新领取后的任务。
- 绑定参数和素材哈希，成功状态与结果 ZIP 同事务保存；下载核验完整性。
- Studio 按 Case 查看任务/错误，关闭页面后任务继续；成功结果可对照原图查看和下载。
- 正确五维 Product / Interaction / Identity / Scene / Overall，全项显式判定，失败必填原因。
- 服务端派生审核结论，结果哈希绑定、版本冲突保护、保留旧审核和记录哈希链。
- 未保存审核提示、审核历史查看、任务/审核 JSON 导出。
- 新迁移 `0003_studio_jobs`，独立 `studio-worker` Compose 服务和运行命令。

使用及接口说明见 `docs/development/studio-jobs-qc.md`。

## 实际验证

- 后端完整套件 **134 项通过**，包括新增任务/QC 测试和迁移 up/down、metadata drift。
- 前端 **6 项既有逻辑测试通过**，TypeScript、格式检查及生产构建通过；新增 UI 未做浏览器点击验收。
- Ruff 与 Compose 配置检查通过，包含前端的 Docker 镜像构建通过：
  `sha256:f61c1004edb2102cddd8419ad5eb97bb7fddfce581299f73d0ff890cf862258a`。
- 临时 PostgreSQL 中真实 HTTP 验证通过：草稿/模板回归、4 个并发相同幂等键只生成 1 个任务、
  两事务跳过已锁任务、独立 worker 输出、ZIP 哈希、并发 QC 返回 201/409、worker 退出后记录仍可读取。
  临时数据库已清理；没有向用户项目写入测试任务或 PASS 审核。
- 实际项目数据库已升级到 `0003_studio_jobs`；本地 API 与独立 worker 已更新运行。
- 独立 worker 容器内真实素材合成通过，包含封存所需 registry 挂载检查。
- 当前 `http://127.0.0.1:8000/` 页面、JS/CSS、任务列表接口和模型关闭标记已通过 HTTP 检查。
- Development/Validation 封存、G0 原证据验证保持通过；没有调用任何模型 API。
- 浏览器入口已请求打开，仅返回 queued；没有据此宣称视觉或交互验收通过。

## 后续工作与边界

| 部分 | 状态 |
|---|---|
| 素材准入/封存、预览、Studio 草稿/模板 | 已实现开发流程 |
| 本地任务、持久结果、开发五维 QC | 本轮已实现；开发用途，非正式 Gate 证据 |
| 生产 Attempt/Retry、队列容量、输出保留策略 | 待完成生产编排与验收 |
| 正式 QC 导入/分析/冻结阈值 | 待对齐；核心旧 QC schema 仍有 geometry/artifact 字段 |
| 角色权限、审计身份、Object Lock、备份/恢复 | 待完成 |
| Gold/Proximity/自动遮挡、商品角度覆盖缺口 | 待完成 |
| 模型接触修补/材质处理、G2 稳定性测试 | 按用户要求暂缓 |
| 浏览器交互、Validation/Frozen Build/Formal/交付验收 | 未完成 |

当前结果包以 PostgreSQL BYTEA 留存，最大 32 MiB；这是本地开发规模的实现决定，
不是生产对象存储/WORM。审核人为固定 `LOCAL_DEVELOPER`；开发 PASS 不计算正式通过率。
下一步优先推进模型无关的身份/权限边界与证据/备份恢复，再对齐正式 QC 导入口径。
