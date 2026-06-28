---
kb_scenario: version_v1
kb_version: 1
kb_priority: 100
---

# 矛盾测试：日志保留策略

> 场景 C-1：仅版本号 v1（导入日自动填 date=今天）

## 测试场景

### 应用日志默认保留多久

【版本v1】应用日志默认保留 30 天，路径 `/var/log/apps/`。超过 30 天由 logrotate 自动压缩归档到 `/var/log/archive/`。

---

*期望：首次导入 added，version=1。*
