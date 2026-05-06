# 文件：services/export_service.py
import os
import shutil
import pandas as pd

def export_job_data(job_id: str, target_absolute_path: str, format_type: str = "csv") -> bool:
    """
    后端导出服务：负责把数据写进前端指定的系统绝对路径里
    :param target_absolute_path: 前端通过弹窗获取到的用户想保存的路径 (例如 D:/data.csv)
    """
    source_parquet = f"output/{job_id}.parquet"
    
    if not os.path.exists(source_parquet):
        raise FileNotFoundError(f"找不到原始数据文件: {source_parquet}")
        
    try:
        if format_type.lower() == "parquet":
            # 如果导出 parquet，直接用 shutil 极速复制过去，连解析都不需要
            shutil.copy2(source_parquet, target_absolute_path)
            print(f"Parquet 文件已成功复制到: {target_absolute_path}")
            
        elif format_type.lower() == "csv":
            # 如果导出 CSV，就需要用 Pandas 读出来再存过去
            df = pd.read_parquet(source_parquet, engine='pyarrow')
            df.to_csv(target_absolute_path, index=False)
            print(f"CSV 文件已成功转换并保存到: {target_absolute_path}")
            
        return True
    except Exception as e:
        print(f"导出失败: {e}")
        return False