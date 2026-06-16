# 数据工程 · 第一阶段交付说明

> 角色：成员 C（数据工程师 & 知识库运营）
> 阶段：一、数据搜集与原材料准备
> 更新：2026-06

---

## 本阶段完成内容

### 1. 新增运维文档（`ops_docs/`）

| 文件 | 内容 | 与现有数据的关系 |
|------|------|----------------|
| `account-management.md` | 账号冻结/解冻、密码重置、运维账号 CRUD | **补充**课题原文示例（http://XXX.YYY.ZZZ + 热线） |
| `common-fault-handling.md` | 服务无法启动、DB 连接超时、网络失败、转人工 | **侧重**申告场景 FAQ |
| `system-operation-manual.md` | 三服务架构、启动顺序、API、数据飞轮 | **新增**门户操作指南 |

**向量存储**：`kb_service` 使用 **ChromaDB + BGE-M3**（`chroma_kb_store/`），与成员 A 的 `rag_ops.py`（`chroma_db/` + bge-small-zh）**路径隔离，无冲突**。

### 2. 样本数据（`kb_service/data/运维知识库_sample.md`）

- 10 条高质量 FAQ 对，对齐课题六要求
- **不自动导入**知识库，仅供格式参考
- 等效内容已结构化写入上述 3 份 ops_docs

### 3. 导入逻辑微调（`kb_service/rebuild_kb.py`）

- 增加 `SKIP_FILES`，跳过 `课题要求.md`（非知识内容）
- **未修改** Java 后端、`rag_ops.py`、`api_server.py`

---

## 与现有项目架构的对应关系

```
ops_docs/*.md          ──rebuild_kb.py──►  chroma_kb_store/ (ChromaDB + BGE-M3)
seed_data.py           ──rebuild_kb.py──►  chroma_kb_store/
                                              ▲
TicketController       ──/api/kb/add──────►  │  (反馈闭环，已实现)
kb_service/main.py     ──/api/kb/search──►  │  (供 RAG 检索)
```

**你的职责边界**：

- ✅ 维护 `ops_docs/` 文档、`seed_data.py`、运行 `rebuild_kb.py`
- ✅ 后续阶段：`data_clean.py`、`ingest.py`、`feedback_loop.py`
- ❌ 不修改 `ChatController.java`、`rag_ops.py`、`api_server.py`

---

## 如何将新文档导入知识库

```bash
# 1. 停止正在运行的 kb_service（如有）
lsof -ti:8000 | xargs kill -9

# 2. 一键重建（清空 → 种子 FAQ → ops_docs 切片导入）
cd kb_service
HF_ENDPOINT=https://hf-mirror.com python3 rebuild_kb.py

# 3. 启动服务验证
python3 main.py

# 4. 测试课题示例
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "账号冻结怎么处理", "top_k": 3}' | python3 -m json.tool
```

**预期**：搜索结果应包含 `http://XXX.YYY.ZZZ` 和热线 `400-8800-1234` 相关内容。

---

## 给其他成员的说明

| 成员 | 你需要知道的 |
|------|-------------|
| **成员 A（RAG）** | 知识库检索仍用 `POST http://127.0.0.1:8000/api/kb/search`，无需改代码 |
| **成员 B（Java）** | 工单闭环 `TicketController` 已对接 `/api/kb/add`，无需改代码 |
| **成员 D（前端）** | 账号/工单 API 不变；新文档不影响前端 |

---

## 下一阶段预告

| 阶段 | 内容 | 产出 |
|------|------|------|
| 二 | 数据清洗与预处理 | `data_clean.py` |
| 三 | 切片策略与入库 | `ingest.py`（对接 ChromaDB + BGE-M3） |
| 四 | 反馈闭环脚本 | `feedback_loop.py`（演示工单 CSV → 入库） |
| 五 | 完整 README | 全员运行指南 |
