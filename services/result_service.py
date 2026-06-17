import pandas as pd
import os

def _load_result(job_id: str) -> pd.DataFrame:
    """内部小工具：根据 job_id 找文件"""
    path = f"output/{job_id}.parquet"
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到任务数据: {job_id}")
    return pd.read_parquet(path, engine='pyarrow')

def get_job_summary(job_id: str) -> dict:
    """供前端画卡片用：提取统计指标"""
    df = _load_result(job_id)
    summary = {}
    
    # 关心什么字段，就在这里加上
    for col in ["sat_alt_km", "tangent_alt_km", "slant_range_km"]:
        if col in df.columns:
            summary[col] = {
                "min": round(float(df[col].min()), 4),
                "max": round(float(df[col].max()), 4),
                "mean": round(float(df[col].mean()), 4)
            }
    return {"job_id": job_id, "total_frames": len(df), "data": summary}

def get_series_data(job_id: str, fields: list, max_points: int = 1000) -> dict:
    """
    供前端画曲线用：支持同时提取多个关联字段（如 y, p, r 组合），并进行时间轴完全对齐的同步下采样
    """
    df = _load_result(job_id)
    
    # 1. 过滤掉那些在 DataFrame 里不存在的非法字段
    valid_fields = [f for f in fields if f in df.columns]
    if not valid_fields:
        raise ValueError(f"请求的字段不存在: {fields}")
        
    # 2. 提取公共的 time_sec 轴，和所有需要的值
    columns_to_extract = ["time_sec"] + valid_fields
    df_subset = df[columns_to_extract].copy()
    
    # 3. 多维同步下采样
    if len(df_subset) > max_points:
        step = len(df_subset) // max_points
        df_subset = df_subset.iloc[::step]
        
    # 4. 组装 JSON 结构供前端使用
    series_dict = {}
    nullable_geo_fields = {
        "fov_left_lon", "fov_left_lat",
        "fov_right_lon", "fov_right_lat",
    }
    for field in valid_fields:
        # fillna(0) 防止出现 NaN 导致前端图表崩溃
        if field in nullable_geo_fields:
            series_dict[field] = [
                None if pd.isna(value) else value
                for value in df_subset[field].tolist()
            ]
        else:
            series_dict[field] = df_subset[field].fillna(0).tolist()
        
    return {
        "job_id": job_id,
        "time": df_subset["time_sec"].tolist(),
        "series": series_dict
    }
