# 运维知识库服务（kb_service）运行指南

> 成员 C · 数据工程与知识库运营 | 华南理工 × 中国电信广东公司 课题六

---

## 一、架构概览

```
ops_docs/ ──data_clean.py──► ops_docs_clean/
                                │
seed_data.py ───────────────────┼──ingest.py / rebuild_kb.py──► chroma_kb_store/
                                │                                      ▲
TicketController (Java) ────────┼──POST /api/kb/add──────────────────┘
                                │
                         main.py :8000
```

| 服务 | 端口 | 技术 |
|------|------|------|
| kb_service | **8000** | FastAPI + ChromaDB + BGE-M3 |
| Java 后端 | **8082** | Spring Boot（成员 B） |
| RAG 问答 | **8001** | rag_ops.py（成员 A，独立知识库） |

---

## 二、首次部署（按顺序执行）

```bash
cd kb_service

# 1. 安装依赖（推荐 conda）
/opt/anaconda3/bin/pip install -r requirements.txt

# 2. 下载 BGE-M3 模型（约 2.1GB，ModelScope 国内镜像）
/opt/anaconda3/bin/python download_model.py

# 3. 清洗文档（第二阶段）
/opt/anaconda3/bin/python data_clean.py

# 4. 重建知识库（第三阶段）
HF_ENDPOINT=https://hf-mirror.com /opt/anaconda3/bin/python rebuild_kb.py
# 或等效：/opt/anaconda3/bin/python ingest.py --rebuild

# 5. 启动服务
HF_ENDPOINT=https://hf-mirror.com /opt/anaconda3/bin/python main.py
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/kb/health
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "账号冻结怎么处理", "top_k": 3}' | python3 -m json.tool
```

---

## 三、脚本说明

| 脚本 | 阶段 | 作用 |
|------|------|------|
| `data_clean.py` | 二 | Markdown 去噪、结构化、实体保护 → `ops_docs_clean/` |
| `download_model.py` | — | BGE-M3 模型下载（跳过 ONNX 大包） |
| `ingest.py` | 三 | 按 `###` 切片 + 元数据 + 向量化入库 |
| `rebuild_kb.py` | 三 | 一键清空重建（种子 FAQ + 文档） |
| `feedback_loop.py` | 四 | 待处理 CSV 队列 → 人工答案 → 自动入库 |
| `main.py` | — | FastAPI 服务（health / search / add / count） |

---

## 四、成员对接

### 成员 B（Java 后端）

工单处理完成后自动入库，**无需改代码**：

```
POST http://127.0.0.1:8000/api/kb/add
{"question": "...", "answer": "...", "skip_if_duplicate": true}
```

注意：使用 `127.0.0.1`、UTF-8、HTTP/1.1（已在 TicketController 修复）。

### 成员 A（RAG 架构师）

检索接口：

```python
import requests
resp = requests.post("http://127.0.0.1:8000/api/kb/search",
                     json={"query": user_question, "top_k": 5})
docs = [r for r in resp.json()["results"] if r["score"] >= 0.60]
```

### 成员 D（前端）

通过成员 B 的后端代理访问，不直接调 8000 端口。

---

## 五、反馈闭环演示（第四阶段）

```bash
# 模拟低置信度问题入队
/opt/anaconda3/bin/python feedback_loop.py add \
  --question "Redis集群脑裂怎么解决" \
  --bot-response "抱歉，无法处理"

# 查看队列
/opt/anaconda3/bin/python feedback_loop.py list

# 运维处理后入库
/opt/anaconda3/bin/python feedback_loop.py resolve \
  --id 1 \
  --resolution "1) 检查哨兵日志 2) redis-cli info replication 3) 修复主从"

# 通过 HTTP API 入库（main.py 运行中）
/opt/anaconda3/bin/python feedback_loop.py resolve --id 1 --resolution "..." --via-api
```

生产环境由 Java `TicketController.resolve()` 替代 `feedback_loop.py`。

---

## 六、新增运维文档流程

```bash
# 1. 在 ops_docs/ 新增 .md（按 ### 标题组织）
# 2. 清洗
/opt/anaconda3/bin/python data_clean.py
# 3. 追加导入（不重建全库）
/opt/anaconda3/bin/python ingest.py --dir ../ops_docs_clean --dedup
# 或完整重建
/opt/anaconda3/bin/python rebuild_kb.py
```

---

## 七、常见问题

| 问题 | 解决 |
|------|------|
| sqlite readonly database | 先停 main.py，再跑 rebuild_kb |
| 模型下载慢/失败 | `download_model.py` 使用 ModelScope；跳过 ONNX |
| 搜索结果差 | 调大 top_k 到 10；检查 ops_docs_clean 是否最新 |
| 内存不足 | BGE-M3 约占 2～3GB；勿与 rag_ops 同时加载大模型 |

---

## 八、本地生成目录（不入 Git）

- `chroma_kb_store/` — 向量库
- `ops_docs_clean/` — 清洗后文档
- `local_models/` — BGE-M3 模型
- `data/pending_tickets.csv` — 反馈闭环演示队列
