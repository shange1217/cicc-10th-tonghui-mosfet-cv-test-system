# data/

运行时数据目录，默认不提交到 git。

- `measurements.db`：SQLite，`runs` + `measurements` 两张表；
- `mos_YYYYmmdd_HHMMSS.csv`：桌面/本目录导出的测量结果。

表结构：

```sql
runs(id, started_at, run_type, operator, device_sn, calibration_id,
     temperature_c, humidity_pct, note, status)
measurements(id, run_id, timestamp, param, unit, secondary_median, secondary_unit,
             n, median, mean, std, min, max, spread_pct, freq_hz, ac_level_v,
             gate_v, drain_v, relay, function, raw_values)
```

重现：

```powershell
$env:MOS_OPERATOR="your-name"
$env:MOS_DEVICE_SN="TK9J90E"
python main.py
```

示例结果见 `docs/measurement_report.md`。
