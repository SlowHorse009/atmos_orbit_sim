import pandas as pd
import os

def save_parquet(df: pd.DataFrame, output_path: str):
    """将 DataFrame 极速压缩存入 Parquet"""
    # 确保 output 文件夹存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 强制使用咱们定好的 pyarrow 引擎
    df.to_parquet(output_path, engine='pyarrow', index=False)
    print(f"数据已成功落盘至: {output_path}")