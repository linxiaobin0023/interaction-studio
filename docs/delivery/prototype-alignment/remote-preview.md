# 远程页面无法访问：诊断与固定入口 — 2026-09-07

## 已证实的问题

用户截图为 `ERR_CONNECTION_REFUSED`：桌面浏览器连接本机临时端口失败，尚未进入
HTTP 或 React 加载阶段。远程项目位于 mydevServer，服务器网卡地址为
`192.168.11.91`；桌面 localhost 与服务器 localhost 不是同一个网络端点。
此前将桌面临时端口 58307 当成远程服务目标再次打开，是错误的处理。
增加兼容端口、修改脚本路径或刷新参数均不能修复桌面上没有可用监听的连接。

远程应用可正常提供首页和业务接口，SSH 有效配置允许 TCP 转发，授权密钥没有
转发限制。当前工具不能读取桌面转发进程或内置浏览器的网络记录，因此不能进一步
断言客户端转发为何未建立或退出，也不能把工具的 queued 响应作为访问成功证据。

## 当前持久配置

固定入口：[Interaction Studio](http://192.168.11.91:8000/#/dashboard)。
该入口直接访问服务器内网地址，避免依赖桌面临时 localhost 端口。

- `.env` 的 `STUDIO_LAN_HOST=192.168.11.91` 仅控制 API 的内网监听。
- `compose.override.yaml` 随默认 Compose 命令自动加载；保留服务器 IPv4/IPv6
  回环入口。通用 `APP_BIND_HOST` 保持 `127.0.0.1`，MinIO 不随 API 对内网开放。
- API、数据库、Redis、MinIO 和 worker 均配置 `restart: unless-stopped`，
  避免 Docker 重启后只恢复 worker。未进行主机重启测试。
- 安装脚本从运行容器的全部端口映射生成地址，优先输出具体内网 IP；
  不再只取 `docker compose port` 返回的第一个回环地址。
- 旧 `compose.preview.yaml` 已退出使用，58307 兼容入口已移除。

常规更新使用 `docker compose up -d` 即可保留此配置，不需要附加预览配置文件。
这台服务器的固定入口要求客户端能够路由到上述内网 IP；服务器 IP 改变时也需要更新配置。

## 验证与边界

独立 Docker 网络容器通过内网 IP 请求首页、JS、CSS 均成功；匿名业务接口返回401。
服务器上的 Chromium 使用同一内网入口完成认证会话、生产概览、各导航页、编辑器
图片加载、退出登录和登录页布局检查，未记录 JavaScript 异常。
浏览器验证不修改业务草稿或审核记录。报告见 `private-entry-browser-report.json`。

这些结果证明固定入口在服务器侧可访问、页面可运行。已请求 Codex 打开固定入口，
但工具只返回 queued，尚未取得用户桌面实际加载成功的证据，不能宣称端到端验收完成。

此前添加的启动提示、React 错误边界、相对静态资源路径及首页 HEAD 支持仍保留，
故障模拟见 `startup-report.json`；它们改善加载失败提示，不是此次 TCP 拒绝连接的根因修复。
