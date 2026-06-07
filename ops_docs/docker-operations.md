# Docker 运维实战手册

> 适用范围：Docker 20.10+ / Docker Compose v2 | 最后更新：2026-06

---

## 一、容器管理基础

### 1.1 常用命令速查

```bash
# 查看运行中的容器
docker ps

# 查看所有容器（包括已停止）
docker ps -a

# 启动/停止/重启
docker start <容器名>
docker stop <容器名>
docker restart <容器名>

# 进入容器
docker exec -it <容器名> /bin/bash

# 查看容器日志（实时）
docker logs -f --tail=100 <容器名>

# 删除容器
docker rm <容器名>
docker rm -f <容器名>   # 强制删除运行中的

# 删除所有已停止容器
docker container prune -f
```

### 1.2 镜像管理

```bash
# 查看本地镜像
docker images

# 拉取镜像
docker pull nginx:1.24

# 删除镜像
docker rmi <镜像ID>

# 清理无用镜像
docker image prune -a -f

# 查看镜像层
docker history <镜像名>
```

---

## 二、容器频繁重启排查

### 2.1 常见原因

容器处于 `Restarting` 状态，`docker ps` 显示持续重启：

**排查步骤**：

```bash
# 1. 查看容器日志
docker logs --tail=200 <容器名>

# 2. 查看退出码
docker inspect <容器名> | grep -i exitcode

# 3. 查看资源占用
docker stats --no-stream <容器名>

# 4. 查看事件时间线
docker events --filter container=<容器名>
```

### 2.2 退出码含义

| 退出码 | 含义 | 常见原因 |
|--------|------|---------|
| 0 | 正常退出 | CMD 进程正常结束（不应该） |
| 1 | 应用错误 | 程序抛异常退出 |
| 137 | SIGKILL | OOM 被杀，内存不够 |
| 139 | SIGSEGV | 段错误，内存访问越界 |
| 143 | SIGTERM | 正常终止信号 |

### 2.3 解决方案

**场景一：OOM 被杀（退出码 137）**

```bash
# 查看容器内存限制
docker inspect <容器名> | grep -i memory

# 加大内存限制
docker update --memory 2g --memory-swap 2g <容器名>

# 或者在 docker-compose.yml 中
services:
  app:
    deploy:
      resources:
        limits:
          memory: 2G
```

**场景二：启动即崩溃（退出码 1）**

```bash
# 以交互模式启动排查
docker run -it --entrypoint /bin/bash <镜像名>

# 手动执行启动命令，看报错
docker run -it <镜像名> /bin/bash -c "你的启动命令"
```

**场景三：健康检查失败**

```yaml
# docker-compose.yml 中配置健康检查
services:
  app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## 三、磁盘空间清理

### 3.1 空间检查

```bash
# 查看 Docker 磁盘占用
docker system df

# 详细信息
docker system df -v
```

### 3.2 一键清理

```bash
# 清理所有未使用资源（镜像、容器、网络、构建缓存）
docker system prune -a -f --volumes
```

### 3.3 日志文件过大

```bash
# 查看容器日志大小
du -sh /var/lib/docker/containers/*/

# 限制日志大小（daemon.json）
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

---

## 四、网络问题排查

### 4.1 容器间无法通信

```bash
# 查看网络列表
docker network ls

# 查看网络详情
docker network inspect <网络名>

# 容器加入同一网络
docker network connect <网络名> <容器名>

# 测试容器间连通
docker exec <容器A> ping <容器B的IP>
```

### 4.2 宿主机访问容器

```bash
# 端口映射是否正确
docker port <容器名>

# 检查防火墙
sudo firewall-cmd --list-ports
```

### 4.3 DNS 解析问题

容器内 `ping` IP 通但域名不通：
```bash
# 检查容器 DNS 配置
docker exec <容器名> cat /etc/resolv.conf

# 自定义 DNS
docker run --dns 8.8.8.8 --dns 114.114.114.114 <镜像名>
```

---

## 五、Docker Compose 常用场景

### 5.1 基础模板

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DB_HOST=mysql
      - DB_PASSWORD=${MYSQL_PASSWORD}
    depends_on:
      mysql:
        condition: service_healthy
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      retries: 5

volumes:
  mysql_data:
```

### 5.2 常用命令

```bash
# 启动所有服务
docker-compose up -d

# 重新构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f --tail=100

# 重启单个服务
docker-compose restart <服务名>

# 停止并删除
docker-compose down -v
```
