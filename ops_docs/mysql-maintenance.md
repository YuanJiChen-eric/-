# MySQL 运维手册

> 适用范围：MySQL 5.7 / 8.0 | 最后更新：2026-06

---

## 一、连接问题

### 1.1 连接数过多

**现象**：`Too many connections`

```sql
-- 查看当前连接数
SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS LIKE 'Threads_connected';

-- 查看所有连接
SHOW FULL PROCESSLIST;

-- 找出 Sleep 状态的长时间连接
SELECT id, user, host, db, command, time, state
FROM information_schema.PROCESSLIST
WHERE command = 'Sleep' AND time > 600;

-- 杀掉指定连接
KILL <连接ID>;
```

**永久解决**：
```ini
# my.cnf
[mysqld]
max_connections = 500
wait_timeout = 300          # 非交互连接超时（秒）
interactive_timeout = 300   # 交互连接超时
```

### 1.2 连接慢

**检查 DNS 解析**：
```ini
# my.cnf 中加（跳过 DNS 反向解析）
[mysqld]
skip-name-resolve
```

---

## 二、慢查询优化

### 2.1 开启慢查询日志

```sql
-- 临时开启
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 2;   -- 超过2秒记录

-- 查看设置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';
```

### 2.2 分析执行计划

```sql
-- 查看查询如何执行
EXPLAIN SELECT * FROM orders WHERE user_id = 123;

-- 关键字段解读：
-- type: ALL(全表扫) < index < range < ref < const(最优)
-- rows: 预估扫描行数，越小越好
-- Extra: Using filesort / Using temporary 是坏信号
```

### 2.3 索引优化

```sql
-- 查看表索引
SHOW INDEX FROM 表名;

-- 找出未使用索引的查询
-- 慢查询日志中 rows_examined >> rows_sent 的查询

-- 创建索引
CREATE INDEX idx_user_id ON orders(user_id);

-- 复合索引（注意最左前缀原则）
CREATE INDEX idx_user_status_time ON orders(user_id, status, create_time);
```

### 2.4 常见优化手法

| 问题 | 优化 |
|------|------|
| `SELECT *` | 只查需要的列 |
| 函数包裹索引列 `WHERE DATE(create_time) = '2026-06-01'` | 改为范围查询 `WHERE create_time >= '2026-06-01' AND create_time < '2026-06-02'` |
| `OR` 条件不走索引 | 拆成 UNION ALL |
| `LIKE '%关键词'` | 前缀模糊不走索引，尽量用 `LIKE '关键词%'` |

---

## 三、备份与恢复

### 3.1 逻辑备份（mysqldump）

```bash
# 全量备份
mysqldump -u root -p --all-databases > full_backup_$(date +%Y%m%d).sql

# 单库备份
mysqldump -u root -p 数据库名 > db_backup.sql

# 只备份结构
mysqldump -u root -p --no-data 数据库名 > schema.sql
```

### 3.2 恢复

```bash
# 恢复全量备份
mysql -u root -p < full_backup.sql

# 恢复单库
mysql -u root -p 数据库名 < db_backup.sql
```

### 3.3 误删数据恢复（binlog）

```sql
-- 确认 binlog 是否开启
SHOW VARIABLES LIKE 'log_bin';

-- 查看 binlog 事件
mysqlbinlog --base64-output=DECODE-ROWS -v /var/lib/mysql/binlog.000001

-- 按时间点恢复
mysqlbinlog --start-datetime="2026-06-07 10:00:00" \
            --stop-datetime="2026-06-07 10:30:00" \
            /var/lib/mysql/binlog.000001 | mysql -u root -p
```

---

## 四、锁与事务问题

### 4.1 查看锁等待

```sql
-- MySQL 8.0
SELECT * FROM performance_schema.data_lock_waits;

-- 查看当前事务
SELECT * FROM information_schema.INNODB_TRX;

-- 找出锁等待超时的事务
SELECT * FROM information_schema.INNODB_TRX
WHERE trx_state = 'LOCK WAIT';

-- 杀事务
KILL <trx_mysql_thread_id>;
```

### 4.2 死锁

```sql
-- 查看最近死锁
SHOW ENGINE INNODB STATUS\G
-- 查看 LATEST DETECTED DEADLOCK 部分

-- 开启死锁日志
SET GLOBAL innodb_print_all_deadlocks = ON;
```

---

## 五、日常维护

### 5.1 表优化

```sql
-- 查看表状态
SHOW TABLE STATUS LIKE '表名';

-- 分析表（更新索引统计）
ANALYZE TABLE 表名;

-- 优化表（整理碎片）
OPTIMIZE TABLE 表名;

-- 检查表
CHECK TABLE 表名;
-- 修复表
REPAIR TABLE 表名;
```

### 5.2 主从延迟检查

```sql
-- 在从库执行
SHOW SLAVE STATUS\G
-- 关注 Seconds_Behind_Master 字段（应为 0 或接近 0）
-- Slave_IO_Running 和 Slave_SQL_Running 都应为 Yes
```
