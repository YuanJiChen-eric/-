# 课题六 · 数据工程交付清单

> 成员 C | 更新：2026-06-17

## 交付物核对

- [x] 第一阶段：运维文档（`ops_docs/` 11 份 + FAQ 样本）
- [x] 第二阶段：`data_clean.py` → `ops_docs_clean/`
- [x] 第三阶段：`ingest.py` + `rebuild_kb.py`（ChromaDB + BGE-M3）
- [x] 第四阶段：`feedback_loop.py`（CSV 队列 → 入库）
- [x] 第五阶段：`README.md` 全员指南
- [x] 知识库验证：629 条，搜索「账号冻结怎么处理」命中 ✅
- [x] API 验证：`/api/kb/health` + `/api/kb/search` ✅
- [x] Java 对接：`TicketController` → `/api/kb/add`（未改成员 B 代码）

## 本地环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10+（推荐 conda） |
| 磁盘 | 模型 2.1GB + 向量库 ~10MB |
| 内存 | 建议 8GB+（BGE-M3 加载约 2～3GB） |

## 一键部署

```bash
cd kb_service
chmod +x setup.sh
./setup.sh
HF_ENDPOINT=https://hf-mirror.com /opt/anaconda3/bin/python main.py
```

## 可选后续

- [ ] `git push` 推送到远程仓库
- [ ] 与成员 A 协调 RAG 是否调用 `8000/api/kb/search`
- [ ] 演示反馈闭环：`feedback_loop.py add/resolve`
