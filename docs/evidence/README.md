# 证据索引

这套文件用来回答一个问题：**“你说测了，凭什么信？”**

## 适用范围

- 代码基线：`6367065`（`v1.4.1`）
- 标签：`v1.4.1`
- 本地测试：当前工作树 `pytest`，**38 passed**；见 `pytest.txt`
- CI：仓库尚未公开，**不引用 CI URL，也不把 CI 当作已完成的公开验证**；公开后再补运行记录
- 工作树状态：**dirty**。未提交修改包括 `device/th1992.py`（docstring 去队伍编号）、`ui/control_widget.py`（默认电平 500 mV→50 mV，界面行为变化）、README/docs、恢复原 docx（Git 显示 `M`，包中不包含）、新增 `docs/evidence/`；见 `git-info.txt`
- 因此：当前可验证结论是**本地 pytest 38 passed**；CI 未用于当前工作树。

## 文件

| 文件 | 内容 |
|---|---|
| `pytest.txt` | `pytest` 原始输出，末行 `38 passed` |
| `pytest-collect.txt` | 按测试文件统计的用例数 |
| `test-names.txt` | 38 个测试函数名与行号 |
| `test-inventory.md` | 测试文件 → 覆盖内容 → 对应需求 |
| `doctor.txt` | 无仪器自检输出，含 `MainWindow 构建成功` |
| `git-info.txt` | HEAD、tag、工作树状态、remote |
| `environment.txt` | Python / PyQt5 / pyserial / OS 版本 |
| `sha256sums.txt` | 关键代码、固件工程、测试、文档的 SHA256 |

## 复现

```powershell
cd <完整包根目录>
python -m pytest -q
python doctor.py
```

## 边界

- 这些是**软件层**证据：SCPI 命令序列、状态机、存储、看门狗、假设备流程；
- 不是硬件实测证据：TH2840E/TH1992 的真实返回、CH2 接线、Rg 夹具仍需实机确认；
- CI 尚未作为公开证据；仓库公开并产生可访问的 CI 记录后，再补 URL。
