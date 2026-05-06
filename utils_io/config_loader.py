import json
import os

def load_config(config_path: str) -> dict:
    """加载仿真任务 JSON 配置文件"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到配置文件: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)