---
kb_scenario: version_v2
kb_version: 2
kb_priority: 100
---

# 矛盾测试：日志保留策略

> 场景 C-2：版本 v2，应软覆盖 v1（同 priority、同 date 时比 version）

## 测试场景

### 应用日志默认保留多久

【版本v2】应用日志默认保留 90 天，路径 `/var/log/apps/`。归档策略改为按周打包上传对象存储，本地仅保留 14 天热数据。

---

*期望：导入 action=superseded，仅 v2 答案 active。*
