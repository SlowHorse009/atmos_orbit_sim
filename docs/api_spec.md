# 🔌 AtmosOrbitSim API 规范 (Frontend Integration Guide)

**适用对象**：前端工程师、集成开发、第三方服务调用

---

## 概览 (Overview)

AtmosOrbitSim 提供两层 API 接口：

1. **本地 Python API** (`services/` 层)：用于同一进程内的直接调用（PyQt5 GUI）
2. **配置 JSON** (`configs/` 目录)：任务参数规范

本文档重点说明如何通过 Python API 调度仿真、获取结果、管理数据生命周期。
当前 GUI 默认把轨道角度字段按“度”传入，后端再统一转换为弧度。

---

## 本地 API (Python Services)

### 1. 模块：`services.simulation_service`

#### 函数：`run_simulation_job(config: dict) -> str`

**作用**：启动异步仿真任务，立即返回 job ID。

**参数**：
- `config` (dict)：仿真配置，详见 [配置文件规范](#配置文件规范-config-file-format) 一节。

**返回**：
- `job_id` (str)：格式为 `job_XXXXXXXX`（8 位 16 进制），用于后续查询状态与结果。

**示例**：
```python
from services.simulation_service import run_simulation_job
from utils_io.config_loader import load_config

config = load_config("configs/config_tc01_dynamic_side.json")
job_id = run_simulation_job(config)
print(f"任务已启动: {job_id}")
# 输出: 任务已启动: job_066e1511
```

**后台行为**：
- 在后台线程中执行仿真，不阻塞调用者。
- 每次任务开始前，自动清理旧 parquet 文件（保留最近 `KEEP_LAST_N=3` 个）。
- 仿真完成后，自动写入 `output/{job_id}.parquet`。

---

#### 函数：`get_job_info(job_id: str) -> dict`

**作用**：查询指定 job 的实时状态与进度。

**参数**：
- `job_id` (str)：任务 ID，由 `run_simulation_job()` 返回。

**返回**：一个字典，包含以下键值：

| 键名 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| `status` | str | 任务状态 | `"RUNNING"` / `"SUCCESS"` / `"FAILED"` / `"NOT_FOUND"` |
| `current` | int | 当前进度（步数） | `120` |
| `total` | int | 总步数 | `360` |
| `msg` | str | （仅当 status=FAILED）错误信息 | `"ValueError: invalid epoch_iso"` |
| `deleted_files` | list | 完成后删除的旧 parquet 文件列表 | `["output/job_xxx.parquet"]` |

**示例**：
```python
from services.simulation_service import get_job_info
import time

job_id = "job_066e1511"
while True:
    info = get_job_info(job_id)
    if info["status"] == "RUNNING":
        pct = (info.get("current", 0) / info.get("total", 100)) * 100
        print(f"进度: {pct:.1f}%")
        time.sleep(0.5)
    elif info["status"] == "SUCCESS":
        print(f"✅ 任务完成！删除了 {len(info.get('deleted_files', []))} 个旧文件")
        break
    elif info["status"] == "FAILED":
        print(f"❌ 任务失败: {info.get('msg', '未知错误')}")
        break
    else:
        print(f"❓ 任务不存在")
        break
```

---

### 2. 模块：`services.result_service`

#### 函数：`get_series_data(job_id: str, fields: list) -> dict`

**作用**：从已完成的仿真结果中提取指定字段的时间序列数据。

**参数**：
- `job_id` (str)：任务 ID。
- `fields` (list)：所需字段名列表。支持的字段见 [数据字典](#数据字典)。

**返回**：一个字典，包含：
- `"time"` (list)：时间戳数组（秒）。
- `"series"` (dict)：按字段名映射到数据数组的字典。

**示例**：
```python
from services.result_service import get_series_data

job_id = "job_066e1511"
data = get_series_data(job_id, [
    "time_sec", 
    "sat_lat", "sat_lon", "sat_alt_km",
    "tangent_lat", "tangent_lon", "tangent_alt_km",
    "sat_in_eclipse", "tangent_in_eclipse",
    "fov_alt_min_km", "fov_alt_max_km"
])

t = data["time"]                          # [0, 10, 20, ..., 3600]
sat_lats = data["series"]["sat_lat"]      # [35.2, 35.1, 35.0, ...]
fov_min = data["series"]["fov_alt_min_km"] # [400, 401, 399, ...]

print(f"时间点数: {len(t)}")
print(f"卫星纬度范围: [{min(sat_lats):.2f}, {max(sat_lats):.2f}]")
```

**错误处理**：
- 若 `job_id` 不存在或 parquet 文件缺失，返回空字典或抛出 `FileNotFoundError`。
- 若字段名不存在，会被忽略；请根据实际返回的键来确定。

---

#### 函数：`export_job_data(job_id: str, target_absolute_path: str, format_type: str = "csv") -> bool`

**作用**：将指定 job 的结果导出到前端提供的绝对路径（支持 `csv` 或 `parquet`）。实现位于 `services/export_service.py`。

**参数**：
- `job_id` (str)：任务 ID。
- `target_absolute_path` (str)：目标系统绝对路径（例如 `D:/data.csv` 或 `/home/user/data.parquet`）。
- `format_type` (str)：`"csv"` 或 `"parquet"`（默认 `"csv"`）。

**返回**：bool，导出是否成功。

**示例**：
```python
from services.export_service import export_job_data

job_id = "job_066e1511"
ok = export_job_data(job_id, r"D:/results/simulation_result.csv", "csv")
print(f"导出完成: {ok}")
```

---

### 3. 模块：`utils_io.config_loader`

#### 函数：`load_config(config_path: str) -> dict`

**作用**：加载并解析 JSON 配置文件。

**参数**：
- `config_path` (str)：相对或绝对路径到 `.json` 配置文件。

**返回**：解析后的配置字典。

**示例**：
```python
from utils_io.config_loader import load_config

config = load_config("configs/config_tc01_dynamic_side.json")
print(config["model"])   # "HPOP"
print(config["duration_sec"])  # 3600
```

---

## 配置文件规范 (Config File Format)

所有配置文件放在 `configs/` 目录，采用 JSON 格式。

### 完整配置示例

```json
{
    "orbit_propagation": {
        "model": "HPOP",
        "epoch_iso": "2026-05-06T00:00:00Z",
        "duration_sec": 3600,
        "step_sec": 10,
        "a": 6878137.0,
        "e": 0.001,
        "i": 97.5,
        "raan": 0.0,
        "arg_pe": 0.0,
        "m0": 0.0,
        "tle_line1": null,
        "tle_line2": null,
        "mass_kg": 1000.0,
        "cross_section_m2": 5.0,
        "cd": 2.5,
        "cr": 1.2,
        "perturbations": {
            "gravity_degree": 10,
            "gravity_order": 10,
            "enable_thirdbody": true,
            "enable_drag": true,
            "enable_srp": true
        }
    },
    "payload_optics": {
        "fov_deg": 1.2,
        "mounting_angles": {
            "mount_roll_deg": 68.0,
            "mount_pitch_deg": 0.0,
            "mount_yaw_deg": 0.0
        }
    },
    "attitude_control": {
        "mode": "DYNAMIC",
        "target_alt_km": 400,
        "locked_angle_deg": null,
        "perturbations": {
            "enable_noise": true,
            "drift_rate_arcsec_s": 0.1,
            "jitter_3sigma_arcsec": 1.0
        }
    }
}
```

### 字段说明

#### 轨道参数 (Orbital Parameters)

| 字段 | 类型 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `model` | str | `"HPOP"` | `"HPOP"` \| `"SGP4"` \| `"ANALYTICAL"` \| `"TWOBODY"` | 轨道传播模型 |
| `epoch_iso` | str | *required* | ISO 8601 格式 | 仿真初始时刻，如 `"2026-05-06T00:00:00Z"` |
| `duration_sec` | int | *required* | > 0 | 仿真总时长（秒）|
| `step_sec` | int | *required* | > 0 | 输出时间步长（秒）|
| `a` | float | *required* | > 6378137 | 轨道半长轴（米）|
| `e` | float | *required* | [0, 1) | 轨道离心率 |
| `i` | float | *required* | [0, 180] | 轨道倾角（度）|
| `raan` | float | 0 | [0, 360) | 升交点赤经（度）|
| `arg_pe` | float | 0 | [0, 360) | 近地点幅角（度）|
| `m0` | float | 0 | [0, 360) | 平近点角（度）|
| `tle_line1` | str | null | TLE 格式 | 两行根数第 1 行（仅 SGP4 使用）|
| `tle_line2` | str | null | TLE 格式 | 两行根数第 2 行（仅 SGP4 使用）|
| `mass_kg` | float | 1000.0 | > 0 | 航天器质量（千克）|
| `cross_section_m2` | float | 5.0 | > 0 | 受光/受阻迎风面积（平方米）|
| `cd` | float | 2.2 | > 0 | 阻力系数（Cd）|
| `cr` | float | 1.2 | > 0 | 太阳辐射压反射系数（Cr）|

#### 扰动参数 (Perturbation Parameters)

| 字段 | 类型 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `enable_drag` | bool | `true` | — | 是否启用大气阻力 (NRLMSISE00) |
| `enable_srp` | bool | `true` | — | 是否启用太阳光压 |
| `enable_thirdbody` | bool | `true` | — | 是否启用日月第三体引力 |
| `gravity_degree` | int | 10 | [0, 21] | 重力场阶数 |
| `gravity_order` | int | 10 | [0, 21] | 重力场次数（仅在 HPOP 模式有效）。对于 `ANALYTICAL` 模式，内部只使用 `gravity_degree` 的前 5 阶（J2~J5），`gravity_order` 无需设置。|

#### 姿态与光学参数 (Attitude & Optics)

| 字段 | 类型 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `target_alt_km` | float | 400 | > 0 | 姿态控制目标高度（公里）|
| `locked_angle_deg` | float | null | [-180, 180] | 锁定姿态角（仅 LOCKED 模式使用，单位：度）|
| `enable_noise` | bool | `false` | — | 是否注入姿态噪声 |
| `drift_rate_arcsec_s` | float | 0.1 | ≥ 0 | 热漂移速率（角秒/秒）|
| `jitter_3sigma_arcsec` | float | 1.0 | ≥ 0 | 飞轮微振(3-sigma)（角秒）|
| `fov_deg` | float | 1.2 | > 0 | 视场角（度）。如果使用焦距/传感器模式，则改填 `focal_length_mm` 与 `sensor_size_mm`。|

#### 光学安装参数 (Payload Mounting)

| 字段 | 类型 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `mount_roll_deg` | float | 68.0 | [0, 360] | 安装滚转角（度）|
| `mount_pitch_deg` | float | 0.0 | [-180, 180] | 安装俯仰角（度）|
| `mount_yaw_deg` | float | 0.0 | [0, 360] | 安装偏航角（度）|

#### 焦距/传感器模式 (Alternative Optics Mode)

| 字段 | 类型 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `focal_length_mm` | float | null | > 0 | 焦距（毫米）|
| `sensor_size_mm` | float | null | > 0 | 传感器尺寸（毫米）|

#### SGP4 特定参数 (SGP4-specific)

当 `model == "SGP4"` 时，可用以下替代字段：

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| `tle_line1` | str | TLE 第一行（North American Aerospace Defense Command 格式）| `"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"` |
| `tle_line2` | str | TLE 第二行 | `"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"` |

若同时提供 `tle_line1/2` 和传统轨道参数，TLE 优先。

---

## 数据字典 (Data Dictionary)

结果 parquet 文件中可用的字段及其含义（由 `core/simulation_engine.py` 实际输出）：

| 字段名 | 类型 | 单位 | 说明 |
| --- | --- | --- | --- |
| **时间** | | | |
| `time_sec` | float | 秒 | 仿真时间（相对于 epoch_iso）|
| **卫星位置** | | | |
| `sat_x`, `sat_y`, `sat_z` | float | 米 | 卫星在 WGS84 ITRF 地固坐标系下的笛卡尔坐标 |
| `sat_lat` | float | 度 | 星下点 WGS84 纬度（-90 ~ +90）|
| `sat_lon` | float | 度 | 星下点 WGS84 经度（-180 ~ +180）|
| `sat_alt_km` | float | 公里 | 卫星轨道高度（椭球面以上）|
| **卫星姿态** | | | |
| `sat_roll_deg` | float | 度 | 滚转角（绕卫星速度方向，±180）|
| `sat_pitch_deg` | float | 度 | 俯仰角（绕横轴，-90 ~ +90）|
| `sat_yaw_deg` | float | 度 | 偏航角（绕竖轴，±180）|
| `attitude_noise_deg` | float | 度 | 实时注入的姿态噪声（热漂 + 抖动）|
| **临边切点** | | | |
| `tangent_lat` | float | 度 | 临边切点 WGS84 纬度 |
| `tangent_lon` | float | 度 | 临边切点 WGS84 经度 |
| `tangent_alt_km` | float | 公里 | 临边切点高度（在大气探测模式下通常为 0~100 km）|
| **光学与距离** | | | |
| `slant_range_km` | float | 公里 | 卫星至临边切点的斜距 |
| `fov_alt_min_km` | float | 公里 | 视场下边界高度*（标准化，保证 ≤ fov_alt_max_km）* |
| `fov_alt_max_km` | float | 公里 | 视场上边界高度*（标准化，保证 ≥ fov_alt_min_km）* |
| **日期-地球-日光状态** | | | |
| `sat_in_eclipse` | bool | — | 卫星是否处于地球阴影内 |
| `tangent_in_eclipse` | bool | — | 临边切点是否处于地球阴影内 |

**注意**：
- 所有输入角度字段默认按“度”传给后端，后端统一转弧度。
- `fov_alt_min_km` 和 `fov_alt_max_km` 在后端生产阶段已自动排序，保证 min ≤ max；前端无需再做交换。
- Parquet 文件采用 snappy 压缩，相比 CSV 可减少 ~70% 存储空间。

---

## 错误处理 (Error Handling)

### 异常类型

| 异常 | 原因 | 建议处理 |
| --- | --- | --- |
| `ValueError` | 配置参数非法（如 epoch_iso 格式错误、轨道参数不合理） | 验证配置文件，参考 [配置文件规范](#配置文件规范-config-file-format) |
| `FileNotFoundError` | 找不到 parquet 文件或 orekit-data.zip | 确保 `data/orekit-data.zip` 存在；检查 job_id 是否正确 |
| `OrekitException` | Orekit 核心库错误（多为物理约束不满足） | 检查轨道参数、扰动设置是否合理 |

### 推荐的错误处理模式

```python
from services.simulation_service import run_simulation_job, get_job_info

try:
    job_id = run_simulation_job(config)
    
    while True:
        info = get_job_info(job_id)
        
        if info["status"] == "SUCCESS":
            print("✅ 仿真完成")
            break
        elif info["status"] == "FAILED":
            error_msg = info.get("msg", "Unknown error")
            print(f"❌ 仿真失败: {error_msg}")
            # 可根据错误信息决定是否重试、记录日志等
            break
        elif info["status"] == "NOT_FOUND":
            print("❓ 任务 ID 不存在")
            break
            
except ValueError as e:
    print(f"配置错误: {e}")
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
except Exception as e:
    print(f"未预期的错误: {e}")
```

---

## 集成示例 (Integration Example)

### 场景：从配置文件启动仿真并导出结果

```python
import time
from utils_io.config_loader import load_config
from services.simulation_service import run_simulation_job, get_job_info
from services.result_service import get_series_data
from services.export_service import export_job_data

# 1. 加载配置
config = load_config("configs/config_tc01_dynamic_side.json")

# 2. 启动仿真
print("📡 启动仿真...")
job_id = run_simulation_job(config)
print(f"Job ID: {job_id}")

# 3. 轮询等待完成
print("⏳ 等待仿真完成...")
while True:
    info = get_job_info(job_id)
    
    if info["status"] == "RUNNING":
        progress = (info["current"] / info["total"]) * 100
        print(f"  进度: {progress:.1f}% ({info['current']}/{info['total']})")
        time.sleep(1)
    elif info["status"] == "SUCCESS":
        print(f"✅ 仿真完成!")
        if info.get("deleted_files"):
            print(f"  清理了 {len(info['deleted_files'])} 个旧文件")
        break
    elif info["status"] == "FAILED":
        print(f"❌ 仿真失败: {info.get('msg')}")
        exit(1)

# 4. 提取结果数据
print("📊 提取数据...")
data = get_series_data(job_id, [
    "sat_lat", "sat_lon", "sat_alt_km",
    "tangent_lat", "tangent_lon", "tangent_alt_km",
    "fov_alt_min_km", "fov_alt_max_km",
    "sat_in_eclipse"
])

print(f"  共 {len(data['time'])} 个时间点")
print(f"  卫星高度范围: [{min(data['series']['sat_alt_km']):.1f}, {max(data['series']['sat_alt_km']):.1f}] km")

# 5. 导出为 CSV 或 Parquet
print("💾 导出结果...")
ok = export_job_data(job_id, f"output/{job_id}_result.csv", "csv")
print(f"  导出成功: {ok}")

print("\n✨ 完成！")
```

---

## Parquet 文件清理策略 (Cleanup Strategy)

### 自动清理

每次启动新仿真时，后端自动清理，仅保留最近 `KEEP_LAST_N = 3` 个 parquet 文件。

```python
# services/simulation_service.py
KEEP_LAST_N = 3  # 可在此修改

def _keep_last_n_parquet(pattern="output/*.parquet", n=KEEP_LAST_N):
    # 保留最新的 n 个文件，删除其余
    ...
```

### 手动清理

```bash
python scripts/cleanup_parquet.py --n 3
```

---

## 常见问题 (FAQ)

**Q: 如何在 GUI 中使用这些 API？**  
A: `gui_ultimate.py` 已内置这些 API 调用。具体实现见 `gui_ultimate.py` 的 `run_simulation()` 和 `render()` 方法。

**Q: 能否同时启动多个仿真任务？**  
A: 可以。每个 `run_simulation_job()` 调用独立启动后台线程，互不干扰。但注意 parquet 清理是全局的（会影响所有 job）。

**Q: FOV 高度在数据中反向是否需要处理？**  
A: 不需要。后端在生产阶段已自动排序 `fov_alt_min_km ≤ fov_alt_max_km`，前端可直接使用。

**Q: 如何支持自定义重力场或大气模型？**  
A: 修改 `core/orekit_generator.py` 的 `create_propagator()` 方法，扩展模型选项。

---

## 变更日志 (Changelog)

### V4.0 (2026-05-06)

- ✅ PyQt5 GUI (`gui_ultimate.py`) 上线，集成 4 个子图仪表板。
- ✅ 后端 FOV 高度自动排序，消除前端反向现象。
- ✅ 自动 parquet 清理策略（保留最近 N 个）。
- ✅ 中文化 GUI 界面、hover 交互、地影分类。
- ✅ 补充 `sat_in_eclipse`, `tangent_in_eclipse` 字段。

### V3.x 与更早版本

详见 Git 提交历史。

---

**文档版本**：V4.0 | **最后更新**：2026-05-06
