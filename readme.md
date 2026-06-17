# AtmosOrbitSim V4.0

AtmosOrbitSim 是一个基于 Python + Orekit 的临边大气探测轨道与光学几何仿真工具。项目支持多种轨道传播模型、WGS84 临边切点求解、载荷视场计算、姿态控制仿真、地影判断，并将结果保存为 Parquet/CSV。

## 主要能力

- 轨道传播：`HPOP`、`SGP4`、`ANALYTICAL`、`TWOBODY`
- 高保真摄动：地球重力场、日月三体、大气阻力、太阳辐射压
- 光学载荷：垂直/水平视场角模式、焦距/传感器尺寸模式、安装角、工作波长
- 姿态控制：动态目标高度跟踪、固定锁定角、热漂移与抖动噪声
- 输出数据：逐帧 UTC 时间、卫星位置、卫星速度、临边切点、FOV 高度范围、水平视场覆盖边界、光照/地影状态

## 目录结构

```text
atmos_orbit_sim/
├── configs/                  # JSON 仿真配置
├── core/                     # 物理模型与仿真核心
├── data/                     # orekit-data.zip
├── docs/                     # 接口、字段与变更说明
├── output/                   # 生成的 parquet 结果
├── services/                 # 异步任务、结果读取、导出服务
├── utils_io/                 # 配置和 parquet 工具
├── gui_main.py               # PyQt5 GUI 入口
├── main.py                   # 命令行入口
└── test.py                   # parquet 字段检查脚本
```

## 环境准备

建议使用 `orbit_env` 环境运行 GUI 和仿真：

```bash
conda activate orbit_env
python gui_main.py
```

项目需要 `data/orekit-data.zip`。如果缺失，请从 Orekit 官方数据包下载后放入：

```text
data/orekit-data.zip
```

## GUI 输入范围

当前 GUI 输入框的主要范围如下，单位以界面后缀为准。

| 参数 | 范围 | 默认值 | 说明 |
| --- | ---: | ---: | --- |
| 仿真时长 `duration_sec` | 1 ~ 1e7 s | 5400 s | 建议结合步长控制总帧数 |
| 仿真步长 `step_sec` | 0.1 ~ 1000 s | 1 s | 越小输出帧数越多 |
| 半长轴 `a` | 6.4e6 ~ 8e10 m | 6878137 m | 覆盖 LEO 到高轨/深空扩展输入 |
| 离心率 `e` | 0 ~ 0.99 | 0.001 | 高偏心率需保证近地点不进入地球 |
| 倾角/RAAN/近地点幅角/平近点角 | 0 ~ 180 或 0 ~ 360 deg | 见界面 | 按角度输入，后端转为弧度 |
| 质量 `mass_kg` | 0.1 ~ 50000 kg | 1200 kg | HPOP/ANALYTICAL 使用 |
| 面积 `cross_section_m2` | 0.0001 ~ 20 m² | 6.5 m² | Drag 或 SRP 启用时使用 |
| 阻力系数 `cd` | 0.5 ~ 5 | 2.2 | Drag 启用时使用 |
| 光压系数 `cr` | 0.5 ~ 3 | 1.2 | SRP 启用时使用 |
| 重力场阶数 `gravity_degree` | HPOP: 0 ~ 21; ANALYTICAL: 2 ~ 5 | 21 | ANALYTICAL 使用 Brouwer-Lyddane，至少需要 J2 项 |
| 重力场次数 `gravity_order` | 0 ~ 21 | 21 | 仅 HPOP 使用 |
| 工作波长 `wavelength_nm` | 100 ~ 20000 nm | 760 nm | 写入输出列 `wavelength_nm` |
| 垂直视场角 `vertical_fov_deg` / `fov_deg` | 0.1 ~ 60 deg | 2 deg | 原 `fov_deg` 兼容为垂直视场角，用于 FOV 高度范围 |
| 水平视场角 `horizontal_fov_deg` | 0.1 ~ 60 deg | 2 deg | 用于地球覆盖轨迹分析面板的左右边界和覆盖范围 |
| 焦距 `focal_length_mm` | 10 ~ 50000 mm | 2000 mm | 焦距模式使用 |
| 传感器尺寸 `sensor_size_mm` | 1 ~ 100 mm | 32.5 mm | 焦距模式使用 |
| 安装滚转/俯仰/偏航角 | -180 ~ 180 deg | 见界面 | 相机相对平台安装角 |
| 目标高度 `target_alt_km` | 20 ~ 1000 km | 400 km | 动态控制目标临边切点高度 |
| 锁定角 `locked_angle_deg` | -90 ~ 90 deg | 68 deg | 固定锁定模式使用 |
| 姿态漂移率 | 0 ~ 10 arcsec/s | 0.05 | 噪声启用时使用 |
| 姿态抖动 3σ | 0 ~ 100 arcsec | 1.5 | 噪声启用时使用 |

## 配置文件结构

典型 JSON 配置如下：

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

说明：

- `vertical_fov_deg` / `fov_deg` 与 `focal_length_mm + sensor_size_mm` 二选一；旧字段 `fov_deg` 保留兼容，语义等同于垂直视场角。
- `horizontal_fov_deg` 用于计算地球覆盖轨迹分析面板中的水平视场左右边界；未提供时默认等于垂直视场角。
- `SGP4` 模式使用 `tle_line1` / `tle_line2`，六根数可忽略。
- `ANALYTICAL` 模式只使用 `gravity_degree`，内部按 Brouwer-Lyddane 模型处理。
- `wavelength_nm` 当前作为载荷元数据写入结果表，便于后续按谱段归档和分析。

## 输出数据

仿真结束后，后台任务会生成：

```text
output/{job_id}.parquet
```

核心输出字段如下：

| 字段 | 单位 | 说明 |
| --- | --- | --- |
| `observation_time_utc` | UTC ISO-8601 | 相较上一版本新增。每一帧对应的真实 UTC 时间，由 Orekit 当前传播时刻生成 |
| `time_sec` | s | 相对仿真起点的秒数 |
| `wavelength_nm` | nm | GUI 或配置传入的工作波长 |
| `vertical_fov_deg`, `horizontal_fov_deg` | deg | 每帧写入的垂直/水平视场角元数据 |
| `los_angle_to_vvlh_plus_x_deg` | deg | LOS 与当前局部轨道/VVLH `+X` 轴的夹角，范围 0~180 |
| `los_angle_to_vvlh_plus_y_deg` | deg | LOS 与当前局部轨道/VVLH `+Y` 轴的夹角，范围 0~180 |
| `los_angle_to_vvlh_plus_z_deg` | deg | LOS 与当前局部轨道/VVLH `+Z` 轴的夹角，范围 0~180 |
| `sat_x`, `sat_y`, `sat_z` | m | 卫星在 WGS84 ITRF/ECEF 下的位置 |
| `sat_vx`, `sat_vy`, `sat_vz` | m/s | 卫星在 WGS84 ITRF/ECEF 下的速度分量 |
| `sat_speed_mps` | m/s | 卫星速度模长 |
| `sat_lat`, `sat_lon`, `sat_alt_km` | deg, km | 卫星大地纬度、经度、高度 |
| `sat_roll_deg`, `sat_pitch_deg`, `sat_yaw_deg` | deg | 姿态角 |
| `attitude_noise_deg` | deg | 注入的姿态噪声 |
| `tangent_lat`, `tangent_lon`, `tangent_alt_km` | deg, km | 临边切点位置与高度 |
| `slant_range_km` | km | 卫星到切点斜距 |
| `fov_left_lat`, `fov_left_lon` | deg | 水平视场左边界对应临边切点纬度、经度 |
| `fov_right_lat`, `fov_right_lon` | deg | 水平视场右边界对应临边切点纬度、经度 |
| `fov_alt_min_km`, `fov_alt_max_km` | km | 视场上下边界对应高度，已保证 min <= max |
| `sat_in_eclipse` | bool | 卫星是否处于地影 |
| `tangent_in_eclipse` | bool | 临边切点是否处于地影 |

LOS 角度说明：当前局部轨道/VVLH 坐标系定义为 `+X` 沿飞行方向、`+Y` 沿轨道负法向 `v x r`（即 `-(r x v)`）、`+Z` 指向天底。当前输出使用三轴夹角字段 `los_angle_to_vvlh_plus_x_deg`、`los_angle_to_vvlh_plus_y_deg`、`los_angle_to_vvlh_plus_z_deg`，均为 LOS 与对应正轴的夹角。如需相对负轴夹角，可用 `180 - 对应正轴夹角`。

第一行字段参考见 [docs/parquet_first_row_reference.json](docs/parquet_first_row_reference.json)。

## 检查输出

可以用项目里的 `test.py` 检查 parquet 字段：

```bash
conda activate orbit_env
python test.py
```

`test.py` 会打印列名、前几行数据，并检查 `observation_time_utc`、`wavelength_nm`、`vertical_fov_deg`、`horizontal_fov_deg`、`los_angle_to_vvlh_plus_x_deg`、`los_angle_to_vvlh_plus_y_deg`、`los_angle_to_vvlh_plus_z_deg`、`sat_vx/sat_vy/sat_vz`、`sat_speed_mps` 等关键字段。

## 常见问题

| 问题 | 可能原因 | 处理 |
| --- | --- | --- |
| `ImportError: No module named 'orekit'` | Python 环境不对 | 使用 `orbit_env` 或安装 Orekit |
| `orekit-data.zip` 缺失 | 数据包未放入 `data/` | 下载并放置到 `data/orekit-data.zip` |
| GUI hover 报 `cannot remove artist` | 旧 hover 图元已被重绘清理 | 当前版本已在 hover 清理逻辑中兼容 |
| 输出帧数过多 | 时长过长或步长过小 | 增大 `step_sec` 或缩短 `duration_sec` |
