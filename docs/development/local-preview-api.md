# 本地定位与遮罩预览

本功能不需要模型、GPU、API Key、数据库或队列。读取 Development v1 的封存素材和
商品母版，在本地完成定位、RGBA 合成及遮罩导出。不是生成式接触修补或正式生产输出。

## 启动和导出

```bash
make api-dev
# 在浏览器打开 http://localhost:8000/docs，使用 local-development 分组。

# 命令行导出，目录和 preview_id 会打印到终端。
make local-preview CASE_ID=DEV_MOUTH_001
make local-preview CASE_ID=DEV_NEAR_001
make local-preview CASE_ID=DEV_HAND_001
```

CLI 默认写入 `.cache/local-previews/<preview_id>/`，包括预览、图层、遮罩、manifest
和 ZIP。同一输入在同一实现/依赖版本下得到相同文件；已有内容不同时拒绝覆盖。
该目录是可再生的本地研发输出，不是封存数据或 Object Lock Evidence。

API 不持久化文件、不创建 Attempt，不调用外部服务。仅用于可信本地研发环境；
部署到共享环境前仍需认证、权限与请求限流。

## API

`GET /api/v1/development/catalog` 返回 30 个开发 Case 的 ID、交互类型、尺寸、哈希、
默认定位、商品视图及角度残差，同时列出 11 个可选商品视图。
不提供 Validation/Formal Case 内容，也不返回服务器文件路径。

`POST /api/v1/development/previews?format=bundle` 下载 ZIP，`format=png` 返回预览图，
`format=manifest` 返回参数和证据清单。例如：

```bash
curl --fail-with-body http://localhost:8000/api/v1/development/previews?format=bundle \
  -H 'Content-Type: application/json' \
  -d '{"case_id":"DEV_MOUTH_001"}' \
  -o /tmp/interaction-preview.zip
```

手动参数示例，可通过 Swagger 输入或保存到 JSON 后运行
`tools/run_local_preview.py --request <文件路径>`：

```json
{
  "case_id": "DEV_MOUTH_001",
  "placement": {
    "center_x": 0.51,
    "center_y": 0.62,
    "width_ratio": 0.13,
    "rotation_degrees": 3
  },
  "product_view_id": "FRONT_00",
  "core_inset_px": 4,
  "contact_radius_px": 12,
  "occlusion_polygons": []
}
```

坐标原点在左上，center_x/y 为归一化坐标；width_ratio 是完整商品图层画布宽度与
Base 宽度之比，包含源图透明边缘；正角度逆时针旋转。所有图层使用同一仿射矩阵。
遮挡多边形使用 Base 上的归一化坐标，交集内恢复 Base 像素，用于手工保留前景手指等。
默认不自动推断嘴唇/手指遮挡，Near-mouth 同样不自动添加咬合遮挡。

参数范围用于防止无效输入和超大计算，不是已验证的生产安全窗口。

## 导出内容与保证

- `preview.png`：本地 RGBA 叠加，应用手动遮挡。
- `layers/`：统一位置的 RGBA、16 位 Depth、Normal、Transmission、Specular。
  Normal 只做空间重采样，通道保持源坐标系；这些诊断图层尚未用于折射或重打光。
- `masks/`：`M_product`、`M_core`、`M_transition`、`M_contact`、`M_occlusion`、
  `M_visible_core`，均为 0/255 灰度 PNG，255 表示包含。
- `manifest.json`：归一化参数、源文件 SHA256、实现和几何代码 SHA256、运行库版本、
  仿射矩阵、角度残差、输出 SHA256、未验证事项。

`M_contact` 是商品边界附近的几何带，不是经过语义分割的嘴唇/手指接触区。
`preserve_regions` 可在后续模型输出后恢复可见商品核心、手动遮挡区以及接触带外的
预合成像素；本轮使用人为改色图验证其像素约束，未调用模型。

每次运行重新验证 Development 封存引用和所选商品五图层的哈希。
非法参数返回 422，不存在的 Case/视图返回 404；角度残差超限、商品越界或可见核心
为空返回 409；缺失/损坏素材返回 503。错误不输出文件系统路径。

## 当前验证与限制

全部 30 个 Development 案例已执行本地渲染检查：29 个生成预览，1 个按规则阻断。
`DEV_MOUTH_011` 的实测姿态约为 yaw -45.712°、pitch 11.727°，现有视图不能同时满足
yaw ≤12°、pitch ≤8° 的残差初值；需后续新增匹配的商品视图版本。
这不是图像质量通过率，不改变已经封存的输入准入结论；固定 G2 的 12 个案例不含该项。

三类示例和可核验清单保存在 `docs/development/local-preview-v1/`。
嘴部/手部接触修补、透明材质合成、定位精度/Proximity Gate、自动遮挡和五维 QC
仍待完成。模型测试和正式准入保持待办，本轮不宣称 G2/G3 通过。
