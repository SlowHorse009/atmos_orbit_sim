import pandas as pd

path = "output/job_de264e7b.parquet"
df = pd.read_parquet(path)

print("行数:", len(df))
print("列名:")
print(df.columns.tolist())

print("\n前5行:")
print(df.head())

print("\n关键字段检查:")
for col in [
    "observation_time_utc",
    "wavelength_nm",
    "los_angle_to_vvlh_plus_x_deg",
    "los_angle_to_vvlh_plus_y_deg",
    "los_angle_to_vvlh_plus_z_deg",
    "sat_alt_km",
    "sat_x",
    "sat_y",
    "sat_z",
    "sat_vx",
    "sat_vy",
    "sat_vz",
    "sat_speed_mps",
    "tangent_lat",
    "tangent_lon",
    "tangent_alt_km"
]:
    if col in df.columns:
        print(f"\n{col}:")
        print("  非空数量:", df[col].notna().sum())
        print("  唯一值数量:", df[col].nunique(dropna=False))
        print("  前几个唯一值:", df[col].drop_duplicates().head(10).tolist())
        print("  min:", df[col].min() if pd.api.types.is_numeric_dtype(df[col]) else "非数值列")
        print("  max:", df[col].max() if pd.api.types.is_numeric_dtype(df[col]) else "非数值列")
    else:
        print(f"\n缺少字段: {col}")
