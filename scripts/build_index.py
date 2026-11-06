"""在项目根目录执行：uv run python -m scripts.build_index。"""
from huggingface_hub import snapshot_download
from app.rag import MODEL_PATH, build_index


if __name__ == "__main__":
    # 首次下载中文 embedding 模型，仅保留推理所需文件，避免下载其他格式副本
    if not (MODEL_PATH / "model.safetensors").exists():
        snapshot_download(
            repo_id="BAAI/bge-small-zh-v1.5", local_dir=str(MODEL_PATH),
            allow_patterns=["*.json", "*.txt", "*.safetensors", "*.model"],
            ignore_patterns=["onnx/*", "openvino/*"],
        )
    print(f"索引建立完成，共 {build_index()} 条规则。")
