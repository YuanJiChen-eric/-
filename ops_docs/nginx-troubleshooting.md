# Nginx 运维排错手册

> 适用范围：Nginx 1.18+ | 最后更新：2026-06

---

## 一、常见启动故障

### 1.1 端口被占用

**现象**：启动报 `bind() to 0.0.0.0:80 failed (98: Address already in use)`

**排查**：
```bash
# 查看谁占用了80端口
sudo lsof -i :80
# 或者
sudo netstat -tlnp | grep :80
```

**解决**：
- 如果旧 Nginx 进程没杀掉：`sudo kill -9 <PID>` 后重启
- 如果是 Apache 占用了 80：停掉 Apache 或换端口

### 1.2 配置文件语法错误

**现象**：`nginx: [emerg] unexpected "}" in /etc/nginx/nginx.conf`

**排查**：
```bash
# 测试配置文件语法
sudo nginx -t
```

**解决**：根据报错行号定位，常见错误包括：
- 缺少分号 `;`
- 大括号不匹配
- 指令写错位置（比如 `server` 写到 `http` 块外）

---

## 二、性能问题

### 2.1 502 Bad Gateway

**现象**：浏览器显示 502，Nginx 错误日志显示 `upstream prematurely closed connection`

**排查步骤**：
```bash
# 1. 检查后端服务是否存活
curl http://127.0.0.1:后端端口/health

# 2. 查看后端日志
tail -f /var/log/应用/error.log

# 3. 检查 Nginx upstream 配置
grep -A5 "upstream" /etc/nginx/nginx.conf
```

**常见原因与解决**：

| 原因 | 解决 |
|------|------|
| 后端服务挂了 | 重启后端服务 |
| 后端响应超时 | 加大 `proxy_read_timeout`：`proxy_read_timeout 300s;` |
| 后端重启中 | 配置 `upstream` 多节点 + `keepalive` |
| 请求体太大 | 加大 `client_max_body_size`：`client_max_body_size 100m;` |

### 2.2 504 Gateway Timeout

**原因**：后端处理时间超过了 `proxy_read_timeout`。

**解决**：
```nginx
location /api/ {
    proxy_read_timeout 600s;   # 从默认60秒加到600秒
    proxy_connect_timeout 60s;
    proxy_send_timeout 600s;
    proxy_pass http://backend;
}
```

### 2.3 高并发下响应变慢

**优化策略**：

```nginx
# worker 进程数（设为 CPU 核数）
worker_processes auto;

# 每个 worker 最大连接数
events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

# 开启 Gzip 压缩
gzip on;
gzip_types text/plain application/json application/javascript text/css;

# 静态文件缓存
location ~* \.(jpg|png|css|js)$ {
    expires 30d;
    add_header Cache-Control "public";
}

# 连接池复用
upstream backend {
    server 127.0.0.1:8080;
    keepalive 64;
}
```

---

## 三、反向代理常见配置

### 3.1 基础反向代理

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.2 HTTPS 配置

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/ssl/certs/example.crt;
    ssl_certificate_key /etc/ssl/private/example.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8080;
    }
}

# HTTP 自动跳转 HTTPS
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}
```

### 3.3 负载均衡

```nginx
upstream app_cluster {
    # 轮询（默认）
    server 192.168.1.10:8080 weight=5;
    server 192.168.1.11:8080 weight=3;
    server 192.168.1.12:8080 backup;  # 备用节点

    # 健康检查
    max_fails=3 fail_timeout=30s;
}
```

---

## 四、日志分析

### 4.1 访问量统计

```bash
# 统计访问最多的 IP
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20

# 统计访问最多的 URL
awk '{print $7}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20

# 统计各状态码数量
awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn
```

### 4.2 慢请求分析

```nginx
# 在 http 块中配置
log_format slow '$remote_addr - $request_time - $request';
access_log /var/log/nginx/slow.log slow;

# 提取响应时间超过 3 秒的请求
awk '($2 > 3){print $0}' /var/log/nginx/slow.log
```

---

## 五、安全加固

```nginx
# 隐藏 Nginx 版本号
server_tokens off;

# 限制请求速率（防 DDoS）
limit_req_zone $binary_remote_addr zone=mylimit:10m rate=10r/s;

# 限制并发连接数
limit_conn_zone $binary_remote_addr zone=addr:10m;

# 禁止直接 IP 访问
server {
    listen 80 default_server;
    server_name _;
    return 444;
}
```
