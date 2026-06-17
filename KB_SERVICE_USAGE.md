# 运维知识库服务（kb_service）使用文档

> 成员 C（数据工程师 & 知识库运营）| 更新时间：2026-06-17
>
> **最新完整指南**：请参阅 [`kb_service/README.md`](kb_service/README.md)（含第三～五阶段脚本说明）

---

## 一、这是什么？

一个基于 **ChromaDB + BGE-M3 向量检索** 的运维知识库服务，用 Python FastAPI 编写，运行在 `8000` 端口。

**核心能力**：把运维工单的处理结果存成向量，当遇到相似问题时能秒级检索出历史答案。

**技术栈**：
- Python 3.12 + FastAPI
- ChromaDB（向量数据库，持久化目录 `chroma_kb_store/`）
- BGE-M3（1024 维中文语义向量，ModelScope 国内镜像下载）
- 数据流水线：`data_clean.py` → `ingest.py` → `rebuild_kb.py`

---

## 二、文件结构与作用

> 成员 C 新增 / 修改的所有文件及其职责说明。

### kb_service/（知识库服务 — 核心目录）

| 文件 | 作用 | 谁需要关心 |
|------|------|-----------|
| `main.py` | **FastAPI 服务主程序**。暴露 4 个 API 端点（health/count/search/add），集成去重逻辑。 | 成员 A、B |
| `chroma_store.py` | **ChromaDB 向量存储封装**。BGE-M3 Embedding、增删查、语义去重、持久化。 | 成员 C |
| `data_clean.py` | **Markdown 清洗**（第二阶段）。去噪、结构化、保护 URL/命令/状态码 → `ops_docs_clean/` | 成员 C |
| `ingest.py` | **切片入库**（第三阶段）。按 `###` 语义切分 + 元数据注入 + 向量化。 | 成员 C |
| `feedback_loop.py` | **反馈闭环演示**（第四阶段）。CSV 待处理队列 → 人工答案 → 自动入库。 | 成员 C |
| `download_model.py` | **BGE-M3 模型下载**（ModelScope 镜像，跳过 ONNX 大包）。 | 成员 C |
| `seed_data.py` | **种子 FAQ**（500+ 条，10 大类）。 | 成员 C |
| `rebuild_kb.py` | **一键重建**。清空 → 种子 FAQ → 导入 ops_docs_clean/。 | 成员 C |
| `import_ops_docs.py` | **在线 HTTP 导入**（备用，服务运行中时使用）。 | 成员 C |
| `requirements.txt` | Python 依赖（chromadb、sentence-transformers、modelscope 等）。 | 所有成员 |
| `README.md` | **全员运行指南**（第五阶段交付）。 | 所有成员 |

### chroma_kb_store/（向量索引持久化目录）

| 说明 |
|------|
| ChromaDB 本地持久化目录，包含 `ops_knowledge` 集合。 |
| 被 `.gitignore` 忽略，新机器需运行 `download_model.py` + `rebuild_kb.py` 重建。 |

> ⚠️ 请勿手动删除，除非要重建知识库。重建前需先停止 `main.py`。

### ops_docs/（运维文档库 — 知识原料）

| 文件 | 内容范围 | 切分块数 |
|------|---------|---------|
| `account-management.md` | 账号冻结/解冻、密码重置、运维账号 CRUD | ~15 块 |
| `common-fault-handling.md` | 服务无法启动、DB 超时、网络故障、转人工 | ~13 块 |
| `system-operation-manual.md` | 三服务架构、API 操作、数据飞轮 | ~11 块 |
| `nginx-troubleshooting.md` | Nginx 502/504、HTTPS、负载均衡 | ~12 块 |
| `docker-operations.md` | 容器/镜像管理、重启排查（exit code 0/1/137/139/143）、OOM 修复、磁盘清理、网络问题、Docker Compose | ~13 块 |
| `mysql-maintenance.md` | MySQL 连接、慢查询、主从复制、备份恢复、性能调优 | ~12 块 |
| `linux-system-admin.md` | 系统监控、进程管理、磁盘管理、用户权限、定时任务 | ~11 块 |
| `redis-operations.md` | Redis 内存管理、持久化、集群、哨兵、性能优化 | ~10 块 |
| `network-troubleshooting.md` | 网络连通性、DNS、防火墙、路由、抓包分析 | ~12 块 |
| `backup-recovery.md` | 备份策略、数据恢复、灾备演练 | ~10 块 |
| `incident-response.md` | 故障响应流程、升级机制、事后复盘 | ~12 块 |

> 共 11 份 Markdown 文档（含 3 份课题专用文档）。推荐流程：`data_clean.py` 清洗 → `rebuild_kb.py` 导入 `ops_docs_clean/`。按 `###` 三级标题切分并转化为自然语言问句后入库 ChromaDB。

### Java 后端（修改的文件）

| 文件 | 修改内容 | 原因 |
|------|---------|------|
| `application.yaml` | JDBC URL 加 `&characterEncoding=UTF-8` | 修复 MySQL 中文乱码（kb_505 乱码问题） |
| `TicketController.java` | 3 处修复：`localhost`→`127.0.0.1`、加 `UTF_8` 编码、强制 HTTP/1.1 | 修复 Java 调用 kb_service 时请求体丢失的 bug |

### 项目根目录

| 文件 | 作用 |
|------|------|
| `KB_SERVICE_USAGE.md` | **本文档**。所有组员的对接指南，接口说明，常见问题排查。 |

---

## 三、怎么启动？

### 前置条件
```bash
cd kb_service
pip3 install -r requirements.txt

# 下载 BGE-M3 模型（约 2.1GB，首次必须）
python3 download_model.py

# 清洗 + 重建知识库
python3 data_clean.py
python3 rebuild_kb.py
```

### 启动服务
```bash
cd /Users/keira/Desktop/project/-/kb_service
HF_ENDPOINT=https://hf-mirror.com python3 main.py
```

启动成功后会打印：
```
🚀 运维知识库服务启动中...
   端口: 8000
   健康检查: http://localhost:8000/api/kb/health
   知识库条数: 502
```

> ⚠️ **注意**：首次启动需要下载 Embedding 模型（约 80MB），请等待 1-2 分钟。

### 停止服务
```bash
lsof -ti:8000 | xargs kill -9
```

---

## 四、API 端点

### 4.1 健康检查 — `GET /api/kb/health`

```bash
curl http://127.0.0.1:8000/api/kb/health
```

响应：
```json
{
  "status": "ok",
  "service": "运维知识库服务",
  "records": 502
}
```

### 4.2 查看总条数 — `GET /api/kb/count`

```bash
curl http://127.0.0.1:8000/api/kb/count
```

### 4.3 搜索知识库 — `POST /api/kb/search`

**成员 A（算法/RAG架构师）和成员 B（后端工程师）主要用这个接口**。成员 A 用它检索 Top-K 相关知识喂给 DeepSeek/Qwen 做 RAG；成员 B 用它为前端提供智能推荐。

请求体：
```json
{
  "query": "Docker容器频繁重启怎么排查",
  "top_k": 5
}
```

调用示例：
```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Docker容器频繁重启", "top_k": 3}'
```

响应：
```json
{
  "query": "Docker容器频繁重启",
  "results": [
    {
      "id": "kb_12",
      "question": "Docker容器频繁重启如何排查？",
      "answer": "排查步骤：1) docker logs查看容器日志...",
      "score": 0.95,
      "document": "问题：Docker容器频繁重启如何排查？\n答案：排查步骤..."
    }
  ],
  "total_in_db": 502
}
```

- `score`：0~1 的相似度，越高越匹配
- `top_k`：最多返回多少条（1~20）
- `total_in_db`：知识库当前总条数

### 4.4 添加知识 — `POST /api/kb/add`

**成员 B（后端工程师）主要用这个接口**：工单处理完成后写入知识库，实现"处理完成后再自动完善知识库"的反馈闭环。

请求体：
```json
{
  "question": "用户原始问题",
  "answer": "人工修正后的正确答案",
  "skip_if_duplicate": true,
  "dedup_threshold": 0.90
}
```

调用示例：
```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/add \
  -H "Content-Type: application/json" \
  -d '{"question": "Redis内存满了怎么扩容？", "answer": "1) 设置淘汰策略maxmemory-policy..."}'
```

正常新增响应：
```json
{
  "success": true,
  "id": "kb_503",
  "message": "知识条目已入库 (ID: kb_503)",
  "duplicate": false,
  "score": 1.0,
  "existing_question": null
}
```

命中重复响应：
```json
{
  "success": true,
  "id": "kb_12",
  "message": "已存在相似记录 (相似度=92.58%, ID=kb_12)，跳过新增",
  "duplicate": true,
  "score": 0.9258,
  "existing_question": "Docker容器频繁重启如何排查？"
}
```

字段说明：
| 字段 | 类型 | 说明 |
|------|------|------|
| `question` | 必填 | 用户原始问题 |
| `answer` | 必填 | 正确答案 |
| `skip_if_duplicate` | 可选，默认 `true` | 是否开启语义去重 |
| `dedup_threshold` | 可选，默认 `0.90` | 相似度阈值（0.5~1.0） |
| `duplicate` | 响应 | 是否命中重复记录 |
| `score` | 响应 | 相似度分数 |

---

## 五、去重机制说明

**默认开启**，阈值 0.90（即语义相似度 ≥ 90% 就跳过）。

工作原理：
1. 收到新问题时，先在知识库中搜索最相似的 3 条记录
2. 如果有一条相似度 ≥ 阈值，则**跳过新增**，返回已有记录的 ID
3. 如果所有的相似度都 < 阈值，则正常入库

如果想强制添加（即使重复），传 `"skip_if_duplicate": false`。

---

## 六、成员对接指南

> 项目四人分工：
> - **成员 A**：算法与 RAG 架构师（大模型本地部署 + RAG 链路 + Prompt 工程）
> - **成员 B**：后端工程师 & 系统集成（FastAPI 后端 + 账号 CRUD + SSE 流式传输）
> - **成员 C**：数据工程师 & 知识库运营（知识库构建 + 反馈闭环 + 数据飞轮）
> - **成员 D**：前端开发与交互设计（聊天界面 + 管理仪表盘 + 可视化）

### 成员 A（算法/RAG架构师）— 对接检索接口

你的 RAG 链路（LangChain / LlamaIndex）需要调用 kb_service 的搜索接口，从知识库中检索 Top-K 条相关知识，注入到 Prompt 中喂给 DeepSeek / Qwen2.5。

调用方式：
```python
# Python 侧（LangChain Retriever 封装示例）
import requests

def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """从 kb_service 检索相关知识"""
    resp = requests.post(
        "http://127.0.0.1:8000/api/kb/search",
        json={"query": query, "top_k": top_k}
    )
    return resp.json()["results"]

# 在 LangChain 中使用
docs = retrieve_context(user_question, top_k=5)
context = "\n".join([f"Q: {d['question']}\nA: {d['answer']}" for d in docs])
prompt = f"""基于以下运维知识库参考：

{context}

用户问题：{user_question}
请根据上述参考资料回答，如果参考资料中没有相关信息，请明确说明。"""
```

关键参数建议：
- `top_k`: 3~5 条，太多会稀释 Prompt，太少可能漏掉相关信息
- 建议只取 `score >= 0.60` 的结果作为有效上下文，低于此阈值的丢弃

### 成员 B（后端工程师）— 反馈闭环 & 前端代理

你需要做两件事：

**1. 反馈闭环（POST /api/kb/add）**：当成员 A 的大模型回答了用户问题，运维人员修正后，你需要把修正后的 Q&A 写入知识库。参考现有 Java 实现：

```
POST http://127.0.0.1:8000/api/kb/add
Body: {"question": "...", "answer": "...", "skip_if_duplicate": true}
```

现有参考代码：`src/main/java/.../TicketController.java` 的 `syncToKnowledgeBase()` 方法（虽然是 Java 写的，但逻辑可以移植到你的 FastAPI 后端）。

关键注意事项：
- 必须用 `127.0.0.1`，不用 `localhost`（macOS IPv6 优先解析问题）
- 请求体编码用 UTF-8
- HTTP 协议版本用 HTTP/1.1

**2. 前端代理**：前端的聊天界面需要通过你的后端 API 获取知识库搜索结果。你可以在 FastAPI 中加一个代理接口：

```python
# 你的 FastAPI 后端新增接口
@app.post("/api/chat/search")
async def search_knowledge(query: str):
    """代理 kb_service 搜索，返回给前端"""
    resp = requests.post(
        "http://127.0.0.1:8000/api/kb/search",
        json={"query": query, "top_k": 5}
    )
    return resp.json()
```

### 成员 C（数据工程师）— 维护知识库（你自己）

- 初始化/重建知识库：`cd kb_service && python3 seed_data.py`
- 清空知识库后重建：运行 `seed_data.py`，选 `y` 清空
- 查看 FAISS 索引位置：`chroma_kb_store/` 目录（index.faiss + metadata.json）
- 当前种子数据覆盖 10 大类：账号认证、网络连接、服务器系统、软件应用、安全事件、硬件设备、邮件协作、数据库、DevOps、备份恢复
- 去重逻辑已在 `chroma_store.py` 中实现，入库时自动生效

### 成员 D（前端开发）— 通过成员 B 的 API 使用

前端的聊天界面不直接调 kb_service。你需要通过成员 B 的后端 API 来获取知识库推荐。具体接口格式请与成员 B 协商约定。

典型使用场景：
- 用户输入问题 → 前端调成员 B 的接口 → 成员 B 调 kb_service search → 返回结果给前端展示
- 管理员审核答案 → 前端调成员 B 的接口 → 成员 B 调 kb_service add → 写入知识库

---

## 七、各组员交接步骤

> 以下是每个角色接手项目时需要执行的操作清单。按顺序执行，打勾确认。

### 7.0 所有人共同步骤

```bash
# 1. 克隆项目（或从 U 盘/共享盘复制到本地）
git clone <仓库地址>
cd <项目根目录>

# 2. 确认 Python 版本 >= 3.10
python3 --version

# 3. 安装 kb_service 依赖
cd kb_service
pip3 install -r requirements.txt
cd ..

# 4. 确认 MySQL 运行中
mysql -u root -p -e "SHOW DATABASES;" 2>/dev/null | grep ops_db
# 如果 ops_db 不存在，创建它：
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS ops_db DEFAULT CHARSET utf8mb4;"

# 5. 启动 Java 后端（新终端窗口）
./mvnw clean spring-boot:run
# 等待看到 "Started DemoApplication" 日志

# 6. 启动 kb_service（另一个新终端窗口）
cd kb_service
HF_ENDPOINT=https://hf-mirror.com python3 main.py
# 等待看到 "🚀 运维知识库服务启动中..."
```

---

### 7.1 成员 C（数据工程师 & 知识库运营）— 接手 kb_service

**你的核心职责**：知识库的初始化、文档导入、索引维护。

#### Step 1 — 确认 kb_service 能跑起来

```bash
cd kb_service
HF_ENDPOINT=https://hf-mirror.com python3 main.py
# 首次启动会下载 Embedding 模型（约 80MB），需等待 1-2 分钟
```

#### Step 2 — 首次部署：一键重建知识库

```bash
# 停止 kb_service（如果在运行）
lsof -ti:8000 | xargs kill -9

# 运行重建脚本（自动清空 + 导入种子数据 + 切片导入 ops_docs）
cd kb_service
python3 rebuild_kb.py
# 预期输出：知识库总数 591（500 种子 + 91 ops 文档块）
```

#### Step 3 — 验证搜索可用

```bash
# 先启动服务
HF_ENDPOINT=https://hf-mirror.com python3 main.py &

# 等 5 秒后测试
sleep 5
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Nginx 502错误怎么排查", "top_k": 3}' | python3 -m json.tool
```

#### Step 4 — 日常维护命令

| 场景 | 命令 |
|------|------|
| 查看知识库总条数 | `curl -s http://127.0.0.1:8000/api/kb/count` |
| 新增运维文档后重建 | `python3 rebuild_kb.py` |
| 完全清空重建 | `python3 rebuild_kb.py`（脚本自动先 clear） |
| 查看 FAISS 索引文件 | `ls -lh chroma_kb_store/` |
| 直接看元数据 | `python3 -m json.tool chroma_kb_store/metadata.json \| head -80` |

#### ⚠️ 注意事项

- `chroma_kb_store/` 目录被 `.gitignore` 忽略，新机器上必须运行 `rebuild_kb.py` 重新生成
- Embedding 模型下载需要 `HF_ENDPOINT=https://hf-mirror.com`，否则可能超时
- 如需手动添加单条知识，直接用 `POST /api/kb/add` 接口（见第四章）

---

### 7.2 成员 B（后端工程师）— 接手 Java 后端 + 反馈闭环

**你的核心职责**：Java Spring Boot 服务的启动、MySQL 配置、工单反馈闭环联调。

#### Step 1 — 确认 MySQL 正常

```bash
# 检查 MySQL 是否运行
mysqladmin -u root -p ping

# 确认 ops_db 数据库存在
mysql -u root -p -e "USE ops_db; SHOW TABLES;"
# JPA ddl-auto=update 会自动建表，第一次启动后应该看到 operators、trouble_tickets 表
```

#### Step 2 — 启动 Java 后端

```bash
cd <项目根目录>
./mvnw clean spring-boot:run
# 等待控制台输出 "Started DemoApplication in X seconds"
# 默认端口：8082
```

#### Step 3 — 验证 Java ↔ kb_service 联通

```bash
# 先确认 kb_service 在 8000 端口运行
curl http://127.0.0.1:8000/api/kb/health

# 测试工单反馈闭环：创建一个工单然后 resolve
# （通过 API 或前端操作，略）
```

#### Step 4 — 关键代码位置

| 文件 | 做了什么 | 注意 |
|------|---------|------|
| `TicketController.java` | `resolve()` 方法中调 kb_service 的 add 接口 | 已经修了 localhost→127.0.0.1、UTF-8、HTTP/1.1 三个坑 |
| `application.yaml` | 数据库连接配置 | JDBC URL 已有 `characterEncoding=UTF-8` |
| `ChatController.java` | SSE 流式代理到 AI 服务 | 如果 AI 服务端口变了，改 `AI_SERVICE_URL` |

#### ⚠️ 常见坑

| 问题 | 原因 | 解决 |
|------|------|------|
| Java 调 kb_service 返回 422 | 没用 `127.0.0.1` 或未加 UTF-8 | 检查 `TicketController.java` 三处修复是否保留 |
| MySQL 中文乱码 | JDBC URL 缺少编码参数 | `application.yaml` 中确认有 `characterEncoding=UTF-8` |
| 端口 8082 被占用 | 上次没杀干净 | `lsof -ti:8082 \| xargs kill -9` |

---

### 7.3 成员 A（算法/RAG 架构师）— 接手大模型 + RAG 链路

**你的核心职责**：部署大模型（DeepSeek/Qwen2.5）、搭建 RAG 检索链路、Prompt 工程。

#### Step 1 — 确认 kb_service 搜索可用

```bash
# kb_service 必须先跑起来
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "服务器CPU使用率100%怎么排查", "top_k": 5}' \
  | python3 -m json.tool
```

#### Step 2 — 对接检索接口（Python 示例）

```python
import requests

def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """从 kb_service 检索 Top-K 相关知识"""
    resp = requests.post(
        "http://127.0.0.1:8000/api/kb/search",
        json={"query": query, "top_k": top_k},
        timeout=10
    )
    data = resp.json()
    # 只保留相似度 >= 0.60 的结果
    return [r for r in data["results"] if r["score"] >= 0.60]

# 构造 RAG Prompt
docs = retrieve_context(user_question, top_k=5)
context = "\n---\n".join([
    f"参考{d['id']}（相似度{d['score']:.0%}）:\nQ: {d['question']}\nA: {d['answer']}"
    for d in docs
])
```

#### Step 3 — 关键参数建议

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `top_k` | 5~10 | 运维文档类问题建议 10~15，FAQ 类 5 即可 |
| 最低相似度 | 0.60 | 低于此值的结果质量不可靠，建议丢弃 |
| 超时 | 10 秒 | 搜索通常 < 1 秒，但首次模型加载需要时间 |

#### ⚠️ 注意事项

- kb_service 的 `all-MiniLM-L6-v2` 模型（384 维）对 Docker/MySQL 等通用领域词检索效果一般，建议 `top_k=10~15` 来补偿
- 如果后续升级到 BGE-M3（1024 维），检索精度会大幅提升
- 成员 C 已将 ops_docs 文档转化为自然语言问句存入知识库，RAG 链路可直接使用

---

### 7.4 成员 D（前端开发）— 接手 UI

**你的核心职责**：聊天界面 + 管理仪表盘的开发。

#### Step 1 — 确认后端 API 可用

```bash
# 确认 Java 后端在跑
curl http://127.0.0.1:8082/api/operators

# 确认 kb_service 在跑
curl http://127.0.0.1:8000/api/kb/health
```

#### Step 2 — API 对接清单

| 前端功能 | 调哪个后端 API | 说明 |
|---------|---------------|------|
| 用户提问 | 成员 B 的 Chat 接口（SSE 流式） | 不直接调 kb_service |
| 知识库推荐 | 通过成员 B 的代理接口 | 成员 B 后端代理 kb_service search |
| 工单管理 | 成员 B 的 Ticket CRUD 接口 | 列出/查看/处理工单 |
| 管理员审核 | 成员 B 的 Ticket resolve 接口 | resolve 后自动写入 kb_service |

#### Step 3 — 典型数据流

```
用户输入问题
  → 前端调成员B的 /api/chat（SSE）
    → 成员B转发给成员A的 RAG 服务
      → 成员A调 kb_service /api/kb/search 检索知识
      → 成员A用大模型生成答案
    → 成员B流式返回给前端
  → 前端逐字展示
```

> ⚠️ 不要直接从前端调 kb_service 的 8000 端口。所有请求统一经过成员 B 的后端（8082 端口），由成员 B 做代理和权限控制。

---

## 八、常见问题排查

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| 连不上 `8000` 端口 | 服务未启动 | `lsof -i:8000` 检查 |
| 启动报 `ModuleNotFoundError` | 缺少依赖 | `pip3 install -r requirements.txt` |
| 模型下载失败 | 网络问题 | 确认 `HF_ENDPOINT=https://hf-mirror.com` |
| Java 调用返回 422 | 编码问题 | 确认用了 `StandardCharsets.UTF_8` + `127.0.0.1` + HTTP/1.1 |
| 中文乱码 | JDBC 编码 | `application.yaml` 中 JDBC URL 加 `&characterEncoding=UTF-8` |
| 搜索结果全是垃圾 | 种子数据未导入 | 运行 `python3 seed_data.py` |

---

## 九、端口与依赖一览

| 服务 | 端口 | 技术栈 |
|------|------|--------|
| kb_service（知识库） | 8000 | Python FastAPI + ChromaDB + BGE-M3 |
| Java 后端 | 8082 | Spring Boot + MySQL |
| MySQL | 3306 | `ops_db` 数据库 |

---

## 十、快速测试命令

```bash
# 健康检查
curl http://127.0.0.1:8000/api/kb/health

# 搜索测试
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "忘记密码怎么办", "top_k": 3}' | python3 -m json.tool

# 添加入库测试
curl -s -X POST http://127.0.0.1:8000/api/kb/add \
  -H "Content-Type: application/json" \
  -d '{"question": "测试问题", "answer": "测试答案"}'

# 查看条数
curl -s http://127.0.0.1:8000/api/kb/count | python3 -m json.tool
```
