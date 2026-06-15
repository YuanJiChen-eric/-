# Redis 运维手册

> 适用范围：Redis 6.x / 7.x | 最后更新：2026-06

---

## 一、内存管理

### 1.1 内存满的处理

**现象**：写入报 `OOM command not allowed when used memory > 'maxmemory'`

```bash
# 查看内存使用
redis-cli INFO memory
```

**解决策略（按优先级）**：

```bash
# 1. 设置淘汰策略
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 2. 查看大 key
redis-cli --bigkeys

# 3. 查看每个 key 的内存占用
redis-cli MEMORY USAGE <key名>
```

### 1.2 淘汰策略选择

| 策略 | 适用场景 |
|------|---------|
| `noeviction` | 不允许淘汰，写满直接报错 |
| `allkeys-lru` | 淘汰最近最少用的（最常用） |
| `volatile-lru` | 只淘汰设了过期时间的 key |
| `allkeys-random` | 随机淘汰 |
| `volatile-ttl` | 淘汰即将过期的 key |

---

## 二、性能问题

### 2.1 慢查询分析

```bash
# 查看慢查询日志
redis-cli SLOWLOG GET 10

# 配置慢查询阈值（微秒）
redis-cli CONFIG SET slowlog-log-slower-than 10000
redis-cli CONFIG SET slowlog-max-len 128
```

### 2.2 延迟排查

```bash
# 测试延迟
redis-cli --latency

# 查看延迟原因
redis-cli --latency-history
redis-cli --latency-dist

# 检查是否在进行持久化
redis-cli INFO persistence | grep rdb_bgsave_in_progress
```

### 2.3 常见慢操作

| 操作 | 原因 | 替代方案 |
|------|------|---------|
| `KEYS *` | 遍历全库，O(N) | `SCAN` 渐进式遍历 |
| `FLUSHALL` | 阻塞删除 | `FLUSHALL ASYNC` 异步删除 |
| 大 key 的 `DEL` | 阻塞 | `UNLINK` 异步删除 |
| `HGETALL` 大 hash | 一次返回太多 | `HSCAN` 分批 |

---

## 三、持久化配置

### 3.1 RDB 快照

```bash
# 配置文件
save 900 1      # 900秒内至少1次修改则保存
save 300 10     # 300秒内至少10次修改
save 60 10000   # 60秒内至少10000次修改

# 手动触发
redis-cli BGSAVE  # 后台保存
```

### 3.2 AOF 日志

```bash
# 配置文件
appendonly yes
appendfsync everysec   # 每秒同步（推荐，丢1秒数据）

# AOF 重写（压缩）
redis-cli BGREWRITEAOF
```

### 3.3 备份脚本

```bash
#!/bin/bash
# Redis 备份脚本
BACKUP_DIR="/backup/redis"
mkdir -p $BACKUP_DIR

# RDB 备份
cp /var/lib/redis/dump.rdb $BACKUP_DIR/dump_$(date +%Y%m%d_%H%M).rdb

# 保留最近 7 天
find $BACKUP_DIR -name "*.rdb" -mtime +7 -delete
```

---

## 四、集群与哨兵

### 4.1 哨兵模式（Sentinel）

```bash
# 查看主节点
redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster

# 查看所有从节点
redis-cli -p 26379 SENTINEL slaves mymaster

# 手动故障转移
redis-cli -p 26379 SENTINEL failover mymaster
```

### 4.2 集群模式检查

```bash
# 查看集群状态
redis-cli -c CLUSTER INFO

# 查看节点
redis-cli -c CLUSTER NODES

# 检查槽分配
redis-cli -c CLUSTER SLOTS
```

---

## 五、安全加固

```bash
# 设置密码
redis-cli CONFIG SET requirepass "复杂密码"

# 绑定内网 IP
# redis.conf
bind 127.0.0.1 192.168.1.100

# 重命名危险命令
rename-command FLUSHALL ""
rename-command CONFIG "CONFIG_XXXX"
rename-command KEYS ""

# 禁用高危命令
# redis.conf
rename-command FLUSHDB ""
rename-command SHUTDOWN ""
```
