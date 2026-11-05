# 证据索引

这套文件用来回答一个问题：**“你说测了，凭什么信？”**

## 适用范围

- 标签：`v1.4.2`（干净历史，不包含原 docx）
- 工作树：**clean**；pytest 直接跑 tag 代码
- 本地测试：`pytest` **38 passed**；见 `pytest.txt`
- CI：仓库尚未公开，**不引用 CI URL**；公开并产生可访问运行记录后再补
- 原始技术文档 docx：不在本仓库/包中；只保留公开摘要或比赛提交材料

## 文件

| 文件 | 内容 |
|---|---|
| `pytest.txt` | `pytest` 原始输出，末行 `38 passed` |
| `pytest-collect.txt` | 按测试文件统计的用例数 |
| `test-names.txt` | 38 个测试函数名与行号 |
| `test-inventory.md` | 测试文件 → 覆盖内容 → 对应需求 |
| `doctor.txt` | 无仪器自检输出，含 `MainWindow 构建成功` |
| `git-info.txt` | tag、工作树状态、remote |
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
- 公开摘要见 `docs/competition/技术文档_公开版.md`；原 docx 只保留在比赛材料中。
