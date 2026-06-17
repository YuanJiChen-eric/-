#!/usr/bin/env bash
# 一键部署 kb_service（首次运行）
set -e
cd "$(dirname "$0")"
PYTHON="${PYTHON:-/opt/anaconda3/bin/python}"

echo "==> 1/5 安装依赖"
$PYTHON -m pip install -r requirements.txt -q

echo "==> 2/5 下载 BGE-M3 模型"
HF_ENDPOINT=https://hf-mirror.com $PYTHON download_model.py

echo "==> 3/5 清洗文档"
$PYTHON data_clean.py

echo "==> 4/5 重建知识库"
HF_ENDPOINT=https://hf-mirror.com $PYTHON rebuild_kb.py

echo "==> 5/5 启动服务"
echo "执行: HF_ENDPOINT=https://hf-mirror.com $PYTHON main.py"
echo "健康检查: curl http://127.0.0.1:8000/api/kb/health"
