# 安全事件应急响应手册

> 最后更新：2026-06

---

## 一、入侵排查

### 1.1 发现可疑登录

```bash
# 查看最近登录记录
last -20
lastb -20          # 失败的登录

# 查看当前登录用户
who
w

# 查看 SSH 登录日志
grep "Accepted" /var/log/auth.log | tail -20    # Ubuntu
grep "Accepted" /var/log/secure | tail -20      # CentOS
```

### 1.2 异常账户检查

```bash
# 查看特权账户（UID 为 0）
awk -F: '($3 == 0) {print $1}' /etc/passwd

# 查看可登录账户
grep -v "/sbin/nologin\|/bin/false" /etc/passwd

# 查看最近创建的用户
grep "new user" /var/log/auth.log
```

### 1.3 异常进程排查

```bash
# 查看 CPU/内存异常的进程
ps aux --sort=-%cpu | head -10
ps aux --sort=-%mem | head -10

# 查看不明进程的路径
ls -l /proc/<PID>/exe

# 查看进程网络连接
netstat -anp | grep <PID>

# 查看定时任务
crontab -l
cat /etc/crontab
ls /var/spool/cron/
```

---

## 二、疑似中毒处理

### 2.1 立即响应（前 5 分钟）

1. **断网**：`ifconfig eth0 down` 或拔网线 —— 但不要关机
2. **不关机**：关机可能触发病毒的自毁脚本，且会丢失内存中的证据
3. **通知安全团队**

### 2.2 排查思路

```bash
# 1. 检查是否有权限提升
find / -perm -4000 -type f 2>/dev/null  # SUID 文件

# 2. 检查是否有隐藏进程
ps -ef | awk '{print $2}' | sort -n | uniq | while read p; do
  if [ ! -d "/proc/$p" ]; then echo "Hidden PID: $p"; fi
done

# 3. 检查自启动项
systemctl list-unit-files | grep enabled
ls /etc/systemd/system/multi-user.target.wants/

# 4. 检查 /tmp 下可疑文件
ls -la /tmp/ --time=atime | head -20

# 5. 检查命令是否被替换
rpm -Va  # CentOS，验证所有包完整性
dpkg --verify  # Ubuntu
```

---

## 三、钓鱼邮件应急

### 3.1 用户报告点击了钓鱼链接

**立即操作**：
1. 让用户**立即修改密码**（所有相关系统）
2. 重置 MFA 绑定
3. 检查邮箱是否有自动转发规则
4. 检查是否有可疑的登录记录

```bash
# 检查用户最近登录
last | grep 用户名 | head -10

# 检查 sudo 记录
grep 用户名 /var/log/auth.log | grep sudo
```

### 3.2 全公司范围排查

1. 邮件系统管理员搜索同批次钓鱼邮件
2. 从收件箱中撤回未读的同批次邮件
3. 将钓鱼发件人域名加入黑名单
4. 全员通知：不要点击 XX 主题的邮件

---

## 四、DDoS 攻击应急

### 4.1 确认是否被攻击

```bash
# 检查网络流量
iftop
nload

# 检查连接数
ss -s
netstat -an | grep ESTABLISHED | wc -l

# 分析请求来源
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20
```

### 4.2 应急缓解

```bash
# Nginx 限流
# 在 http 块中
limit_req_zone $binary_remote_addr zone=ddos:10m rate=10r/s;
# 在 location 块中
limit_req zone=ddos burst=20 nodelay;

# iptables 封 IP
iptables -A INPUT -s 攻击IP -j DROP

# 云厂商控制台开启 DDoS 防护
```
