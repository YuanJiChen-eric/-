# 运维知识库服务 · 成员查阅指南

> **成员 C（数据工程师 & 知识库运营）交付文档**
> 华南理工 × 中国电信广东公司 · 课题六
>
> 其他成员只需阅读本文档即可对接知识库与数据飞轮。

---

## 一、交付成果概览

| 类别 | 内容 | 位置 |
|------|------|------|
| 知识库服务 | FastAPI，端口 **8000** | `main.py` |
| 向量存储 | ChromaDB + BGE-M3，约 **629 条** | `chroma_kb_store/`（本地生成） |
| 运维文档 | 11 份 Markdown（账号/故障/系统操作等） | `ops_docs/` |
| 种子 FAQ | 500+ 条，10 大类 | `seed_data.py` |
| 数据流水线 | 清洗 → 切片 → 入库 | `data_clean.py` / `ingest.py` / `rebuild_kb.py` |
| 反馈闭环 | 工单 → 人工答案 → 自动入库 | Java `TicketController` + `feedback_loop.py`（演示） |

**未修改他人代码**：Java 后端、成员 A 的 `rag_ops.py` / `api_server.py` 保持原样，通过 HTTP 接口对接。

---

## 二、架构与数据流

```
用户提问
  → Java /api/chat (8082, SSE)
  → RAG 服务 /api/rag (8001, 成员 A)
  → [可选] kb_service /api/kb/search (8000) 检索知识
  → 大模型生成回答
  → 答不了时自动创建工单 (status=pending)

运维处理工单
  → Java POST /api/tickets/{id}/resolve
  → 自动 POST /api/kb/add (8000)  ← 数据飞轮
  → ChromaDB 知识库增长
  → 下次类似问题可被检索到
```

| 服务 | 端口 | 负责人 | 说明 |
|------|------|--------|------|
| kb_service | **8000** | 成员 C | 向量知识库（本文档） |
| Java 后端 | **8082** | 成员 B | 聊天代理、工单、账号 CRUD |
| RAG 问答 | **8001** | 成员 A | 独立 ChromaDB，与 8000 不冲突 |
| MySQL | **3306** | 成员 B | 数据库 `ops_db` |

---

## 三、首次部署（成员 C 或新机器）

```bash
cd kb_service
chmod +x setup.sh && ./setup.sh          # 依赖 → 模型 → 清洗 → 重建
HF_ENDPOINT=https://hf-mirror.com /opt/anaconda3/bin/python main.py
```

或分步执行：

```bash
/opt/anaconda3/bin/pip install -r requirements.txt
/opt/anaconda3/bin/python download_model.py   # BGE-M3 约 2.1GB，ModelScope 镜像
/opt/anaconda3/bin/python data_clean.py
/opt/anaconda3/bin/python rebuild_kb.py
/opt/anaconda3/bin/python main.py
```

验证：

```bash
curl http://127.0.0.1:8000/api/kb/health
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "账号冻结怎么处理", "top_k": 3}' | python3 -m json.tool
```

停止服务：`lsof -ti:8000 | xargs kill -9`

---

## 四、API 接口（成员 A / B 必看）

### 4.1 健康检查 `GET /api/kb/health`

```bash
curl http://127.0.0.1:8000/api/kb/health
# {"status":"ok","service":"运维知识库服务","records":629}
```

### 4.2 搜索知识库 `POST /api/kb/search`（成员 A 主要使用）

```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Docker容器频繁重启", "top_k": 5}'
```

| 字段 | 说明 |
|------|------|
| `query` | 用户问题 |
| `top_k` | 返回条数（1~20，建议 5~10） |
| `results[].score` | 相似度 0~1，建议 **≥ 0.60** 才作为 RAG 上下文 |
| `results[].question` / `answer` | 结构化 Q&A |

Python 示例（成员 A）：

```python
import requests

def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    resp = requests.post(
        "http://127.0.0.1:8000/api/kb/search",
        json={"query": query, "top_k": top_k},
        timeout=10,
    )
    return [r for r in resp.json()["results"] if r["score"] >= 0.60]
```

Few-shot 模板见：`prompts/rag_fewshot.txt`

### 4.3 添加知识 `POST /api/kb/add`（数据飞轮核心）

```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/add \
  -H "Content-Type: application/json" \
  -d '{"question": "Redis内存满了怎么办", "answer": "1) 设置 maxmemory-policy...", "skip_if_duplicate": true}'
```

| 字段 | 说明 |
|------|------|
| `question` | 用户原始问题 |
| `answer` | 人工标准答案 |
| `skip_if_duplicate` | 默认 `true`，相似度 ≥ 90% 跳过重复 |
| `dedup_threshold` | 去重阈值，默认 `0.90` |

**成员 B 注意**：Java 调用时必须用 `127.0.0.1`、UTF-8、HTTP/1.1（已在 `TicketController` 修复）。

### 4.4 查看条数 `GET /api/kb/count`

```bash
curl http://127.0.0.1:8000/api/kb/count
```

---

## 五、数据飞轮怎么用（重点）

课题要求：*「处理完成后再自动完善知识库」*。

### 5.1 生产环境（已实现，成员 B）

无需额外开发，`TicketController.resolve()` 已对接：

```
1. 用户提问 → ChatController → RAG 回答
2. 答不了（含「无法回答/抱歉/人工」）→ 自动创建 TroubleTicket (pending)
3. 运维后台 GET /api/tickets/pending 查看待办
4. 运维填写 resolution，POST /api/tickets/{id}/resolve
5. Java 自动调用 POST http://127.0.0.1:8000/api/kb/add
6. 知识库新增一条，下次类似问题可被 search 命中
```

**前置条件**：kb_service 在 8000 端口运行。

### 5.2 本地演示（成员 C / 答辩用）

不依赖 Java，用 `feedback_loop.py` 模拟：

```bash
cd kb_service

# ① 模拟「模型答不了」→ 进入待处理队列
/opt/anaconda3/bin/python feedback_loop.py add \
  --question "Redis集群脑裂怎么解决" \
  --bot-response "抱歉，无法处理"

# ② 查看队列
/opt/anaconda3/bin/python feedback_loop.py list

# ③ 运维填写标准答案 → 自动入库
/opt/anaconda3/bin/python feedback_loop.py resolve \
  --id 1 \
  --resolution "1) redis-cli info replication 2) 检查哨兵日志 3) 修复主从"

# ④ 验证已入库
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Redis集群脑裂", "top_k": 3}'
```

队列文件：`data/pending_tickets.csv`（演示用，生产由 MySQL `trouble_tickets` 表替代）。

若 `main.py` 已运行，resolve 时加 `--via-api` 走 HTTP 入库。

### 5.3 去重机制

入库时默认开启语义去重：新问题与已有记录相似度 **≥ 90%** 则跳过，避免知识库膨胀。强制入库设 `"skip_if_duplicate": false`。

---

## 六、各成员对接要点

### 成员 A（RAG 架构师）

- 检索：`POST http://127.0.0.1:8000/api/kb/search`，`top_k=5~10`，过滤 `score >= 0.60`
- 你的 `rag_ops.py`（8001）使用独立 `chroma_db/`，与 kb_service **不冲突**
- 若希望统一知识源，可在 RAG 链路中改为调用 8000 search，无需改 kb_service

### 成员 B（Java 后端）

- 工单闭环已对接 `/api/kb/add`，**无需改代码**
- 确保 kb_service 运行后再 resolve 工单
- 前端不直接调 8000，统一走 8082 代理

### 成员 D（前端）

| 功能 | 调用 |
|------|------|
| 用户聊天 | 成员 B `POST /api/chat`（SSE） |
| 工单列表 | 成员 B `GET /api/tickets/pending` |
| 处理工单 | 成员 B `POST /api/tickets/{id}/resolve` → 触发数据飞轮 |
| 账号管理 | 成员 B `/api/operators` CRUD |

---

## 七、脚本速查（成员 C 维护）

| 脚本 | 用途 |
|------|------|
| `setup.sh` | 一键首次部署 |
| `download_model.py` | 下载 BGE-M3（ModelScope，跳过 ONNX） |
| `data_clean.py` | 清洗 `ops_docs/` → `ops_docs_clean/` |
| `ingest.py` | 切片入库；`--rebuild` 完整重建；`--file` 追加单文件 |
| `rebuild_kb.py` | 清空并重建（种子 FAQ + 文档） |
| `feedback_loop.py` | 数据飞轮演示（add / list / resolve） |
| `import_ops_docs.py` | 服务运行时通过 HTTP 追加导入（备用） |

**新增运维文档**：

```bash
# 1. 在 ops_docs/ 新增 .md（按 ### 标题组织）
# 2. 清洗 + 重建或追加
/opt/anaconda3/bin/python data_clean.py
/opt/anaconda3/bin/python rebuild_kb.py
# 或追加：/opt/anaconda3/bin/python ingest.py --dir ../ops_docs_clean --dedup
```

---

## 八、FAQ 格式参考

高质量 Q&A 需包含具体 URL、命令、状态码。完整内容见 `ops_docs/account-management.md` 等文档。

**课题标准示例**：

| 问题 | 答案要点 |
|------|----------|
| 账号冻结怎么处理？ | 自助 http://XXX.YYY.ZZZ 或热线 400-8800-1234 |
| 数据库连接超时？ | `telnet IP 3306`、`SHOW PROCESSLIST`、`systemctl restart mysql` |
| Nginx 502？ | 查后端服务、`systemctl status nginx`、错误日志 |

Markdown 切片规范：`# 标题` → `## 章节` → `### 切片边界（每条知识一块）`

---

## 九、常见问题

| 问题 | 解决 |
|------|------|
| 连不上 8000 | `lsof -i:8000` 检查；`python main.py` 启动 |
| rebuild 报 sqlite readonly | 先停 main.py，再跑 rebuild_kb |
| 模型下载慢 | `download_model.py` 用 ModelScope；约 2.1GB |
| Java 调 add 返回 422 | 用 `127.0.0.1` + UTF-8 + HTTP/1.1 |
| 搜索结果差 | 增大 top_k；运行 data_clean + rebuild |
| 内存不足 | BGE-M3 约占 2~3GB；避免与 rag_ops 同时加载 |

---

## 十、本地生成目录（不入 Git）

| 目录 | 说明 |
|------|------|
| `chroma_kb_store/` | 向量库 |
| `ops_docs_clean/` | 清洗后文档 |
| `local_models/` | BGE-M3 模型（约 2.1GB） |
| `data/pending_tickets.csv` | 飞轮演示队列 |

新机器克隆代码后：执行 `setup.sh` 即可重建知识库。
