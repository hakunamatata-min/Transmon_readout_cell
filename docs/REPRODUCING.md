# 复现指南

## 1. 浏览展示

在 GitHub 中打开 `Transmon_Readout_Project.ipynb`，或下载
`Transmon_Readout_Presentation.html` 后用浏览器打开。两者均包含已执行的结果。
展示 notebook 的代码只读数据和显示图片，不导入 HFSS，也不自动启动求解器。

## 2. 重算保存数据的分析

在项目根目录执行。已验证的解释器为 Windows x64 / Python 3.14.10。

```console
python -m pip install -r requirements-view.txt
python -m ipykernel install --user --name qmetal2026 --display-name "Quantum Metal 2026"
python analyze.py
python validate_results.py
python build_presentation_figures.py
python build_presentation.py --execute --html
```

此路线使用 `results/` 中保存的 S21 CSV、EPR JSON、收敛与物理检查记录，
不需要安装或运行 AEDT。`analyze.py` 会重新拟合并写入比较表、拟合 JSON 和图。
展示 builder 会保存一份本机旧 notebook 备份到被 Git 忽略的 `tmp/`。

当前依赖锁定的是已安装验证环境，不承诺其他版本组合兼容。

## 3. 从空 HFSS 工程完整运行

需要本机已安装、有授权的 AEDT 2026 R1，以及 Quantum Metal / PyAEDT / pyEPR。
安装完整依赖前，先完成上一节的查看依赖安装。

```console
python -m pip install -r requirements-verified.txt
python run_study.py --project my_readout_cell
python analyze.py
python validate_results.py
```

批量脚本按 200、160、240 μm 顺序，逐组执行 eigen → epr → driven → fine。
fine 阶段会导出窄带数据并更新该组拟合 JSON；批量完成后 `analyze.py` 生成三组比较。
`--project` 不带 `.aedt` 扩展名，工程保存在 `models/` 下。

PyAEDT 负责查找 AEDT 安装目录。若本机未正确注册安装路径，可在启动前自行设置环境变量。
PowerShell 示例（路径需替换为本机实际值）：

```powershell
$env:AEDT_VERSION = '2026.1'
$env:ANSYSEM_ROOT261 = 'YOUR_AEDT_INSTALLATION_DIRECTORY'
```

其他 AEDT / 依赖版本尚未重新验证。`compat.py` 只在当前进程中适配已知接口名称，
不会修改安装目录中的第三方软件包。

## 4. 单独运行某阶段

```console
python run_hfss.py --phase eigen --width 200 --project my_readout_cell
python run_hfss.py --phase epr --width 200 --project my_readout_cell
python run_hfss.py --phase driven --width 200 --project my_readout_cell
python run_hfss.py --phase fine --width 200 --project my_readout_cell
```

EPR 需要已有的本征模场解；driven 默认用本征模频率定位扫频中心；fine 需要定位扫频结果。
可用 `--center` 手动指定定位中心（GHz），`--passes` 指定本征模最大迭代次数。
使用 `--port` 可连接明确的 AEDT gRPC 端口。

导出 200 μm 模态场并生成场图：

```console
python export_fields.py --width 200 --project my_readout_cell
```

`--project` 默认值为 `readout_cell_v2`；使用其他工程名时与前面求解阶段保持一致。

## 5. 修改参数的位置

| 内容 | 位置 |
|---|---|
| 结电感、布线长度、馈线耦合尺寸、衬底厚度 | `cell.py` 的 `DEFAULTS` |
| CPW 宽度和缝隙、主电容板、布局位置 | `cell.py` 的 `make_cell()` |
| 本次读出焊盘宽度 | `make_cell(width)` / `--width` |
| 模式数、网格和收敛标准、扫频设置 | `run_hfss.py` |
| 复数拟合与 Purcell 估算 | `analyze.py` |

两个 `pad_width` 不同：425 μm 是主电容板宽度；`connection_pads.readout.pad_width`
才是本次 160 / 200 / 240 μm 的扫描量。

**修改几何或结参数后，使用新工程名。**当前 runner 复用已存在的设计，不会自动重建其几何。
结果文件按焊盘宽度命名；若要同时保存另一轮研究，请先复制整个项目到另一文件夹再运行。

## 6. 工程和证据范围

仓库保留 AEDT 几何/设置、原始 S21 CSV、线性频率、EPR 摘要、200 μm 场采样及验证记录。
求解器结果目录、运行日志、旧校准工程、带本机路径的 pyEPR 内部容器不打包。
因此仅打开 AEDT 工程不一定有可用的场解；需要重新求解后才能进行新的 EPR 分析。

工程读取和 HFSS 求解已在原始记录环境中验证。本次展示/打包修改只重新执行保存数据分析和
notebook，没有重新跑长时间 HFSS 求解，也没有验证全新系统上的依赖安装。
