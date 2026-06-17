# 修改说明

本文按功能模块整理当前版本的主要改动，便于交付、验收和后续维护时快速查阅。

## GUI 输入与参数范围

### 轨道参数

- 半长轴 `a` 范围调整为 `6.4e6 ~ 8e10 m`，避免下界低于地球半径，同时支持高轨和高椭圆轨道输入。
- 离心率 `e` 上界调整为 `0.99`，支持高偏心率轨道场景。
- 目标高度 `target_alt_km` 下界调整为 `20 km`，更贴近临边大气探测任务语义。

### 物理与摄动参数

- 质量 `mass_kg` 范围调整为 `0.1 ~ 50000 kg`。
- 对风面积 `cross_section_m2` 范围调整为 `0.0001 ~ 20 m²`。
- 重力场阶数和次数约束为 `0 ~ 21`，其中 HPOP 最大为 21。
- ANALYTICAL 模式下 `gravity_degree` 联动范围为 `2 ~ 5`，避免 Brouwer-Lyddane 缺少 J2 项。
- 焦距 `focal_length_mm` 上界调整为 `50000 mm`。

### 光学参数

- 光学参数区新增“工作波长”输入。
- 字段名为 `payload_optics.wavelength_nm`。
- GUI 默认值为 `760.0 nm`，输入范围为 `100 ~ 20000 nm`。
- 工作波长作为载荷元数据写入结果表，便于后续按谱段归档和分析。

## 垂直与水平视场角

- 单一旧字段 `fov_deg` 的语义明确为“垂直视场角”。
- 新增 `payload_optics.vertical_fov_deg`，用于显式传入垂直视场角。
- 新增 `payload_optics.horizontal_fov_deg`，用于传入水平视场角。
- 旧字段 `payload_optics.fov_deg` 保留为兼容字段；当 `vertical_fov_deg` 未提供时，后端会把 `fov_deg` 当作垂直视场角使用。
- `horizontal_fov_deg` 未提供时默认等于垂直视场角。
- 垂直视场角继续用于 FOV 高度范围计算，保证原有视场高度语义不变。
- 水平视场角用于地球覆盖轨迹分析面板的左右边界和覆盖范围绘制。

## 光学几何与覆盖边界

- `LimbOpticsSimulator` 内部新增：
  - `vertical_fov_deg`
  - `vertical_fov_rad`
  - `horizontal_fov_deg`
  - `horizontal_fov_rad`
- FOV 高度范围计算显式使用垂直视场角。
- 新增水平视场左右边界临边切点计算。
- 输出表新增水平视场边界字段：
  - `fov_left_lat`
  - `fov_left_lon`
  - `fov_right_lat`
  - `fov_right_lon`
- 输出表新增视场角元数据：
  - `vertical_fov_deg`
  - `horizontal_fov_deg`

## 输出字段调整

### 观测时间

- 输出表新增 `observation_time_utc`。
- 该字段表示每一帧对应的真实 UTC 观测时间，由 Orekit 当前传播时刻 `AbsoluteDate` 生成。
- `observation_time_utc` 与 `time_sec` 一一对应，可直接用于绝对时间展示、归档和外部系统对接。

### 卫星速度

输出表新增：

- `sat_vx`：卫星 ECEF/ITRF X 向速度，单位 `m/s`
- `sat_vy`：卫星 ECEF/ITRF Y 向速度，单位 `m/s`
- `sat_vz`：卫星 ECEF/ITRF Z 向速度，单位 `m/s`
- `sat_speed_mps`：速度模长，单位 `m/s`

### LOS 轴夹角

- LOS 方向输出统一为 VVLH/LVLH 三轴夹角。
- 当前字段为：
  - `los_angle_to_vvlh_plus_x_deg`
  - `los_angle_to_vvlh_plus_y_deg`
  - `los_angle_to_vvlh_plus_z_deg`
- 三个字段均表示 LOS 与对应正轴的夹角，范围为 `0 ~ 180 deg`。
- 当前局部轨道/VVLH 坐标系定义为：
  - `+X` 沿飞行方向
  - `+Y` 沿轨道负法向 `v x r`，即 `-(r x v)`
  - `+Z` 指向天底
- 如需相对负轴夹角，可用 `180 - 对应正轴夹角`。
- 旧的水平面俯角字段不再作为当前输出 schema 的字段。

## ANALYTICAL 传播器修正

- 原实现使用 Brouwer-Lyddane 默认构造器，部分轨道会在 osculating-to-mean 转换阶段报 `unable to compute Brouwer-Lyddane mean parameters after 201 iterations`。
- 当前实现使用 `PropagationType.MEAN` 初始化 ANALYTICAL 传播器，将 GUI 或配置传入的六根数按 mean elements 处理，避免默认转换不收敛。
- 后端会将 ANALYTICAL 模式的 `gravity_degree` 钳制到 `2 ~ 5`。

## GUI 图表与交互

### 面板名称

当前 2x2 仪表板面板名称为：

- `1. 地球覆盖轨迹分析面板`
- `2. 载荷视场分析面板`
- `3. 姿态机动与噪声分析面板`
- `4. 轨道高度与工作距离分析面板`

第 4 面板中，底层字段 `slant_range_km` 在 GUI 上展示为“工作距离”，字段名和物理含义保持不变。

### 地球覆盖轨迹分析面板

- 显示卫星轨迹、临边切点、日照/地影分类。
- 新增水平视场范围显示：
  - 左右边界线
  - 左右边界之间的浅色覆盖面
  - 沿中心切点轨迹的半透明强调带
  - 少量横向连接线，用于增强左右边界的对应关系
- 覆盖范围在经度跨越 `±180°` 时自动断线，避免世界地图上出现横穿全球的伪线。
- 切点 marker 和图例 marker 缩小，减少对水平视场覆盖范围的遮挡。

### 载荷视场分析面板

- 使用 `fov_alt_min_km` 和 `fov_alt_max_km` 显示垂直视场高度范围。
- 使用 `tangent_alt_km` 显示靶心高度。
- 前端绘图仍会对上下界执行一次 `min/max` 防御性排序，避免异常点影响 `fill_between`。
- 排序结果缓存为 `self.fov_low` 和 `self.fov_high`，供 hover 信息框使用。

### Hover 交互

- 新增 `clear_hover_artists()`，对已失效 Matplotlib 图元做兼容清理。
- hover 清理时忽略 `NotImplementedError`、`ValueError`、`RuntimeError`。
- 每次重新 `render()` 前断开旧 hover 回调，避免重复绑定。
- 修复 hover 清理时可能出现的 `cannot remove artist` 类异常。

## 结果服务调整

- `services.result_service.get_series_data()` 对以下水平视场边界经纬度字段保留空值为 `None`：
  - `fov_left_lon`
  - `fov_left_lat`
  - `fov_right_lon`
  - `fov_right_lat`
- 这样前端可以正确断开无交点或无效点，不会把 NaN 补成 `(0, 0)` 后误画到地图上。
- 其他常规绘图字段仍沿用原有 `fillna(0)` 策略，保持现有图表稳定性。

## 文档同步

- 更新 `readme.md`：
  - 补充垂直/水平视场角说明。
  - 补充工作波长、逐帧 UTC 时间、卫星速度、LOS 三轴夹角和水平覆盖边界字段。
  - 同步 GUI 输入范围、配置结构和输出字段。
- 更新 `docs/api_spec.md`：
  - 补充 payload 字段。
  - 补充输出数据字典。
  - 明确 `fov_deg` 与 `vertical_fov_deg` 的兼容关系。
  - 明确 LOS 三轴夹角字段语义。
- 更新 `docs/ui_interaction_spec.md`：
  - 补充 GUI 控件联动。
  - 补充 2x2 面板名称和绘图字段。
  - 补充水平视场范围显示规则和验收点。
- 更新 `docs/parquet_first_row_reference.json`：
  - 同步核心字段顺序。
  - 补充 `vertical_fov_deg` 和 `horizontal_fov_deg`，供其他模块按首行参考读取视场角元数据。
  - 补充 LOS 三轴夹角字段说明。
  - 补齐 `sat_speed_mps` 的字段说明和首行示例值。
  - 更新首行参考示例。

## 验证项

已执行或建议执行以下检查：

```bash
python -m py_compile core\simulation_engine.py core\optics_simulator.py gui_main.py services\result_service.py test.py
python -m json.tool docs\parquet_first_row_reference.json
git diff --check
```

建议使用代表性配置执行一次短时长仿真，重点确认以下字段可生成并能被 GUI 正常读取：

- `observation_time_utc`
- `wavelength_nm`
- `vertical_fov_deg`
- `horizontal_fov_deg`
- `los_angle_to_vvlh_plus_x_deg`
- `los_angle_to_vvlh_plus_y_deg`
- `los_angle_to_vvlh_plus_z_deg`
- `sat_vx`
- `sat_vy`
- `sat_vz`
- `sat_speed_mps`
- `fov_left_lat`
- `fov_left_lon`
- `fov_right_lat`
- `fov_right_lon`
