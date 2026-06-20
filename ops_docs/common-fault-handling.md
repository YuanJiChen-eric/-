# 常见故障处理手册

> 适用范围：运维申告门户 · 一线报障场景 FAQ
> 最后更新：2026-06
> 文档类型：故障处理 | source: common-fault-handling

---

## 一、服务无法启动

### 1.1 应用服务启动失败怎么排查

**现象**：执行 `systemctl start <service>` 后服务状态为 `failed`，或启动后立即退出。

**排查步骤**：

```bash
# 1. 查看服务状态
systemctl status nginx -l

# 2. 查看最近日志（最关键）
journalctl -u nginx -n 50 --no-pager

# 3. 检查配置文件语法
nginx -t          # Nginx
java -jar app.jar --spring.config.location=...  # Java 应用

# 4. 检查端口占用
ss -tlnp | grep :8080

# 5. 检查磁盘与权限
df -h
ls -la /var/log/nginx/
```

**常见原因与处理**：

| 原因 | 现象 | 处理 |
|------|------|------|
| 配置文件错误 | 日志含 `syntax error` | 修正配置后 `systemctl restart` |
| 端口被占用 | `Address already in use` | `kill` 占用进程或改端口 |
| 磁盘满 | `No space left on device` | 清理日志，`df -h` 确认 |
| 权限不足 | `Permission denied` | `chown`/`chmod` 修正目录权限 |
| 依赖服务未启动 | `Connection refused` | 先启动 MySQL/Redis 等依赖 |

**重启命令**：

```bash
systemctl restart nginx
systemctl restart mysql
systemctl restart redis
```

---

### 1.2 Docker 容器无法启动

**现象**：`docker ps` 看不到容器，或状态为 `Exited`。

**排查步骤**：

```bash
# 查看容器状态与退出码
docker ps -a

# 查看容器日志（最重要）
docker logs <container_id> --tail 100

# 查看退出码含义
# 0=正常退出  1=应用错误  137=OOM被杀  139=段错误  143=SIGTERM
```

**处理**：

```bash
# 重新启动
docker start <container_id>

# 若反复失败，检查资源
docker stats
docker inspect <container_id> | grep -A5 State
```

---

### 1.3 Java Spring Boot 应用启动失败

**现象**：日志出现 `Application run failed` 或端口绑定失败。

**排查步骤**：

```bash
# 查看启动日志
tail -f /var/log/app/application.log

# 常见错误关键字搜索
grep -E "Error|Exception|Failed" application.log | tail -20
```

**常见错误**：

| 错误信息 | 原因 | 处理 |
|----------|------|------|
| `Communications link failure` | MySQL 未启动或网络不通 | 检查 MySQL 状态与 `application.yaml` 连接串 |
| `Port 8082 was already in use` | 端口冲突 | `lsof -ti:8082 \| xargs kill -9` |
| `BeanCreationException` | 配置错误或依赖缺失 | 检查 YAML 配置与 Maven 依赖 |
| `Table doesn't exist` | 数据库表未创建 | 确认 JPA `ddl-auto=update` 或手动建表 |

---

## 二、数据库连接故障

### 2.1 数据库连接超时怎么处理

**现象**：应用日志出现 `Connection timed out`、`Communications link failure` 或 `wait_timeout exceeded`。

**排查步骤**：

```bash
# 1. 测试 MySQL 端口连通
telnet 192.168.1.100 3306
# 或
nc -zv 192.168.1.100 3306

# 2. 测试 MySQL 登录
mysql -h 192.168.1.100 -u root -p -e "SELECT 1;"

# 3. 查看 MySQL 当前连接数
mysql -e "SHOW STATUS LIKE 'Threads_connected';"
mysql -e "SHOW VARIABLES LIKE 'max_connections';"

# 4. 查看慢查询与锁
mysql -e "SHOW PROCESSLIST;"
```

**常见原因与处理**：

| 原因 | 处理 |
|------|------|
| MySQL 服务未启动 | `systemctl start mysql` |
| 防火墙阻断 3306 | `firewall-cmd --add-port=3306/tcp --permanent` |
| 连接池耗尽 | 增大 `max_connections`，优化连接池 `maxActive` |
| 网络抖动 | 检查交换机/路由，增加连接超时重试 |
| 账号权限不足 | `GRANT` 授权或重置密码 |

**JDBC 连接串参考**：

```
jdbc:mysql://localhost:3306/ops_db?useSSL=false&serverTimezone=UTC&allowPublicKeyRetrieval=true&characterEncoding=UTF-8
```

---

### 2.2 数据库连接数过多（Too many connections）

**现象**：报错 `ERROR 1040 (HY000): Too many connections`。

**处理步骤**：

```bash
# 查看当前连接
mysql -e "SHOW PROCESSLIST;"

# 终止长时间空闲连接
mysql -e "SELECT id FROM information_schema.processlist WHERE Command='Sleep' AND Time > 300;"
# kill <id>

# 临时增大连接数
mysql -e "SET GLOBAL max_connections = 500;"
```

**根本解决**：优化应用连接池配置，排查慢查询导致连接长时间占用。

---

### 2.3 Redis 连接失败

**现象**：`Could not connect to Redis`、`Connection refused` 或 `NOAUTH Authentication required`。

**排查**：

```bash
redis-cli -h 127.0.0.1 -p 6379 ping
# 期望返回 PONG

systemctl status redis
redis-cli info clients
```

**处理**：

```bash
systemctl restart redis
# 若需密码
redis-cli -a <password> ping
```

---

## 三、网络连接故障

### 3.1 网络连接失败怎么排查

**现象**：无法访问内网系统、VPN 连不上、网页打不开。

**标准排查顺序**（由近到远）：

```
应用层：curl -v http://目标URL  → 看 HTTP 状态码（500/502/504）
传输层：telnet IP 端口          → 看 TCP 是否通
网络层：ping IP                 → 看 IP 层是否通
链路层：ipconfig / ifconfig     → 看是否获取到 IP
```

**常用命令**：

```bash
# 查看本机 IP
ip addr show | grep inet

# 测试网关
ping -c 4 192.168.1.1

# 测试外网
ping -c 4 8.8.8.8

# DNS 解析测试
nslookup portal.company.com
dig portal.company.com

# HTTP 详细测试
curl -v --connect-timeout 5 http://portal.company.com
```

---

### 3.2 VPN 连接失败

**现象**：VPN 客户端提示「连接超时」「认证失败」或频繁掉线。

**处理步骤**：

1. 确认外网正常（手机热点测试）
2. 更新 VPN 客户端到最新版本
3. 切换 VPN 协议：UDP → TCP
4. 更换接入节点（广州/深圳/北京）
5. 确认 VPN 账号未过期：`curl http://XXX.YYY.ZZZ/vpn-status`

**仍无法连接**：拨打 **400-8800-1234** 或提交工单。

---

### 3.3 HTTP 错误码速查

| 状态码 | 含义 | 常见原因 | 处理方向 |
|--------|------|----------|----------|
| 500 Internal Server Error | 服务端内部错误 | 应用 Bug、未捕获异常 | 查应用日志 |
| 502 Bad Gateway | 网关无法连接上游 | Nginx 后端服务宕机 | `systemctl status` 后端服务 |
| 503 Service Unavailable | 服务不可用 | 过载、维护中 | 检查负载与限流 |
| 504 Gateway Timeout | 网关超时 | 后端响应慢 | 查慢查询、增加超时时间 |
| 401 Unauthorized | 未认证 | Token 过期 | 重新登录 |
| 403 Forbidden | 无权限 | 账号权限不足 | 申请权限开通 |

---

## 四、运维申告与转人工

### 4.1 数字员工无法回答时怎么转人工

**现象**：聊天机器人回复「抱歉，我暂时无法处理该问题」或提示转人工。

**用户操作**：

1. 在聊天界面点击「转人工」按钮
2. 或继续描述问题，系统自动创建工单（status=pending）
3. 记录工单编号，等待运维人员电话回访

**系统自动行为**：

- 保存用户原始问题（userQuestion）
- 保存机器人回答（botResponse）
- 创建 TroubleTicket，状态 `pending`
- 前端收到 `transfer_to_human` 事件

---

### 4.2 运维人员如何处理待办工单

**后台操作步骤**：

```
1. 登录运维申告门户后台
2. 进入「工单管理 → 待处理工单」
   API: GET /api/tickets/pending
3. 查看用户问题与机器人回答
4. 电话回访报障人，确认问题并给出解决方案
5. 在后台填写 resolution（标准答案）并提交
   API: POST /api/tickets/{id}/resolve
   Body: {"resolution": "...", "operatorId": 1}
6. 系统自动将 (问题, 标准答案) 写入知识库（数据飞轮）
```

**知识库同步**：

```
POST http://127.0.0.1:8000/api/kb/add
{"question": "用户原始问题", "answer": "人工标准答案", "skip_if_duplicate": true}
```

---

### 4.3 如何查询历史在线记录

**运维人员定期查询机器难以处理的记录**：

1. 后台「工单管理」筛选 `status=pending` 的工单
2. 按创建时间排序，优先处理超时未处理工单（建议 2 小时内响应）
3. 处理完成后工单状态变为 `resolved`
4. 答案自动入库，下次类似问题可由数字员工直接回答
