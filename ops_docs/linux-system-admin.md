# Linux 系统管理手册

> 适用范围：CentOS 7+ / Ubuntu 20.04+ | 最后更新：2026-06

---

## 一、系统监控

### 1.1 CPU 使用率 100% 排查

```bash
# 查看 CPU 总体使用率
top
# 按 1 展开每个核心
# 按 P 按 CPU 使用排序

# 更友好的工具
htop

# 查看过去负载
uptime

# 找出高 CPU 进程
ps aux --sort=-%cpu | head -10
```

找到高 CPU 进程后的排查方向：
- **Java 应用**：`jstack <PID>` 查看线程堆栈，找频繁 GC 或死循环
- **MySQL**：`SHOW FULL PROCESSLIST` 查看慢查询
- **Python**：`py-spy top --pid <PID>` 实时采样

### 1.2 内存不足处理

```bash
# 查看内存使用
free -h

# 查看进程内存占用排序
ps aux --sort=-%mem | head -10

# 查看内存详情
cat /proc/meminfo

# 清理缓存（非紧急不要用）
sync && echo 3 > /proc/sys/vm/drop_caches
```

OOM 被杀后查看：
```bash
# 查看 OOM 记录
dmesg | grep -i "out of memory"
grep -i "oom" /var/log/messages
```

### 1.3 磁盘空间满

```bash
# 查看各分区使用情况
df -h

# 找出大目录
du -sh /* 2>/dev/null | sort -rh | head -10
du -h --max-depth=1 /var | sort -rh

# 找大文件（> 100MB）
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null

# 清理日志
journalctl --vacuum-size=500M          # systemd 日志
find /var/log -name "*.log" -mtime +30 -delete  # 30天前的日志
```

---

## 二、用户与权限管理

### 2.1 用户管理

```bash
# 创建用户
useradd -m -s /bin/bash 用户名

# 设置密码
passwd 用户名

# 删除用户
userdel -r 用户名

# 查看所有用户
cat /etc/passwd

# 锁定/解锁用户
usermod -L 用户名    # 锁定
usermod -U 用户名    # 解锁
```

### 2.2 权限管理

```bash
# 修改文件所有者
chown -R 用户名:组名 /path

# 修改权限
chmod 755 /path       # rwxr-xr-x
chmod 700 /path       # rwx------

# 给用户 sudo 权限
usermod -aG sudo 用户名      # Ubuntu
usermod -aG wheel 用户名     # CentOS
```

### 2.3 SSH 安全

```bash
# /etc/ssh/sshd_config
Port 2222                        # 改默认端口
PermitRootLogin no              # 禁止 root SSH
PasswordAuthentication no       # 只用密钥登录
MaxAuthTries 3                  # 最大尝试次数

# 重启 SSH
systemctl restart sshd
```

---

## 三、进程管理

```bash
# 查看进程树
pstree -p

# 查看进程详情
ps -ef | grep 进程名

# 杀进程
kill <PID>           # 温和终止
kill -9 <PID>        # 强制杀
kill -15 <PID>       # 正常终止（推荐）

# 按名称杀进程
pkill -f 进程名

# 后台运行（防 HUP）
nohup 命令 &         # 输出到 nohup.out
screen -S 会话名      # 创建 screen 会话
tmux new -s 会话名    # 创建 tmux 会话
```

---

## 四、网络诊断

```bash
# 查看网络接口
ip addr show

# 查看监听端口
ss -tlnp

# 查看路由表
ip route show

# DNS 解析测试
nslookup 域名
dig 域名

# 网络连通性
ping -c 4 IP
traceroute IP

# 抓包
tcpdump -i eth0 port 80 -w capture.pcap
```

---

## 五、systemd 服务管理

```bash
# 启动/停止/重启
systemctl start <服务名>
systemctl stop <服务名>
systemctl restart <服务名>

# 查看状态
systemctl status <服务名>

# 开机自启
systemctl enable <服务名>
systemctl disable <服务名>

# 查看日志
journalctl -u <服务名> -f
journalctl -u <服务名> --since "10 minutes ago"

# 列出所有服务
systemctl list-units --type=service
```

### systemd 服务文件模板

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Application Service
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/start.sh
ExecStop=/bin/kill -15 $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```
