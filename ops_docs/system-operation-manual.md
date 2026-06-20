# 运维申告门户系统操作手册

> 适用范围：中国电信广东公司 · 运维数字员工平台
> 最后更新：2026-06
> 文档类型：系统操作 | source: system-operation-manual

---

## 一、系统概述

### 1.1 平台架构与端口说明

本系统由三个服务组成，部署在同一台 PC（4C8GB）上：

| 服务 | 端口 | 技术栈 | 职责 |
|------|------|--------|------|
| 运维申告门户（Java 后端） | **8082** | Spring Boot + MySQL | 账号管理、工单、聊天代理 |
| 知识库服务（kb_service） | **8000** | FastAPI + ChromaDB + BGE-M3 | 向量检索、知识入库 |
| RAG 问答服务 | **8001** | FastAPI + LangChain + Ollama | 大模型问答生成 |
| MySQL 数据库 | **3306** | MySQL 8.x | 持久化存储 `ops_db` |

**数据流**：

```
用户提问 → Java /api/chat (SSE)
         → RAG 服务 /api/rag (8001)
         → 检索知识库 + 大模型生成答案
         → 流式返回前端

工单处理完成 → Java TicketController
            → kb_service /api/kb/add (8000)
            → ChromaDB 向量库更新（BGE-M3）
```

---

### 1.2 启动与停止服务

**启动顺序**（建议）：

```bash
# 1. 确认 MySQL 运行
mysqladmin -u root -p ping

# 2. 启动知识库服务
cd kb_service
HF_ENDPOINT=https://hf-mirror.com python3 main.py

# 3. 启动 RAG 服务（另开终端）
cd <项目根目录>
uvicorn api_server:app --host 0.0.0.0 --port 8001

# 4. 启动 Java 后端（另开终端）
./mvnw spring-boot:run
```

**健康检查**：

```bash
curl http://127.0.0.1:8000/api/kb/health    # 知识库
curl http://127.0.0.1:8001/health           # RAG
curl http://127.0.0.1:8082/api/operators    # Java 后端
```

**停止服务**：

```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:8001 | xargs kill -9
lsof -ti:8082 | xargs kill -9
```

---

## 二、前台用户操作

### 2.1 自助查询运维问题

**操作步骤**：

1. 打开运维申告门户聊天界面
2. 在输入框描述问题（如「账号冻结了怎么办」）
3. 系统调用 RAG 服务，结合知识库生成回答
4. 答案以流式打字机效果逐字显示

**API 接口**（供前端联调）：

```http
POST /api/chat
Content-Type: application/json

{"query": "账号冻结了怎么办"}
```

响应：`text/event-stream`（SSE 流式）

---

### 2.2 提交工单申告

**适用场景**：数字员工无法回答、需要人工介入。

**操作**：

1. 聊天中收到「转人工」提示，或主动点击「转人工」
2. 系统自动创建工单，记录问题与机器人回答
3. 记录工单 ID，等待运维人员回访

**工单字段说明**：

| 字段 | 说明 |
|------|------|
| userQuestion | 用户原始提问 |
| botResponse | 机器人当时的回答 |
| status | pending（待处理）/ resolved（已处理） |
| resolution | 运维人员填写的标准答案 |
| operatorId | 处理人工号 |

---

## 三、后台运维操作

### 3.1 运维账号管理

详见《运维账号与自助服务管理手册》第二章。

**快速入口**：

- 创建账号：`POST /api/operators`
- 冻结账号：`DELETE /api/operators/{id}`
- 修改账号：`PUT /api/operators/{id}`
- 查询账号：`GET /api/operators`

---

### 3.2 待处理工单查询与处理

**查询待处理工单**：

```bash
curl http://127.0.0.1:8082/api/tickets/pending
```

**处理工单并同步知识库**：

```bash
curl -X POST http://127.0.0.1:8082/api/tickets/1/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution": "访问 http://XXX.YYY.ZZZ 自助解冻，或拨打 400-8800-1234", "operatorId": 1}'
```

处理完成后，系统自动调用 `http://127.0.0.1:8000/api/kb/add` 将问答写入知识库。

---

### 3.3 知识库维护操作

**查看知识库条数**：

```bash
curl http://127.0.0.1:8000/api/kb/count
```

**搜索测试**：

```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Nginx 502错误", "top_k": 5}'
```

**手动添加知识**：

```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/add \
  -H "Content-Type: application/json" \
  -d '{"question": "新问题", "answer": "标准答案", "skip_if_duplicate": true}'
```

**一键重建知识库**（数据工程师操作）：

```bash
cd kb_service
python3 rebuild_kb.py
# 预期：种子 FAQ + ops_docs 文档切片全部重新导入
```

---

## 四、知识库数据管理

### 4.1 数据来源说明

| 来源 | 文件/脚本 | 条数（约） | 说明 |
|------|-----------|-----------|------|
| 种子 FAQ | `kb_service/seed_data.py` | 500+ | 10 大类运维 FAQ |
| 运维文档 | `ops_docs/*.md` | 按 ### 切片 | 结构化 Markdown 文档 |
| 工单反馈 | TicketController 自动入库 | 动态增长 | 数据飞轮 |

**ops_docs 文档清单**：

- `account-management.md` — 账号管理
- `common-fault-handling.md` — 常见故障
- `system-operation-manual.md` — 系统操作（本文档）
- `nginx-troubleshooting.md` — Nginx 排错
- `docker-operations.md` — Docker 运维
- `mysql-maintenance.md` — MySQL 维护
- `linux-system-admin.md` — Linux 系统管理
- `redis-operations.md` — Redis 运维
- `network-troubleshooting.md` — 网络排错
- `backup-recovery.md` — 备份恢复
- `incident-response.md` — 故障响应

---

### 4.2 新增运维文档的标准格式

**格式要求**（便于 RAG 切片）：

```markdown
# 文档标题

> source: 文档标识 | 最后更新：YYYY-MM

## 一、章节标题

### 1.1 子标题（切片边界）

**现象**：描述问题现象

**排查步骤**：
1. 第一步
2. 第二步

**处理命令**：
```bash
systemctl restart nginx
```

**常见错误码**：Error 500、502
```

**切片规则**：`rebuild_kb.py` 按 `###` 三级标题切分，每个块转为自然语言问句后入库。

---

### 4.3 数据飞轮机制

```
用户提问 → 数字员工回答（置信度低）
         → 自动创建 pending 工单
         → 运维人员电话回访 + 填写 resolution
         → POST /api/tickets/{id}/resolve
         → 自动 POST /api/kb/add（语义去重 threshold=0.90）
         → 下次类似问题可被检索到
```

**去重机制**：相似度 ≥ 90% 的已有记录跳过新增，避免知识库膨胀。
