# Interaction Studio 本地可用版交付

> 登录页已恢复独立入口，采用企业 SaaS 视觉风格，见 [设计纠正记录](login-standalone-design.md)。登录提交及错误提示已修复，见 [登录验证记录](login-submit-fix.md)。

> 商品素材新增“结构修正版”，修复正面吸嘴凸起并加入基础接触阴影；当前材质仍未达到照片级真实感。见 [修正与限制](product-structure-fix.md)。请使用 v1.0.5 交付包。
用户已确认本次范围：**先交付本地可用版本，模型继续暂缓**。
本包面向同一台电脑上的素材编辑、本地合成、任务处理和人工 QC；不是正式生产模型或 Formal 验收交付。

## 打开与登录

1. 同机部署打开 `http://127.0.0.1:8000/`。当前 mydevServer 远程部署使用
   [固定内网入口](http://192.168.11.91:8000/#/dashboard)，见[连接诊断与配置](../prototype-alignment/remote-preview.md)。
2. 初始账号为 `studio_owner`；密码见本机 `data/local-delivery/initial-login.txt`。
   该文件仅当前操作系统用户可读，不进入源码包和 Git。
3. 登录后可在“账号设置”修改密码、创建独立账号、启用/停用账号及查看近期安全记录。
4. 技术管理员负责账号管理；内容操作员可以编辑、提交任务和进行开发 QC；审核员可以读取结果和进行开发 QC；
   只读审计账号只能读取。技术管理员不能兼任 Gate 签署人。正式 Custodian/Gate 流程仍未开放。

修改密码会退出所有会话，退出登录前请保存草稿和审核内容。
会话有效期 8 小时；连续登录失败 5 次锁定 15 分钟。页面提示会话过期时，可刷新并重新登录。

## 一次完整操作

1. 从左侧选择一个 Development Case，可按交互类型、姿态或编号筛选。
2. 选择商品视图，在画布拖动、缩放、旋转；必要时绘制遮挡多边形。调整支持撤销/重做。
3. 保存草稿。可将参数保存为模板，之后加载历史版本或同交互模板。
4. 点击本地预览，检查商品和遮罩；预览不调用任何模型。
5. 在“处理任务与 QC”点击“提交当前参数”。任务保存独立参数副本，关闭页面后继续处理。
6. 成功后进入“查看结果 / QC”，对照原图判定产品、交互、身份、场景、整体五项。
   未通过必须写原因；五项全部明确通过才记为开发 PASS。每次修改保存新版本。
7. 下载结果 ZIP、可校验证据包或任务/审核 JSON。

`DEV_MOUTH_011` 的现有商品视图残差超限，会正常显示失败；调整前不会输出不符合几何约束的结果。
本地成功渲染数量不是质量通过率。手工合成尚不具备模型接触修补、材质重打光或自动语义遮挡。

## 安装和升级

需要 Docker Engine + Compose、Python 3.12，以及足够存放图片、镜像和数据库的磁盘空间。
先校验交付包旁的 SHA256 文件，解压到一个新目录。在该目录运行：

```bash
python3 tools/install_local_studio.py
```

脚本会构建镜像、启动依赖、迁移数据库、在空账号库创建初始账号，并启动 API/独立 worker。
重复执行保留数据库、已有账号和密码。已有旧版数据升级前先按下节备份。
默认 API 和 MinIO 仅监听 `127.0.0.1`，PostgreSQL/Redis 不对主机开放端口。

基础运维：

```bash
docker compose ps
docker compose logs --tail 100 api studio-worker
docker compose stop api studio-worker
docker compose up -d api studio-worker
```

需要离线校验/备份工具时，先运行 `make api-install` 安装锁定的 Python 工具环境。
生产 HTTPS/公网、SSO、正式权限和安全验收不属于本地版交付；不要将默认配置直接开放到公网。

## 备份、校验与恢复

已保存当前项目的加密备份：`data/backups/local-delivery-20260905/`。
备份密钥单独放在 `data/backup-keys/local-backup.key`（权限 600）；密钥不包含在备份包或源码包中。
备份包括完整 PostgreSQL 数据库和 141 个输入/封存相关文件，数据库内含账号、草稿、任务、结果和审核。
请将密钥与备份分开保管；没有密钥无法恢复。**当前未配置自动定时备份**，重要操作后手动执行：

```bash
.venv/bin/python tools/studio_backup.py backup \
  --key-file data/backup-keys/local-backup.key \
  --directory data/backups/新的备份目录

.venv/bin/python tools/studio_backup.py verify \
  --key-file data/backup-keys/local-backup.key \
  --directory data/backups/新的备份目录

.venv/bin/python tools/studio_backup.py drill \
  --key-file data/backup-keys/local-backup.key \
  --directory data/backups/新的备份目录
```

`drill` 创建隔离数据库和素材目录，验证封存、草稿链、模板、结果、审核、证据重放及实际 HTTP 权限；
完成后清理临时恢复数据，不替换当前数据库。

实际需要取回数据时，将 `drill` 换成 `recover`。它会保留新建的恢复数据库和
`data/recoveries/<恢复库名>/`，其中 `.env.recovery` 保存对应连接配置，`assets/` 保存恢复素材。
它不会自动切换线上数据库。核对恢复报告后，停止 API/worker，将恢复连接配置应用到本机 `.env`，
如素材丢失则从恢复目录恢复对应素材，再启动服务。原数据库保持保留，可供核对或回退。
不要对正常项目使用 `docker compose down -v`；该命令会删除数据库卷。

加密方案：AES-256-CBC + PBKDF2-SHA256（200000 次）并对密文清单使用 HMAC-SHA256。
校验 HMAC 和密文哈希后才解密。此实现用于本地备份，不宣称正式 WORM/PITR、异地容灾或 RPO/RTO 达标。

## 证据校验

```bash
.venv/bin/python tools/verify_studio_evidence.py 下载的-evidence.zip
```

离线校验包括结果 ZIP、任务参数/来源、结果内各文件哈希及审核版本链。
证据包不内嵌所有输入素材，输入通过封存哈希关联；完整输入保存在交付源码包和加密备份中。
本地证据可发现意外修改，但不等同 Object Lock、签名或生产验收凭证。

## 已验证与边界

- 后端 142 项测试通过；前端 6 项既有逻辑测试、类型/格式检查和生产构建通过。
- PostgreSQL HTTP 联调覆盖登录、只读拦截、退出撤销、重复提交、并发任务领取、QC 版本冲突和离线证据重放。
- 当前项目恢复报告：[live-restore-drill.json](live-restore-drill.json)。原项目当前无任务记录，报告如实记录 0 条。
- 有样本恢复报告：[populated-restore-drill.json](populated-restore-drill.json)：包含草稿、2 个模板、2 个任务结果、1 份 QC 和账号。
- 独立安装报告：[cleanroom.json](cleanroom.json)，使用全新 Compose 项目、数据库卷和自动分配的本地端口。
- 无模型 API 调用；不计入 Formal/G2/G3 通过。正式模型、Object Lock、生产容量/保留策略等留到后续阶段。
- **未进行浏览器点击/视觉验收。** 本次交付验证为自动化逻辑、真实 HTTP、容器运行、恢复和隔离安装。
  首次使用请按上面的完整操作步骤检查画布、登录和审核体验；发现问题可继续修复。

更多接口说明见 `docs/development/studio-workbench.md` 和 `docs/development/studio-jobs-qc.md`。
