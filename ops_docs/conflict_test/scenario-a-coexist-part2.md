---
kb_scenario: coexist_part2
kb_priority: 100
---

# 矛盾测试：DNS 故障排查

> 场景 A-2：与 part1 问题相似、答案矛盾，应并存且 priority+1

## 测试场景

### DNS 解析失败怎么排查

【并存测试-方案B】优先使用 `dig @10.0.0.53 internal.company.com` 测试内网 DNS。若 dig 失败，改用公共 DNS `8.8.8.8` 对比排查。检查 `/etc/nsswitch.conf` 中 hosts 顺序是否为 `files dns`。

---

*期望：导入 action=added_coexist，新条 priority=101，与 part1 同时 active。*
