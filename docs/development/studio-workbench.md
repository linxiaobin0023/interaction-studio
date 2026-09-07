# Studio 工作台

本轮把 Development 的定位流程接成了可操作的 React + TypeScript 界面。
仅用于本地研发，模型、Formal 和生产 Attempt 不参与此流程。

## 使用

```bash
# 完整本地运行：构建包含前端的 API 镜像，迁移后启动服务。
docker compose up --build -d
# 浏览器打开 http://127.0.0.1:8000/
```

API 默认绑定本机回环地址，`APP_BIND_HOST` 默认 `127.0.0.1`。共享部署仍需后续认证、
权限和限流工作。无需 OpenAI 或其他模型密钥。

1. 在左侧按交互类型或案例编号筛选素材。
2. 自动定位后拖拽商品，或用滑块调整位置、尺寸、角度；画布支持方向键微调。
3. 可用“绘制遮挡”圈出应保留的前景，点击“添加遮挡”；支持移除最后一层及撤销/重做。
4. 生成本地预览，或在“遮罩与保留区域”中检查六类遮罩。
5. 保存草稿，或命名保存为模板新版本。同名模板追加版本，不覆盖旧版本。
6. 保存记录可恢复历史参数；恢复后需再保存，才成为新的草稿版本。
7. 下载预览包或导出参数 JSON。切换案例时会提醒保存，离开页面有未保存提示。

如果其他页面已保存同一草稿，服务端返回版本冲突；当前未保存参数仍留在界面中，
可先导出，再重新读取服务端草稿。恢复旧版本也采用新增版本，不删除保存记录。

## 存储与接口

新增 Alembic 迁移 `0002_studio_editing`：

- `studio_drafts`：每个开发 Case 的当前参数及来源哈希、资源版本。
- `studio_events`：每次服务端保存的 before/after、序号、时间及 SHA256 前序链。
- `studio_templates`：不可通过 API 修改的模板版本，绑定交互类型、参数与内容哈希。

草稿和记录在同一个 PostgreSQL 事务中提交。使用行锁、条件更新及唯一约束处理并发；
客户端旧版本不能覆盖新数据。每次加载草稿验证来源和记录链，损坏时拒绝使用。
模板/草稿持久化不依赖 localStorage。浏览器撤销栈和未保存调整仅在当前页面有效。

API：

```text
GET  /api/v1/development/cases/{case_id}/image
GET  /api/v1/development/product-views/{view_id}/image
POST /api/v1/development/previews/masks/{mask_name}
GET  /api/v1/development/studio/drafts/{case_id}
PUT  /api/v1/development/studio/drafts/{case_id}
GET  /api/v1/development/studio/templates
POST /api/v1/development/studio/templates
```

`PUT draft` 请求体包含 `expected_version`、`parameters`（原 PreviewRequest）及
`action`（SAVE/RESET/APPLY_TEMPLATE）。首次保存版本为 0，服务端返回资源版本 1。
模板请求包含 `name` 和 `parameters`。图片入口仅按已知 Development Case/商品视图解析，
不能用任意文件路径访问 Validation/Formal 或配置文件。

## 开发与验证

```bash
make web-install web-check web-build
make lint test
# 已有本地 PostgreSQL 时，单独验证打包后的真实 HTTP 与持久化流程：
.venv/bin/python tools/smoke_studio_container.py
```

前端热更新：`make web-dev`，Vite 固定端口 5173、API 代理目标 127.0.0.1:28741；
另启 API 时使用该端口，并把 `DATABASE_URL` 配置为可连接的 PostgreSQL 地址。
不需要热更新时，直接使用包含前端的 Compose 服务即可。

后端继续使用 FastAPI/PostgreSQL；保留原型的主要布局和紫色/浅色主题。浏览器使用
Pointer Events、CSS 图层和 SVG 遮挡轮廓做即时定位，实际 PNG/Mask 由 Python 流程产生。
本轮没有把既有后端迁移到云端，也没有发布外部网站。

## 边界

- 记录粒度是“保存草稿”，不是每次拖拽的完整生产审计；operator 标记为 LOCAL_DEVELOPER，
  未接认证身份。哈希链用于本地一致性校验，不等于防篡改存储或 Object Lock。
- 模板保存完整归一化位置参数。只展示同交互、同数据集哈希的模板；应用到新 Case 后应复核定位。
- 没有自动生成嘴唇/手指遮挡，尚未加入 Gold 精度、真实接触修补、光照和折射处理。
- 界面不会生成质量通过率，也不会消耗 Business Attempt。
- 本轮进行了类型/构建、纯前端状态测试、后端与 HTTP 联调；未进行浏览器点击/视觉验收。
- 为支持后续代理检查，页面按浏览器能力注册只读 `inspect_studio_state` WebMCP 工具；
  当前环境没有提供可执行该工具的验证上下文，尚未验证浏览器端注册和调用。

后续功能：持久任务、结果与五维 QC 见 [任务与 QC 使用说明](studio-jobs-qc.md)。
