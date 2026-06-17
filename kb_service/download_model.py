"""
BGE-M3 模型下载脚本
优先使用 ModelScope 国内镜像（比 HuggingFace 直连快很多）
"""
import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_MODEL_DIR = os.path.join(BASE_DIR, "local_models", "BAAI", "bge-m3")


def is_model_ready(path: str) -> bool:
    """检查本地模型是否可用"""
    if not os.path.isdir(path):
        return False
    for name in ("config.json", "pytorch_model.bin", "model.safetensors"):
        if os.path.isfile(os.path.join(path, name)):
            return True
    # ModelScope 可能嵌套一层
    for root, _, files in os.walk(path):
        if "config.json" in files and (
            "pytorch_model.bin" in files or "model.safetensors" in files
        ):
            return True
    return False


def download_via_modelscope() -> str:
    print("[download_model] 使用 ModelScope 镜像下载 BAAI/bge-m3 ...")
    print("[download_model] 仅下载 PyTorch 权重（跳过 onnx 约 2GB，避免重复下载）")
    from modelscope import snapshot_download

    cache_root = os.path.join(BASE_DIR, "local_models")
    model_dir = snapshot_download(
        "BAAI/bge-m3",
        cache_dir=cache_root,
        revision="master",
        # 跳过 ONNX 导出（约 2.1GB）及图片，sentence-transformers 只需 PyTorch 权重
        ignore_patterns=[
            "onnx/**",
            "onnx/*",
            "*.onnx",
            "imgs/**",
            "*.jpg",
            "long.jpg",
            "README.md",
        ],
    )
    print(f"[download_model] ModelScope 下载完成: {model_dir}")
    return model_dir


def download_via_hf_mirror() -> str:
    print("[download_model] 使用 HuggingFace 镜像下载 BAAI/bge-m3 ...")
    from huggingface_hub import snapshot_download

    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    snapshot_download(
        repo_id="BAAI/bge-m3",
        local_dir=LOCAL_MODEL_DIR,
        endpoint=os.environ.get("HF_ENDPOINT", "https://hf-mirror.com"),
        ignore_patterns=["onnx/**", "*.onnx", "imgs/**", "*.jpg"],
    )
    print(f"[download_model] HF 镜像下载完成: {LOCAL_MODEL_DIR}")
    return LOCAL_MODEL_DIR


def ensure_bge_m3() -> str:
    if is_model_ready(LOCAL_MODEL_DIR):
        print(f"[download_model] 本地模型已存在: {LOCAL_MODEL_DIR}")
        return LOCAL_MODEL_DIR

    # 扫描 local_models 下是否已有 ModelScope 缓存
    bge_root = os.path.join(BASE_DIR, "local_models", "BAAI")
    if os.path.isdir(bge_root):
        for name in os.listdir(bge_root):
            candidate = os.path.join(bge_root, name)
            if is_model_ready(candidate):
                print(f"[download_model] 使用已有缓存: {candidate}")
                return candidate

    try:
        return download_via_modelscope()
    except Exception as e:
        print(f"[download_model] ModelScope 失败: {e}")
        print("[download_model] 回退到 HuggingFace 镜像 ...")
        return download_via_hf_mirror()


if __name__ == "__main__":
    path = ensure_bge_m3()
    print(f"\n✅ BGE-M3 就绪: {path}")
    sys.exit(0)
