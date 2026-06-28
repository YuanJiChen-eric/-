# 矛盾知识处理 — 测试文档套件

本目录用于验证 `kb_conflict` + `ingest` 入库仲裁与检索多答案排序。

## 场景一览

| 文件 | 场景 | 期望结果 |
|------|------|----------|
| `scenario-a-coexist-part1.md` + `part2.md` | 同 priority，无 date/version 可裁决 | **并存**，part2 `priority=101` |
| `scenario-b-date-old.md` + `date-new.md` | 同 priority，新 **date** 更大 | **supersede**，仅新版 active |
| `scenario-c-version-v1.md` + `v2.md` | 同 priority、同 date，新 **version** 更大 | **supersede**，仅 v2 active |
| `scenario-d-duplicate.md` | 重复导入相同内容 | 第二次 **duplicate** |
| `scenario-e-priority-doc-vs-seed.md` | 文档 vs 种子 FAQ | 文档 **supersede** 种子（若相似） |

## 一键运行

```bash
cd kb_service

# 清洗测试文档
/opt/anaconda3/bin/python data_clean.py \
  --input ../ops_docs/conflict_test \
  --output ../ops_docs_clean/conflict_test

# 执行自动化测试（需 8000 可选，脚本直连 Chroma）
/opt/anaconda3/bin/python scripts/run_conflict_doc_tests.py
```

## 手动单文件导入

```bash
cd kb_service
/opt/anaconda3/bin/python ingest.py \
  --file ../ops_docs_clean/conflict_test/scenario-b-date-old.md
/opt/anaconda3/bin/python ingest.py \
  --file ../ops_docs_clean/conflict_test/scenario-b-date-new.md
```

## Frontmatter 字段

```yaml
---
kb_date: 2026-06-06      # 可选，入库 metadata.date
kb_version: 2            # 可选，默认 1
kb_priority: 100         # 可选，默认 100（ops_doc）
kb_scenario: 场景标识    # 写入 test_scenario，便于日志排查
---
```

## 验证检索（最多 3 条，按 priority 排序）

```bash
curl -s -X POST http://127.0.0.1:8000/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query":"DNS解析失败怎么排查","top_k":5,"max_answers":3}'
```

## 场景 F：工单低优先级（API 脚本自动测）

`ticket` priority=60 写入矛盾答案 → 期望 **rejected**，见 `run_conflict_doc_tests.py` 步骤 F。

冲突日志：`kb_service/data/import_conflicts.jsonl`
