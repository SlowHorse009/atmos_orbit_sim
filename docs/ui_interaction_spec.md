# AtmosOrbitSim UI 联动说明 (UI Interaction Spec)

本文档用于给前端工程师快速理解 UI 控件联动、任务状态流和图表交互。

## 1. 适用范围

- 当前推荐界面：`gui_ultimate.py`
- 备用界面：`gui_main.py`
- 后端接口：`services/simulation_service.py`、`services/result_service.py`、`services/export_service.py`
- API 字段说明：`docs/api_spec.md`

## 2. 页面状态机

- `IDLE`：初始状态，未提交任务。
- `RUNNING`：点击“启动”后，调用 `run_simulation_job(payload)`，开始轮询 `get_job_info(job_id)`。
- `SUCCESS`：状态变为 `SUCCESS`，停止轮询，进度条到 100，触发 `render()` 绘图，启用“导出”按钮。
- `FAILED`：状态变为 `FAILED`，停止轮询，进度条归零，日志显示错误，禁用导出。
- `NOT_FOUND`：任务不存在，停止轮询，进度条归零，日志提示任务丢失。

## 3. 控件联动规则

### 3.1 轨道模型联动 (`update_model`)

- 选择 `SGP4`：
  - 禁用六根数输入：`a/e/i/raan/arg_pe/m0`
  - 启用 TLE 输入：`tle_line1/tle_line2`
- 选择 `HPOP` 或 `ANALYTICAL`：
  - 启用 `mass_kg` 和 `gravity_degree`
- `gravity_degree` 上限：
  - `ANALYTICAL`：最大 5
  - `HPOP`：最大 21
- 仅 `HPOP` 启用：
  - `gravity_order`
  - `enable_thirdbody`
  - `enable_drag`
  - `enable_srp`
- `cross_section_m2`（对风面积）启用条件：
  - 模型为 `HPOP` 且 `drag` 或 `srp` 任一开启
- `cd` 启用条件：`HPOP` 且 `drag` 开启
- `cr` 启用条件：`HPOP` 且 `srp` 开启

### 3.2 光学模式联动 (`update_fov`)

- 视场角模式：启用 `fov_deg`，禁用 `focal_length_mm` 和 `sensor_size_mm`
- 焦距模式：禁用 `fov_deg`，启用 `focal_length_mm` 和 `sensor_size_mm`

### 3.3 姿态模式联动 (`update_att`)

- 动态控制：
  - 强制使用目标高度 (`use_target=True`)
  - 禁用“使用锁定角”
- 固定锁定：
  - 允许“使用目标高度 / 使用锁定角”二选一
  - 按单选状态启用对应输入框

### 3.4 噪声联动 (`update_noise_perturbation`)

- 勾选“启用姿态噪声”后，启用：
  - `drift_rate_arcsec_s`
  - `jitter_3sigma_arcsec`

## 4. 前后端数据流

### 4.1 启动流程

1. UI 调用 `build_payload()` 组装 payload
2. 调用 `run_simulation_job(payload)` 返回 `job_id`
3. 启动 200ms 轮询 `get_job_info(job_id)`

### 4.2 绘图流程

- 当状态变为 `SUCCESS`：
  - 调用 `get_series_data(job_id, fields)`
  - 渲染 2x2 仪表板
  - 缓存 `current_time_data`、`current_series_data`
  - 绑定 hover 事件 `motion_notify_event`

### 4.3 导出流程

- 导出按钮触发 `export_job_data(job_id, path, "csv")`

## 5. Payload 结构 (与 `gui_ultimate.py` 对齐)

```json
{
  "orbit_propagation": {
    "model": "HPOP|SGP4|ANALYTICAL|TWOBODY",
    "epoch_iso": "2026-05-01T12:00:00.000Z",
    "duration_sec": 5400,
    "step_sec": 1,
    "a": 6878137.0,
    "e": 0.001,
    "i": 1.7017,
    "raan": 0.5236,
    "arg_pe": 1.5708,
    "m0": 0.0,
    "tle_line1": null,
    "tle_line2": null,
    "mass_kg": 1200,
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
    "fov_deg": 2.0,
    "focal_length_mm": null,
    "sensor_size_mm": null,
    "mounting_angles": {
      "mount_roll_deg": 68.0,
      "mount_pitch_deg": 0.0,
      "mount_yaw_deg": 0.0
    }
  },
  "attitude_control": {
    "mode": "DYNAMIC|LOCKED",
    "target_alt_km": 400,
    "locked_angle_deg": null,
    "perturbations": {
      "enable_noise": false,
      "drift_rate_arcsec_s": 0.05,
      "jitter_3sigma_arcsec": 1.5
    }
  }
}
```

注：当前 `gui_ultimate.py` 在 `build_payload()` 中会把 `i/raan/arg_pe/m0` 从度转成弧度后发送。

## 6. 图表联动规范

## 6.1 图布局

- 图1：地球覆盖轨迹（卫星 + 切点 + 地影分类）
- 图2：FOV 上下边界 + 切点高度
- 图3：姿态角 + 噪声（双 y 轴）
- 图4：卫星高度 + 斜距（双 y 轴）

## 6.2 Hover 交互

- 触发事件：`motion_notify_event`
- 每次 hover 前先清除上一次临时元素（竖线、文本框、高亮点）
- 地图轴 hover：
  - 用经纬度最近点匹配，阈值 2 度
  - 高亮命中点，并同步所有时间轴竖线
  - 图1显示双信息框：左上“切点”，左下“卫星”
- 时间轴 hover（图2/图3/图4及 twin 轴）：
  - 查最近时间索引
  - 所有轴同步竖线
  - 图2/图3/图4分别显示对应数据摘要

## 6.3 FOV 显示约定

- 后端语义：`fov_alt_min_km <= fov_alt_max_km`
- 前端绘图仍做一次 `min/max` 排序防御，避免异常点导致 `fill_between` 方向错误

## 7. 错误与边界处理

- `FAILED`：日志输出后端 `msg`，禁用导出
- `NOT_FOUND`：提示任务丢失
- 空数据/无索引：hover 不更新，仅刷新画布
- 导出路径为空：不执行导出

## 8. 交付建议

- 前端实现按本文档行为作为验收标准。
- 字段与单位以 `docs/api_spec.md` 为准。
- 当行为与代码冲突时，优先对齐 `gui_ultimate.py` 的当前实现，并同步更新本文档。
