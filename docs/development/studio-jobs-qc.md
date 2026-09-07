# Development 处理任务与五维 QC

当前入口：`http://127.0.0.1:8000/`。选择 Development 素材后，在“处理任务与 QC”提交当前参数。
提交保存独立参数副本，不要求先保存草稿。页面关闭不影响工作进程；重新打开相同 Case 可查看任务。
成功任务可对照原图查看结果、下载 ZIP，并填写产品、交互、身份、场景、整体五项人工 QC。
所有项初始为空；未通过必须填写原因；服务端只有在五项全 PASS 时才记录 PASS。
审核修改会新增版本，旧版本保留；任务与审核 JSON 可导出。离开未保存审核会提示。

## 运行

```bash
docker compose up --build
```

Compose 包含独立 `studio-worker`，使用相同 API 镜像，只读取 Development 素材和相关封存证据。
本机直接运行时，在已配置 PostgreSQL 并迁移之后，分别运行 API 和 `make studio-worker`。
`python -m interaction_studio_api.studio_worker --once` 处理至多一个队列项。
任务执行不调用任何外部模型，仍使用已有本地几何合成。

## 数据与一致性

- 迁移 `0003_studio_jobs` 增加 `studio_jobs`、`studio_job_outputs`、`studio_reviews`。
- 入队绑定标准化参数和来源哈希；UUID 幂等键重放返回同一任务，改变参数或来源返回 409。
- PostgreSQL `FOR UPDATE SKIP LOCKED` 领取任务。5 分钟租约，崩溃或失联后允许重新领取；
  最多执行 3 次，超过返回 `WORKER_RETRY_EXHAUSTED`。旧租约 token 无法覆盖新工作进程结果。
- 任务为 `QUEUED → RUNNING → SUCCEEDED/FAILED`。确定性几何错误直接失败，调整后提交新任务。
  暂未提供取消/用户重试端点。这里的执行次数不是生产 Business Attempt / Infrastructure Retry。
- 渲染在数据库事务外执行；输入哈希不一致失败。ZIP 内容、manifest 和成功状态在同一事务提交。
  输出 ZIP 上限 32 MiB，存 PostgreSQL BYTEA；读取时核验 ZIP、manifest 绑定及各文件 SHA256。
- QC 绑定结果 ZIP 哈希，以 `expected_version` 和任务行锁处理并发；保存新版本形成内容哈希链。
  记录缺失或校验失败会阻断读取/新增审核。没有提供修改、删除既有结果或审核的 API。
- 认证版已绑定真实账号 ID；迁移前的 `LOCAL_DEVELOPER` 历史保留原标记。哈希校验不是签名、Object Lock 或 WORM。

## API

所有路径前缀为 `/api/v1/development/studio/jobs`：

| 方法 / 路径 | 行为 |
|---|---|
| POST 空路径 | `{idempotency_key, parameters}`，202 返回持久任务 |
| GET `?case_id=DEV_...&limit=20&offset=0` | 按 Case 倒序分页，`limit` 1–100，返回 `has_more` |
| GET `/{job_id}` | 任务、经校验 manifest、完整 QC 版本记录 |
| GET `/{job_id}/output?format=bundle` | 结果 ZIP；`format=png` 查看合成图 |
| POST `/{job_id}/reviews` | `{expected_version, output_sha256, dimensions}`，201 新增版本 |

`dimensions` 必须且只能含 `product/interaction/identity/scene/overall`，每项格式为
`{decision: "PASS" | "FAIL", reason: "..."}`。缺项、空判定、额外维度或 FAIL 原因空白返回 422。
状态不就绪、错误结果哈希、幂等/版本冲突返回 409；损坏数据返回安全错误码 503。
不接受 Validation/Formal Case，永远返回 `formal_eligible=false`。

## 验证与边界

`apps/api/tests/test_studio_jobs.py` 覆盖持久化、幂等、租约接续/旧进程隔离、来源变化、损坏数据、
五维校验、QC 历史/冲突及分页。`tools/smoke_studio_container.py` 在临时 PostgreSQL 数据库中
验证真实 HTTP、并发重复入队、跳过锁定任务、独立工作进程、输出哈希、并发审核和持久读取。
脚本只清理自身临时数据库；不会将测试 QC 写进用户项目。

开发队列选用 PostgreSQL 而非冻结架构建议的 Redis/RQ，是这一模型无关开发切片的局部实现决定：
将状态和小型结果原子保存，减少双存储提交失败。生产队列/存储方案仍待最终编排和容量验收。
数据库结果留存尚无配额、清理/保留策略和备份恢复验收；不适合开放给外部或大规模任务。

这些 QC 记录不计算 Technical/Production Pass Rate，不产生任何 G2/G3/Formal Gate 决策。
原始核心 `QCResult` 表仍包含旧 geometry/artifact 字段；本轮新增的 Development 协议使用正确五维，
没有将旧记录解释成新口径。正式 QC 导入协议、分析指标/冻结阈值仍需后续对齐。
未完成浏览器交互和视觉验收；当前验证为类型/构建、后端测试和容器 HTTP 联调。

认证与权限现已接入，见 [本地账号](local-accounts.md)；交付操作见 `docs/delivery/local-v1/README.md`。
