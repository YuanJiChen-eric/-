---
kb_scenario: coexist_part1
kb_priority: 100
---

# 矛盾测试：DNS 故障排查

> 场景 A-1：无日期/版本差异时的并存（part1）

## 测试场景

### DNS 解析失败怎么排查

【并存测试-方案A】先检查本机 DNS 配置：`cat /etc/resolv.conf`。确认 nameserver 指向内网 DNS `10.0.0.53`。使用 `nslookup internal.company.com` 验证解析是否正常。若配置正确仍失败，检查防火墙是否放行 53 端口。

---

*期望：首次导入 action=added。*
