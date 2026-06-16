# 运维知识库样本数据（Sample）

> 用途：数据质量参考样本，展示高质量 FAQ 对的格式标准
> 注意：本文件 **不会** 自动导入知识库，仅供数据工程师与其他成员参考
> 最后更新：2026-06

---

## 样本说明

以下 10 条 FAQ 严格对齐「课题六：运维数字员工」要求，包含：

- 课题原文示例（账号冻结 + URL + 热线）
- 运维门户账号 CRUD 场景
- 常见故障（网络、服务、数据库）
- 具体实体：URL、命令、HTTP 状态码

导入知识库时，等效内容已写入 `ops_docs/account-management.md` 等文档，**请勿重复手动添加**。

---

## FAQ 样本（10 条）

### 1. 账号冻结（课题原文示例）

**问题**：账号冻结怎么处理？

**答案**：通过自助方式访问网址 http://XXX.YYY.ZZZ 进行账号解冻，或拨打运维服务热线 400-8800-1234（工作日 8:30–18:00）申请人工解冻。冻结通常由长期未登录、密码多次错误或安全策略触发，与临时「锁定」（约 30 分钟）不同，冻结需主动解冻。

**元数据**：`source: account-management | type: FAQ | category: 账号管理 | date: 2026-06`

---

### 2. 密码重置

**问题**：忘记密码如何重置？

**答案**：访问 http://XXX.YYY.ZZZ/password-reset ，通过企业微信扫码或短信验证码验证身份后设置新密码。密码须至少 8 位，包含大小写字母、数字、特殊符号中至少三类，且不能与最近 5 次密码相同。无法自助时拨打 400-8800-1234。

**元数据**：`source: account-management | type: FAQ | category: 账号管理 | date: 2026-06`

---

### 3. 创建运维账号

**问题**：如何创建运维人员账号？

**答案**：登录运维申告门户后台 →「系统管理 → 运维账号管理」→「新增账号」，填写用户名、密码、真实姓名、联系电话后保存。或通过 API：`POST /api/operators`，密码以 BCrypt 加密存储。须先完成《运维人员权限申请表》审批。

**元数据**：`source: account-management | type: FAQ | category: 账号管理 | date: 2026-06`

---

### 4. 冻结运维账号

**问题**：如何冻结离职运维人员的账号？

**答案**：后台「运维账号管理」搜索目标账号 → 点击「冻结」。系统执行软删除（isActive=false），账号无法登录但数据保留。API：`DELETE /api/operators/{id}`。须在工单中记录冻结原因与操作人。

**元数据**：`source: account-management | type: FAQ | category: 账号管理 | date: 2026-06`

---

### 5. 网络连接失败

**问题**：网络连接失败怎么排查？

**答案**：按层次排查：① `curl -v URL` 看 HTTP 状态码（500/502/504）；② `telnet IP 端口` 测 TCP；③ `ping IP` 测网络层；④ `ipconfig`/`ifconfig` 确认本机 IP。常见原因：网线松动、DNS 故障、防火墙阻断、VPN 未连接。

**元数据**：`source: common-fault-handling | type: FAQ | category: 故障处理 | date: 2026-06`

---

### 6. 服务无法启动

**问题**：Nginx 服务启动失败怎么处理？

**答案**：执行 `systemctl status nginx -l` 查看状态；`journalctl -u nginx -n 50` 查日志；`nginx -t` 检查配置语法；`ss -tlnp | grep :80` 查端口占用。常见原因：配置错误、端口冲突、磁盘满、权限不足。修复后 `systemctl restart nginx`。

**元数据**：`source: common-fault-handling | type: FAQ | category: 故障处理 | date: 2026-06`

---

### 7. 数据库连接超时

**问题**：应用报数据库连接超时（Connection timed out）怎么办？

**答案**：① `telnet DB_IP 3306` 测端口；② `mysql -h IP -u root -p -e "SELECT 1;"` 测登录；③ `SHOW PROCESSLIST` 查连接与锁；④ 检查 MySQL 是否运行：`systemctl status mysql`。常见原因：MySQL 未启动、防火墙阻断、连接池耗尽、网络抖动。

**元数据**：`source: common-fault-handling | type: FAQ | category: 故障处理 | date: 2026-06`

---

### 8. HTTP 502 错误

**问题**：访问系统出现 502 Bad Gateway 是什么原因？

**答案**：502 表示 Nginx 网关无法连接上游后端服务。排查：① `systemctl status` 检查后端 Java/Python 服务是否运行；② 查 Nginx 错误日志 `/var/log/nginx/error.log`；③ 确认 upstream 地址与端口正确；④ 后端恢复后 `systemctl restart nginx`。

**元数据**：`source: common-fault-handling | type: FAQ | category: 故障处理 | date: 2026-06`

---

### 9. 转人工工单

**问题**：数字员工无法回答我的问题，怎么转人工？

**答案**：在聊天界面点击「转人工」，或当机器人回复含「无法处理」「转人工」时系统自动创建工单（status=pending）。系统记录你的原始问题与机器人回答，运维人员会在 2 小时内电话回访。处理完成后答案自动写入知识库，下次类似问题可直接回答。

**元数据**：`source: common-fault-handling | type: FAQ | category: 故障处理 | date: 2026-06`

---

### 10. 知识库数据飞轮

**问题**：运维人员处理完工单后，知识库会自动更新吗？

**答案**：会。运维人员在后台填写 resolution 并提交 `POST /api/tickets/{id}/resolve` 后，Java 后端自动调用 `POST http://127.0.0.1:8000/api/kb/add` 将（用户问题, 标准答案）写入 ChromaDB 向量库（BGE-M3）。默认开启语义去重（相似度 ≥ 90% 跳过），避免重复入库。

**元数据**：`source: system-operation-manual | type: FAQ | category: 系统操作 | date: 2026-06`

---

## 格式规范（数据工程师参考）

| 要素 | 要求 |
|------|------|
| 问题 | 自然语言问句，含「怎么」「如何」等 |
| 答案 | 步骤化（1/2/3 或命令块），含具体 URL/命令/状态码 |
| 层级 | `#` 文档标题 → `##` 章节 → `###` 切片边界 |
| 元数据 | source、type、category、date |
| 实体 | URL（http://XXX.YYY.ZZZ）、命令（systemctl restart）、状态码（Error 500/502） |
