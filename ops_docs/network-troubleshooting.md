# 网络故障排查手册

> 最后更新：2026-06

---

## 一、排查方法论

### 1.1 基本排查顺序

```
应用层：能访问 URL 吗？响应码是什么？
  ↓
传输层：端口通吗？TCP 连接能建立吗？
  ↓
网络层：IP 通吗？路由对吗？
  ↓
链路层：网卡亮灯吗？获取到 IP 了吗？
```

### 1.2 排查工具速查

| 工具 | 用途 |
|------|------|
| `ping` | 测试 IP 层连通性 |
| `traceroute` | 追踪路由路径 |
| `telnet IP 端口` | 测试 TCP 端口连通 |
| `curl -v` | 测试 HTTP 服务 |
| `nslookup / dig` | DNS 解析测试 |
| `tcpdump` | 抓包分析 |
| `ss -tlnp` | 查看监听端口 |

---

## 二、常见故障场景

### 2.1 完全断网

**排查步骤**：
```bash
# 1. 检查物理连接
ip link show
# 看 eth0 状态是否为 UP

# 2. 检查 IP 获取
ip addr show
# 是否有 IP（DHCP 没获取到？）

# 3. 检查网关
ip route show
ping 网关IP

# 4. 检查 DNS
cat /etc/resolv.conf
nslookup baidu.com
```

### 2.2 部分网站打不开

**可能原因**：
- DNS 污染/劫持 → 换 DNS（`8.8.8.8` 或 `114.114.114.114`）
- MTU 问题 → `ping -M do -s 1472 目标IP` 测试 MTU
- 路由问题 → `traceroute 目标IP` 看在哪个节点断了

### 2.3 间歇性断网

```bash
# 持续 ping 观察丢包率
ping -c 100 网关IP

# 检查网卡错误
ip -s link show eth0
# 看 errors / dropped / overruns

# 查看系统日志
dmesg | grep eth0
```

---

## 三、端口问题

### 3.1 端口不通排查

```bash
# 检查端口是否在监听
ss -tlnp | grep :端口号

# 检查防火墙
sudo iptables -L -n -v | grep 端口号        # iptables
sudo firewall-cmd --list-ports              # firewalld
sudo ufw status                             # ufw

# 临时开放端口测试
sudo iptables -I INPUT -p tcp --dport 端口号 -j ACCEPT
```

### 3.2 端口被占用

```bash
# 找到占用进程
lsof -i :端口号
# 或
ss -tlnp | grep :端口号

# 强制释放
kill -9 <PID>
```

---

## 四、DNS 问题

### 4.1 解析失败

```bash
# 测试 DNS 服务器是否可达
nslookup baidu.com 8.8.8.8

# 清空 DNS 缓存
# macOS
sudo dscacheutil -flushcache
# Linux（systemd-resolved）
sudo systemd-resolve --flush-caches
# Windows
ipconfig /flushdns

# 检查 hosts 文件
cat /etc/hosts
```

### 4.2 DNS 劫持排查

```bash
# 用不同 DNS 对比解析结果
nslookup example.com 8.8.8.8
nslookup example.com 114.114.114.114
nslookup example.com 1.1.1.1

# 如果结果不一致，可能被劫持
```

---

## 五、防火墙问题

### 5.1 临时关闭测试

```bash
# 先临时关闭确认是否防火墙问题
sudo systemctl stop firewalld    # CentOS
sudo ufw disable                 # Ubuntu

# 如果关了就能通 → 防火墙规则问题
# 记得测完重新开启！
sudo systemctl start firewalld
```

### 5.2 放行规则

```bash
# iptables 放行指定 IP
iptables -A INPUT -s 192.168.1.0/24 -p tcp --dport 8080 -j ACCEPT

# firewalld 放行服务
firewall-cmd --permanent --add-service=http
firewall-cmd --reload

# ufw 放行端口
ufw allow 8080/tcp
```
