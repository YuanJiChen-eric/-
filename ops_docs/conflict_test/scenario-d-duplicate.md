---
kb_scenario: duplicate_same
kb_date: 2026-01-01
kb_version: 1
kb_priority: 100
---

# 矛盾测试：重复入库

> 场景 D：相同问题 + 相同答案，重复导入应 duplicate

## 测试场景

### 测试重复入库的标准问题

【重复测试】这是一条用于测试去重的标准答案。内容包含固定口令 `DUPLICATE-TOKEN-42`，重复导入时不应产生新条目。

---

*期望：第一次 added；第二次导入本文件 action=duplicate。*
