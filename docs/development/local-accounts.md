# 本地账号与权限

默认 `AUTH_MODE=authenticated`。本机 HTTP 使用 HttpOnly、SameSite=Strict 会话 Cookie；
非 development 环境强制认证和 `SESSION_COOKIE_SECURE=true`（HTTPS）。
`AUTH_MODE=local` 仅用于显式本地无认证调试/遗留测试，不是本地版交付配置。

密码使用随机盐 PBKDF2-HMAC-SHA256 600000 次。服务端仅保存密码派生值和会话 token 的 SHA256，
原始 token 仅在 Cookie 中；会话 8 小时过期、退出可撤销、改密撤销全部会话、停用账号立即阻断后续访问。
写请求要求 `X-Studio-Request: 1`，浏览器 Origin 必须匹配，未开放 CORS。

`/api/v1/auth`：login、me、logout、password、users（管理员）、users/{id}/status（管理员）、events（管理员）。
账号名 3–64 位，密码至少 12 位。不能停用当前账号；不允许 ADMIN 和 GATE_SIGNER 同时赋予一个账号。
账号角色创建后不提供直接变更接口；如需调整可停用旧账号、建立独立账号。

应用层对 Development 的全部素材、图像、任务和审核入口执行认证；只读角色禁止所有修改。
OPERATOR 可以编辑/提交和做开发 QC，REVIEWER 可以做开发 QC；管理员不自动获得内容操作权限。
首次生成账号显式具有 ADMIN/OPERATOR/AUDITOR。CUSTODIAN/GATE_SIGNER 仅预留角色名，正式动作仍未实现。

草稿事件和 QC 内容哈希链记录真实账号 ID；新模板与任务记录创建者。历史 LOCAL_DEVELOPER 数据保留原身份，
不伪造迁移前的操作者。安全事件记录登录、退出、账号创建/启停和密码更改，不保存密码或 Cookie。
安全事件表没有宣称 WORM/独立签名。当前无 MFA/SSO/公网流量限速；本地交付保持回环监听。

管理员命令（密码通过隐藏输入，不放进命令参数）：

```bash
docker compose run --rm --no-deps api python -m interaction_studio_api.accounts \
  --username new_operator --roles OPERATOR
```

角色负向、会话、CSRF、账号唯一、角色分离、锁定、真实身份和撤销见 `apps/api/tests/test_auth.py`。
