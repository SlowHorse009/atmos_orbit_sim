# AtmosOrbitSim API 规范

本文面向 GUI、脚本和第三方集成调用方，说明当前 Python 服务 API、配置 payload、输出字段和约束范围。

## 1. 服务 API

### `run_simulation_job(config: dict) -> str`

位置：`services.simulation_service`

启动一个后台仿真任务，并立即返回 `job_id`。

```python
from services.simulation_service import run_simulation_job
from utils_io.config_loader import load_config

config = load_config("configs/config_tc02_locked_forward.json")
job_id = run_simulation_job(config)
print(job_id)
```

后台行为：

- 任务在线程中运行，不阻塞 GUI。
- 仿真结果写入 `output/{job_id}.parquet`。
- 输出目录默认只保留最近 `KEEP_LAST_N = 3` 个 parquet 文件。

### `get_job_info(job_id: str) -> dict`

位置：`services.simulation_service`

查询后台任务状态。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | str | `RUNNING`、`SUCCESS`、`FAILED`、`NOT_FOUND` |
| `current` | int | 当前完成步数 |
| `total` | int | 总步数 |
| `msg` | str | 失败时的错误消息 |
| `deleted_files_at_start` | list | 任务开始前清理的旧 parquet |
| `deleted_files` | list | 任务结束后清理的旧 parquet |

### `get_series_data(job_id: str, fields: list, max_points: int = 1000) -> dict`

位置：`services.result_service`

读取 parquet 中的时间序列字段，并按 `max_points` 下采样。

```python
from services.result_service import get_series_data

data = get_series_data(job_id, [
    "sat_lat",
    "sat_lon",
    "sat_alt_km",
    "sat_speed_mps",
    "tangent_alt_km"
])

t = data["time"]
sat_speed = data["series"]["sat_speed_mps"]
```

返回结构：

```json
{
  "job_id": "job_xxxxxxxx",
  "time": [0.0, 1.0, 2.0],
  "series": {
    "sat_speed_mps": [7684.9, 7684.8, 7684.7]
  }
}
```

### `get_job_summary(job_id: str) -> dict`

位置：`services.result_service`

读取结果并返回部分核心字段的统计信息。目前统计 `sat_alt_km`、`tangent_alt_km`、`slant_range_km`。

### `export_job_data(job_id: str, target_absolute_path: str, format_type: str = "csv") -> bool`

位置：`services.export_service`

导出指定任务结果，支持 `csv` 和 `parquet`。

```python
from services.export_service import export_job_data

ok = export_job_data(job_id, r"D:/result.csv", "csv")
```

## 2. Payload 结构

GUI 的 `build_payload()` 会生成如下结构，脚本调用也应保持一致。

```json
{
  "orbit_propagation": {
    "model": "HPOP",
    "epoch_iso": "2026-05-01T12:00:00.000Z",
    "duration_sec": 5400.0,
    "step_sec": 1.0,
    "a": 6878137.0,
    "e": 0.001,
    "i": 97.5,
    "raan": 30.0,
    "arg_pe": 90.0,
    "m0": 0.0,
    "tle_line1": null,
    "tle_line2": null,
    "mass_kg": 1200.0,
    "cross_section_m2": 6.5,
    "cd": 2.2,
    "cr": 1.2,
    "perturbations": {
      "gravity_degree": 21,
      "gravity_order": 21,
      "enable_thirdbody": true,
      "enable_drag": true,
      "enable_srp": false
    }
  },
  "payload_optics": {
    "wavelength_nm": 760.0,
    "fov_deg": null,
    "vertical_fov_deg": null,
    "horizontal_fov_deg": null,
    "focal_length_mm": 2000.0,
    "sensor_size_mm": 32.5,
    "mounting_angles": {
      "mount_roll_deg": 68.0,
      "mount_pitch_deg": 0.0,
      "mount_yaw_deg": 0.0
    }
  },
  "attitude_control": {
    "mode": "DYNAMIC",
    "target_alt_km": 400.0,
    "locked_angle_deg": null,
    "perturbations": {
      "enable_noise": true,
      "drift_rate_arcsec_s": 0.05,
      "jitter_3sigma_arcsec": 1.5
    }
  }
}
```

## 3. 输入字段和范围

### 轨道传播

| 字段 | 类型 | GUI 范围 | 说明 |
| --- | --- | --- | --- |
| `model` | str | `HPOP` / `SGP4` / `ANALYTICAL` / `TWOBODY` | 轨道传播模型 |
| `epoch_iso` | str | ISO-8601 | 初始历元。SGP4 模式优先使用 TLE 历元 |
| `duration_sec` | float | 1 ~ 1e7 s | 仿真时长 |
| `step_sec` | float | 0.1 ~ 1000 s | 输出步长 |
| `a` | float | 6.4e6 ~ 8e10 m | 半长轴 |
| `e` | float | 0 ~ 0.99 | 离心率 |
| `i` | float | 0 ~ 180 deg | 倾角 |
| `raan` | float | 0 ~ 360 deg | 升交点赤经 |
| `arg_pe` | float | 0 ~ 360 deg | 近地点幅角 |
| `m0` | float | 0 ~ 360 deg | 平近点角 |
| `tle_line1` | str | TLE 文本 | SGP4 使用 |
| `tle_line2` | str | TLE 文本 | SGP4 使用 |

输入角度默认按“度”传给后端，`SimulationEngine` 会统一转成弧度。

高偏心率轨道应额外保证近地点合理：

```text
a * (1 - e) > Earth radius + minimum perigee altitude
```

### 物理和摄动

| 字段 | 类型 | GUI 范围 | 说明 |
| --- | --- | --- | --- |
| `mass_kg` | float | 0.1 ~ 50000 kg | HPOP/ANALYTICAL 使用 |
| `cross_section_m2` | float | 0.0001 ~ 20 m² | Drag 或 SRP 启用时使用 |
| `cd` | float | 0.5 ~ 5 | 大气阻力系数 |
| `cr` | float | 0.5 ~ 3 | 太阳辐射压反射系数 |
| `gravity_degree` | int | HPOP: 0 ~ 21; ANALYTICAL: 2 ~ 5 | HPOP 最大 21；ANALYTICAL 使用 Brouwer-Lyddane，至少需要 J2 项 |
| `gravity_order` | int | 0 ~ 21 | 仅 HPOP 使用 |
| `enable_thirdbody` | bool | true/false | 日月三体摄动 |
| `enable_drag` | bool | true/false | 大气阻力 |
| `enable_srp` | bool | true/false | 太阳辐射压 |

注意：ANALYTICAL 模式下 Brouwer-Lyddane 需要至少 J2 项，后端会将 JSON 中小于 2 的 `gravity_degree` 钳制到 2。

### 光学载荷

| 字段 | 类型 | GUI 范围 | 说明 |
| --- | --- | --- | --- |
| `wavelength_nm` | float | 100 ~ 20000 nm | 工作波长，作为输出元数据写入 parquet |
| `vertical_fov_deg` | float/null | 0.1 ~ 60 deg | 垂直视场角，视场角模式使用，用于 FOV 高度范围 |
| `horizontal_fov_deg` | float/null | 0.1 ~ 60 deg | 水平视场角，视场角模式使用，用于地球覆盖轨迹分析面板左右边界 |
| `fov_deg` | float/null | 0.1 ~ 60 deg | 旧字段，兼容为 `vertical_fov_deg` |
| `focal_length_mm` | float/null | 10 ~ 50000 mm | 焦距模式使用 |
| `sensor_size_mm` | float/null | 1 ~ 100 mm | 焦距模式使用 |
| `mount_roll_deg` | float | -180 ~ 180 deg | 相机安装滚转角 |
| `mount_pitch_deg` | float | -180 ~ 180 deg | 相机安装俯仰角 |
| `mount_yaw_deg` | float | -180 ~ 180 deg | 相机安装偏航角 |

`vertical_fov_deg` / `fov_deg` 与 `focal_length_mm + sensor_size_mm` 二选一，不能同时提供。`fov_deg` 是旧字段，当前语义等同于垂直视场角。`horizontal_fov_deg` 未提供时默认等于垂直视场角；焦距模式下如未显式提供水平视场角，则水平/垂直视场角均由 `sensor_size_mm` 和 `focal_length_mm` 推导为同一值。

### 姿态控制

| 字段 | 类型 | GUI 范围 | 说明 |
| --- | --- | --- | --- |
| `mode` | str | `DYNAMIC` / `LOCKED` | 姿态控制模式 |
| `target_alt_km` | float/null | 20 ~ 1000 km | 目标临边切点高度 |
| `locked_angle_deg` | float/null | -90 ~ 90 deg | 固定锁定角 |
| `enable_noise` | bool | true/false | 是否启用姿态噪声 |
| `drift_rate_arcsec_s` | float | 0 ~ 10 arcsec/s | 热漂移率 |
| `jitter_3sigma_arcsec` | float | 0 ~ 100 arcsec | 抖动 3σ |

## 4. 输出数据字典

结果文件为：

```text
output/{job_id}.parquet
```

| 字段 | 类型 | 单位 | 说明 |
| --- | --- | --- | --- |
| `observation_time_utc` | string | UTC ISO-8601 | 相较上一版本新增。每一帧真实 UTC 时间，由 Orekit 当前传播时刻生成 |
| `time_sec` | float | s | 相对仿真起点的时间 |
| `wavelength_nm` | float | nm | 工作波长 |
| `vertical_fov_deg` | float | deg | 当前仿真使用的垂直视场角 |
| `horizontal_fov_deg` | float | deg | 当前仿真使用的水平视场角 |
| `los_angle_to_vvlh_plus_x_deg` | float | deg | LOS 与当前局部轨道/VVLH `+X` 轴的夹角，范围 0~180 |
| `los_angle_to_vvlh_plus_y_deg` | float | deg | LOS 与当前局部轨道/VVLH `+Y` 轴的夹角，范围 0~180 |
| `los_angle_to_vvlh_plus_z_deg` | float | deg | LOS 与当前局部轨道/VVLH `+Z` 轴的夹角，范围 0~180 |
| `sat_x`, `sat_y`, `sat_z` | float | m | 卫星 ECEF/ITRF 位置 |
| `sat_vx`, `sat_vy`, `sat_vz` | float | m/s | 卫星 ECEF/ITRF 速度分量 |
| `sat_speed_mps` | float | m/s | 卫星速度模长 |
| `sat_lat`, `sat_lon` | float | deg | 卫星大地纬度、经度 |
| `sat_alt_km` | float | km | 卫星高度 |
| `sat_roll_deg`, `sat_pitch_deg`, `sat_yaw_deg` | float | deg | 姿态角 |
| `attitude_noise_deg` | float | deg | 注入的姿态噪声 |
| `tangent_lat`, `tangent_lon` | float | deg | 临边切点纬度、经度 |
| `tangent_alt_km` | float | km | 临边切点高度 |
| `slant_range_km` | float | km | 卫星到切点斜距 |
| `fov_left_lat`, `fov_left_lon` | float | deg | 水平视场左边界临边切点纬度、经度 |
| `fov_right_lat`, `fov_right_lon` | float | deg | 水平视场右边界临边切点纬度、经度 |
| `fov_alt_min_km` | float | km | FOV 下边界高度，后端已保证 min <= max |
| `fov_alt_max_km` | float | km | FOV 上边界高度，后端已保证 max >= min |
| `sat_in_eclipse` | bool | - | 卫星是否处于地影 |
| `tangent_in_eclipse` | bool | - | 切点是否处于地影 |

LOS 角度说明：当前局部轨道/VVLH 坐标系定义为 `+X` 沿飞行方向、`+Y` 沿轨道负法向 `v x r`（即 `-(r x v)`）、`+Z` 指向天底。当前输出使用三轴夹角字段 `los_angle_to_vvlh_plus_x_deg`、`los_angle_to_vvlh_plus_y_deg`、`los_angle_to_vvlh_plus_z_deg`，均为 LOS 与对应正轴的夹角。如需相对负轴夹角，可用 `180 - 对应正轴夹角`。

第一行字段参考见 `docs/parquet_first_row_reference.json`。

## 5. 错误处理

| 异常 | 常见原因 | 建议 |
| --- | --- | --- |
| `ValueError` | 配置缺失或参数冲突 | 检查 payload 结构、FOV/焦距模式二选一 |
| `FileNotFoundError` | parquet 或 `orekit-data.zip` 缺失 | 检查 `output/{job_id}.parquet` 和 `data/orekit-data.zip` |
| `OrekitException` / `JavaError` | 轨道或摄动设置超出 Orekit 数据能力 | 检查半长轴、离心率、重力场阶数/次数、TLE |

## 6. 集成示例

```python
import time
from utils_io.config_loader import load_config
from services.simulation_service import run_simulation_job, get_job_info
from services.result_service import get_series_data
from services.export_service import export_job_data

config = load_config("configs/config_tc02_locked_forward.json")
job_id = run_simulation_job(config)

while True:
    info = get_job_info(job_id)
    if info["status"] == "RUNNING":
        print(info["current"], "/", info["total"])
        time.sleep(0.5)
    elif info["status"] == "SUCCESS":
        break
    else:
        raise RuntimeError(info.get("msg", info["status"]))

data = get_series_data(job_id, ["sat_speed_mps", "tangent_alt_km"])
export_job_data(job_id, f"output/{job_id}.csv", "csv")
```

## 7. 变更记录

### 2026-06-11

- 新增 GUI 工作波长输入 `payload_optics.wavelength_nm`。
- 输出新增 `observation_time_utc`、`los_angle_to_vvlh_plus_y_deg`、`sat_vx`、`sat_vy`、`sat_vz`、`sat_speed_mps`。
- `observation_time_utc` 的语义为逐帧真实 UTC 时间，不是固定初始历元。
- 同步 GUI 参数上下界。
- 修复 GUI hover 清理已失效 Matplotlib artist 时的异常。

### 2026-06-17

- 光学输入新增 `vertical_fov_deg` 和 `horizontal_fov_deg`。
- 旧字段 `fov_deg` 保留兼容，语义等同于垂直视场角。
- 输出新增 `vertical_fov_deg`、`horizontal_fov_deg`、`fov_left_lat`、`fov_left_lon`、`fov_right_lat`、`fov_right_lon`。
- 地球覆盖轨迹分析面板使用水平视场角绘制左右边界、浅色覆盖范围和强调带。

### 2026-06-17 LOS 字段补充

- 移除旧的水平面俯角字段。
- 新增 `los_angle_to_vvlh_plus_x_deg` 和 `los_angle_to_vvlh_plus_z_deg`。
- LOS 方向输出统一为相对 VVLH/LVLH `+X/+Y/+Z` 三个正轴的夹角字段，范围均为 `0~180 deg`。
