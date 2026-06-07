# 备份与恢复策略手册

> 最后更新：2026-06

---

## 一、备份策略设计

### 1.1 3-2-1 原则

- **3** 份数据副本（1 份原件 + 2 份备份）
- **2** 种不同介质（如本地磁盘 + 云端/磁带）
- **1** 份异地存放（防止火灾/地震等）

### 1.2 备份频率建议

| 数据类型 | 备份频率 | 保留周期 |
|---------|---------|---------|
| 数据库 | 每日增量 + 每周全量 | 30 天增量，3 个月全量 |
| 配置文件 | 每次变更后 | 永久 |
| 用户文件 | 每日增量 | 30 天 |
| 日志 | 按需归档 | 按合规要求 |

---

## 二、文件级备份

### 2.1 rsync 增量备份

```bash
# 基本用法
rsync -avz --delete /源目录/ user@backup-server:/备份目录/

# 带时间戳的版本备份
rsync -avz /源目录/ /备份目录/$(date +%Y%m%d)/

# 排除特定文件
rsync -avz --exclude='*.log' --exclude='tmp/' /源目录/ /备份目录/

# 限速（KB/s）
rsync -avz --bwlimit=10000 /源目录/ /备份目录/
```

### 2.2 tar 归档

```bash
# 全量打包
tar -czf backup_$(date +%Y%m%d).tar.gz /path/to/data

# 增量备份（只备份变更文件）
find /path/to/data -mtime -1 -type f | tar -czf incremental_$(date +%Y%m%d).tar.gz -T -
```

---

## 三、数据库备份

### 3.1 MySQL 备份脚本

```bash
#!/bin/bash
# MySQL 自动备份
BACKUP_DIR="/backup/mysql"
DB_USER="root"
DB_PASS="密码"
DB_NAME="ops_db"
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

# 备份
mysqldump -u$DB_USER -p$DB_PASS --single-transaction --routines --triggers \
    $DB_NAME | gzip > $BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d_%H%M).sql.gz

# 清理过期备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "备份完成：$(ls -lh $BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d)*.sql.gz)"
```

### 3.2 Redis 备份

```bash
#!/bin/bash
# Redis RDB 备份
REDIS_DATA="/var/lib/redis"
BACKUP_DIR="/backup/redis"

cp ${REDIS_DATA}/dump.rdb ${BACKUP_DIR}/dump_$(date +%Y%m%d_%H%M).rdb
```

---

## 四、文件恢复

### 4.1 从备份恢复

```bash
# tar 恢复
tar -xzf backup.tar.gz -C /恢复目录/

# rsync 恢复（从备份同步回原目录）
rsync -avz user@backup-server:/备份目录/ /目标目录/

# MySQL 恢复
gunzip < backup.sql.gz | mysql -u root -p 数据库名
```

### 4.2 文件误删恢复（文件服务器快照）

如果文件服务器启用了快照（如 ZFS / NetApp / Windows Shadow Copy）：

```bash
# ZFS 查看快照
zfs list -t snapshot

# 恢复具体文件
cp /pool/.zfs/snapshot/snap_20260601_0000/path/to/file /恢复位置/

# Windows 文件服务器
# 右键文件夹 → 属性 → 以前的版本 → 选择快照日期 → 还原
```

### 4.3 恢复后验证清单

- [ ] 文件数量是否匹配？
- [ ] 关键文件是否能正常打开？
- [ ] 数据库能否正常连接和查询？
- [ ] 应用能否正常启动？
- [ ] 权限是否正确？

---

## 五、灾备演练

### 5.1 演练步骤

1. 在隔离环境中恢复最近一次全量备份
2. 应用增量备份（如有）
3. 启动应用服务
4. 执行冒烟测试（登录、核心功能、数据查询）
5. 记录恢复耗时和遇到的问题
6. 更新预案文档

### 5.2 恢复时间目标（RTO / RPO）

| 指标 | 含义 | 目标 |
|------|------|------|
| RTO | 从故障到恢复服务的时间 | < 2 小时 |
| RPO | 可接受的数据丢失量 | < 24 小时 |

---

## 六、备份监控脚本

```bash
#!/bin/bash
# 检查备份是否正常执行
BACKUP_DIR="/backup"
WARN_AGE=2  # 超过2天没备份就告警

LATEST_BACKUP=$(find $BACKUP_DIR -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2)

if [ -z "$LATEST_BACKUP" ]; then
    echo "CRITICAL: 没有找到备份文件！"
    exit 2
fi

LAST_BACKUP_DAYS=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 86400 ))

if [ $LAST_BACKUP_DAYS -gt $WARN_AGE ]; then
    echo "WARNING: 最近备份是 ${LAST_BACKUP_DAYS} 天前！"
    exit 1
else
    echo "OK: 最近备份于 $(date -d @$(stat -c %Y "$LATEST_BACKUP") '+%Y-%m-%d %H:%M')"
    exit 0
fi
```
