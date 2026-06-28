---
kb_scenario: priority_doc_over_seed
kb_date: 2026-06-01
kb_version: 1
kb_priority: 100
---

# 矛盾测试：与种子 FAQ 冲突

> 场景 E：官方文档 priority=100，应覆盖相似种子 FAQ（priority=80）

## 测试场景

### 公司数据备份策略是什么

【官方文档覆盖种子】日备份（增量）：每天凌晨 02:00；周备份（全量）：每周日 03:00 全量备份；月备份（归档）：每月 1 日归档到异地机房 `backup-dr.company.com`。与种子 FAQ 中「每周全量」表述不同，以本手册为准。

---

*期望：若库中已有相似种子 FAQ，导入时 action=superseded；检索命中本答案。*
