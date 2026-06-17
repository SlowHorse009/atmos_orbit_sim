# AtmosOrbitSim UI 交互说明

本文说明当前推荐 GUI：`gui_main.py` 的控件联动、payload 生成、任务状态流转和图表交互行为。

## 1. 页面状态

| 状态 | 触发 | UI 行为 |
| --- | --- | --- |
| `IDLE` | 程序启动 | 等待用户输入参数 |
| `RUNNING` | 点击“启动” | 调用 `run_simulation_job(payload)`，每 200 ms 查询 `get_job_info(job_id)` |
| `SUCCESS` | 后端任务成功 | 进度条置 100，调用 `render()` 绘图，启用“导出” |
| `FAILED` | 后端任务失败 | 停止轮询，进度条归零，日志显示 `msg`，禁用“导出” |
| `NOT_FOUND` | 任务状态丢失 | 停止轮询，日志提示任务不存在或丢失 |

## 2. 参数输入区

### 2.1 轨道传播参数

| 控件 | 对应 payload 字段 | 范围/选项 |
| --- | --- | --- |
| 模型 | `orbit_propagation.model` | `HPOP`、`SGP4`、`ANALYTICAL`、`TWOBODY` |
| 仿真历元 | `epoch_iso` | ISO-8601 字符串 |
| 仿真时长 | `duration_sec` | 1 ~ 1e7 s |
| 仿真步长 | `step_sec` | 0.1 ~ 1000 s |
| 半长轴 | `a` | 6.4e6 ~ 8e10 m |
| 离心率 | `e` | 0 ~ 0.99 |
| 倾角 | `i` | 0 ~ 180 deg |
| 升交点赤经 | `raan` | 0 ~ 360 deg |
| 近地点幅角 | `arg_pe` | 0 ~ 360 deg |
| 平近点角 | `m0` | 0 ~ 360 deg |
| TLE 第 1 行 | `tle_line1` | SGP4 使用 |
| TLE 第 2 行 | `tle_line2` | SGP4 使用 |

联动规则：

- 选择 `SGP4` 时禁用六根数输入，启用 TLE 输入。
- 选择非 `SGP4` 时启用六根数输入，TLE 输入可留空。

### 2.2 物理和摄动参数

| 控件 | 对应 payload 字段 | 范围/选项 |
| --- | --- | --- |
| 质量 | `mass_kg` | 0.1 ~ 50000 kg |
| 对风面积 | `cross_section_m2` | 0.0001 ~ 20 m² |
| 阻力系数 | `cd` | 0.5 ~ 5 |
| 光压系数 | `cr` | 0.5 ~ 3 |
| 重力模型阶数 | `gravity_degree` | HPOP: 0 ~ 21; ANALYTICAL: 2 ~ 5 |
| 重力模型次数 | `gravity_order` | 0 ~ 21 |
| 三体摄动 | `enable_thirdbody` | 勾选/不勾选 |
| 大气阻力 | `enable_drag` | 勾选/不勾选 |
| 太阳辐射压 | `enable_srp` | 勾选/不勾选 |

联动规则：

- `mass_kg` 与 `gravity_degree` 仅在 `HPOP` 或 `ANALYTICAL` 模式启用。
- `gravity_degree` 在 `ANALYTICAL` 模式范围为 2 ~ 5，在 `HPOP` 模式范围为 0 ~ 21。
- `gravity_order`、三体摄动、大气阻力、太阳辐射压仅在 `HPOP` 模式启用。
- `cross_section_m2` 仅在 `HPOP` 且 Drag 或 SRP 至少一个启用时可编辑。
- `cd` 仅在 `HPOP` 且 Drag 启用时可编辑。
- `cr` 仅在 `HPOP` 且 SRP 启用时可编辑。

### 2.3 光学参数

| 控件 | 对应 payload 字段 | 范围/选项 |
| --- | --- | --- |
| 模式 | - | `视场角模式`、`焦距模式` |
| 工作波长 | `payload_optics.wavelength_nm` | 100 ~ 20000 nm |
| 垂直视场角 | `payload_optics.vertical_fov_deg` / `payload_optics.fov_deg` | 0.1 ~ 60 deg |
| 水平视场角 | `payload_optics.horizontal_fov_deg` | 0.1 ~ 60 deg |
| 焦距 | `focal_length_mm` | 10 ~ 50000 mm |
| 传感器尺寸 | `sensor_size_mm` | 1 ~ 100 mm |
| 安装滚转角 | `mounting_angles.mount_roll_deg` | -180 ~ 180 deg |
| 安装俯仰角 | `mounting_angles.mount_pitch_deg` | -180 ~ 180 deg |
| 安装偏航角 | `mounting_angles.mount_yaw_deg` | -180 ~ 180 deg |

联动规则：

- `视场角模式`：启用垂直视场角、水平视场角，禁用 `focal_length_mm` 和 `sensor_size_mm`。
- `焦距模式`：禁用垂直视场角、水平视场角，启用 `focal_length_mm` 和 `sensor_size_mm`。
- `fov_deg` 作为旧字段继续随垂直视场角一起输出，便于兼容旧配置和旧调用。
- `wavelength_nm` 不参与几何联动，始终可编辑并写入结果表。

### 2.4 姿态参数

| 控件 | 对应 payload 字段 | 范围/选项 |
| --- | --- | --- |
| 控制模式 | `attitude_control.mode` | `DYNAMIC`、`LOCKED` |
| 使用目标高度 | `target_alt_km` | 20 ~ 1000 km |
| 使用锁定角 | `locked_angle_deg` | -90 ~ 90 deg |
| 启用姿态噪声 | `enable_noise` | 勾选/不勾选 |
| 姿态漂移速率 | `drift_rate_arcsec_s` | 0 ~ 10 arcsec/s |
| 姿态抖动 3σ | `jitter_3sigma_arcsec` | 0 ~ 100 arcsec |

联动规则：

- `动态控制`：强制使用目标高度，禁用锁定角。
- `固定锁定`：允许在目标高度和锁定角之间二选一。
- 勾选“启用姿态噪声”后，漂移速率和抖动输入框启用。

## 3. Payload 生成

点击“启动”时，GUI 调用 `build_payload()` 生成如下结构：

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
      "enable_noise": false,
      "drift_rate_arcsec_s": 0.05,
      "jitter_3sigma_arcsec": 1.5
    }
  }
}
```

## 4. 绘图流程

当任务状态变为 `SUCCESS`：

1. 停止状态轮询。
2. 调用 `render()`。
3. `render()` 使用 `get_series_data()` 读取绘图字段。
4. 清空旧图、清理旧 hover 临时图元，并断开旧 hover 回调。
5. 绘制 2x2 仪表板。
6. 缓存 `current_time_data`、`current_series_data`、`main_axes`、`vline_axes`、`time_axes`。
7. 绑定新的 `motion_notify_event` hover 回调。
8. 启用导出按钮。

## 5. 图表布局

| 子图 | 内容 |
| --- | --- |
| 1 | 地球覆盖轨迹分析面板：卫星点、切点、日照/地影分类、水平视场覆盖范围 |
| 2 | 载荷视场分析面板：视场高度范围与靶心高度 |
| 3 | 姿态机动与噪声分析面板：姿态角与姿态噪声，双 y 轴 |
| 4 | 轨道高度与工作距离分析面板：卫星高度与工作距离，双 y 轴 |

当前 GUI 绘图字段包括：

- `sat_lon`, `sat_lat`
- `tangent_lon`, `tangent_lat`
- `fov_left_lon`, `fov_left_lat`
- `fov_right_lon`, `fov_right_lat`
- `sat_in_eclipse`, `tangent_in_eclipse`
- `tangent_alt_km`
- `fov_alt_min_km`, `fov_alt_max_km`
- `sat_roll_deg`, `sat_pitch_deg`, `sat_yaw_deg`
- `attitude_noise_deg`
- `sat_alt_km`
- `slant_range_km`

`observation_time_utc` 是相较上一版本新增的输出字段，表示每一帧真实 UTC 观测时间。当前默认仪表板横轴仍使用 `time_sec`，如需显示绝对时间，可在后续 UI 中读取该字段并格式化展示。

速度字段已在 parquet 中输出，但当前默认仪表板暂未绘制 `sat_speed_mps`。

## 6. Hover 交互

触发事件：`motion_notify_event`

清理策略：

- 每次 hover 前调用 `clear_hover_artists()`。
- 对已经被 Matplotlib 重绘清理的 artist，忽略 `NotImplementedError`、`ValueError`、`RuntimeError`。
- 每次重新 `render()` 前断开旧 hover 回调，避免重复绑定。

地图子图 hover：

- 根据鼠标经纬度寻找最近的卫星点或切点。
- 命中阈值为 2 度。
- 高亮命中点。
- 在所有时间轴同步绘制竖线。
- 地图左上显示切点信息，左下显示卫星信息。

时间轴 hover：

- 仅在图 2、图 3、图 4 及其 twin 轴响应。
- 根据鼠标横坐标寻找最近时间索引。
- 所有时间轴同步竖线。
- 各子图显示对应摘要信息。

## 7. FOV 显示约定

- 后端已保证 `fov_alt_min_km <= fov_alt_max_km`。
- 前端绘图仍会用 `min/max` 再做一次防御性排序，避免异常点影响 `fill_between`。
- 排序结果缓存为 `self.fov_low` 和 `self.fov_high`，供 hover 信息框使用。
- 垂直视场角用于图 2 的 FOV 高度范围，也就是旧 `fov_deg` 的原始语义。
- 水平视场角用于图 1“地球覆盖轨迹分析面板”。GUI 会读取 `fov_left_lon/lat` 和 `fov_right_lon/lat`，绘制左右边界、浅色覆盖面、横向连接线和一条固定屏幕宽度的半透明强调带。
- 水平覆盖面和边界在经度跨越 `±180°` 时会自动断线，避免在世界地图上画出横穿全球的伪线。
- `services.result_service.get_series_data()` 对水平视场边界经纬度保留 `None`，不将无交点的 NaN 补成 0，前端据此断开覆盖范围。

## 8. 导出流程

点击“导出”：

1. 弹出保存路径选择框。
2. 当前实现默认导出 CSV。
3. 调用 `export_job_data(self.current_job_id, path, "csv")`。

## 9. 验收要点

- 切换 `SGP4` 时六根数禁用，TLE 输入启用。
- 切换 `HPOP` / `ANALYTICAL` 时重力阶数上限正确变化。
- Drag/SRP 开关能正确控制面积、`cd`、`cr` 输入框。
- 光学模式能正确切换垂直/水平视场角与焦距/传感器尺寸。
- 旧字段 `fov_deg` 与 `vertical_fov_deg` 保持一致。
- “地球覆盖轨迹分析面板”能显示水平视场范围、左右边界和强调带。
- 工作波长始终可编辑，并进入 `payload_optics.wavelength_nm`。
- 动态控制强制目标高度，固定锁定允许目标高度/锁定角二选一。
- 任务成功后能绘图、hover、导出。
- 多次运行后 hover 不应重复绑定或抛 `cannot remove artist`。
