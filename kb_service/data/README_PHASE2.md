# 数据工程 · 第二阶段交付说明

> 产出：`data_clean.py` → `ops_docs_clean/`
> 更新：2026-06

---

## 本阶段完成内容

### `data_clean.py` — 运维 Markdown 清洗

| 能力 | 说明 |
|------|------|
| 去噪 | 删除控制字符、行尾空格、压缩多余空行 |
| 结构化 | 统一 `#` 标题格式、列表符号 |
| 实体保护 | URL、`systemctl` 等命令、Error 500/502、IP、JDBC、API 路径清洗时不破坏 |

### 用法

```bash
cd kb_service

# 清洗（默认 ops_docs → ops_docs_clean）
/opt/anaconda3/bin/python data_clean.py

# 仅预览
/opt/anaconda3/bin/python data_clean.py --dry-run

# 自定义路径
/opt/anaconda3/bin/python data_clean.py --input ../ops_docs --output ../ops_docs_clean
```

### 与重建流程衔接

`rebuild_kb.py` **自动优先**使用 `ops_docs_clean/`（若存在），否则回退 `ops_docs/`。

```bash
/opt/anaconda3/bin/python data_clean.py
HF_ENDPOINT=https://hf-mirror.com /opt/anaconda3/bin/python rebuild_kb.py
```

---

## BGE-M3 模型下载（ModelScope 镜像）

```bash
/opt/anaconda3/bin/python download_model.py
```

优先 ModelScope 国内源，失败时回退 HF 镜像（`hf-mirror.com`）。

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `data_clean.py` | 第二阶段清洗脚本 |
| `download_model.py` | BGE-M3 模型下载（ModelScope 加速） |
| `ops_docs_clean/` | 清洗后文档（gitignore，本地生成） |

---

## 下一阶段

| 阶段 | 产出 |
|------|------|
| 三 | `ingest.py`（切片 + 向量化入库，与 rebuild_kb 整合） |
| 四 | `feedback_loop.py` |
| 五 | 全员 README |
