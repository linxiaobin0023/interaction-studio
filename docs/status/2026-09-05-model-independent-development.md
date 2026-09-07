# 模型无关开发进度 — 2026-09-05

后续交付见 `2026-09-05-studio-workbench.md`：已新增可操作的 Studio 界面与草稿/模板持久化。

状态：`MODEL INTEGRATION DEFERRED / LOCAL DEVELOPMENT IN PROGRESS`。

用户明确要求模型部分先不处理，继续其他开发。本轮完成可独立使用的本地定位和遮罩
流程。无需 API Key、GPU、数据库或队列；没有外部模型调用或新增 API 费用。
原 G0 和数据集封存记录不变，G2/G3 尚未通过，Formal 保持关闭。

## 本轮交付

- `GET /api/v1/development/catalog`：30 个开发案例、11 个商品视图、默认定位和角度残差。
- `POST /api/v1/development/previews`：输出 PNG、JSON 清单或 ZIP 下载包。
- 三类交互的默认定位：Mouth 嘴角中心、Near-mouth 嘴角偏移、Hand-held 拇指/食指中点。
  支持手动指定视图、位置、尺寸、旋转、核心收缩/接触带宽度和遮挡多边形。
- RGBA 预乘 Alpha 重采样合成，统一仿射变换五个商品图层；Depth 保留 16 位。
- 六种遮罩和纯本地商品核心恢复函数；手动遮挡区恢复 Base 像素。
- 请求校验、角度残差/越界/可见核心约束、源文件完整性检查及不暴露文件路径的错误。
- `make local-preview` / `tools/run_local_preview.py`：本地可复现导出，已有不同内容拒绝覆盖。
- 每个包绑定源数据、参数、实现/几何代码、运行库版本和输出 SHA256。
- Compose 增加商品母版只读挂载；API 不持久化预览或创建 Business Attempt。

操作说明：`docs/development/local-preview-api.md`。

## 检查结果

- `make lint test`：通过；**108 tests passed**，3 个既有 warning。
- Development 和 Validation 本地 seal 校验通过；原 G0 引用哈希校验通过。
- 固定 G2 输入准备命令可重复运行，原 12 个案例残差均通过；未执行模型测试。
- Compose 配置和 API 镜像构建通过；非 root 临时容器内真实 HTTP 检查通过：
  30 Case/11 视图目录、Hand-held ZIP 及全部输出哈希、残差超限 409、Validation 输入 422。
  临时容器已移除，没有启动持续服务。镜像 ID：
  `sha256:746beba9f1e8c7660eb534a783b4b63edc5381937e52aaab62793f4804ec6a10`。
- 三个示例包的文件哈希/实现绑定、CLI 相同输入重复导出和拒绝覆盖被修改输出均通过。
- 全部 30 个开发 Case 执行默认定位渲染：**29 rendered / 1 blocked**。
- `DEV_MOUTH_011` 无满足 yaw ≤12°、pitch ≤8° 初值的商品视图，正确返回 409。
  当前最近视图 LEFT45_00 的 pitch 残差为 11.727°。此项不在固定 G2 的 12 个输入中。
- 29 个渲染成功只是工程可执行性检查，不是商品/交互/身份/场景/整体质量通过率。
- Coverage 清单：`docs/development/local-preview-v1/coverage.json` 及 SHA256 sidecar。
- 三类实际 PNG、六遮罩、五图层、manifest 和 ZIP 示例在同目录的 DEV_MOUTH_001、
  DEV_NEAR_001、DEV_HAND_001 子目录。

## 后续工作与边界

本轮是后端/CLI 本地流程，尚未建设可拖拽的 Studio 前端。可通过 FastAPI `/docs` 操作。
默认定位未做 Gold 精度验证，接触遮罩是商品边界几何带，嘴唇/手指遮挡需要手工指定；
Normal 通道保留源坐标系，Transmission/Specular 未用于真实材质合成。

接下来可继续交互编辑界面、模板/操作记录、QC 和证据管理等模型无关部分。
新增匹配视角应创建产品母版新版本，不能改写已封存输入。
模型接触修补、真实材质表现、五维 QC 评估、G2 基准及 Formal 准入仍待后续完成。
