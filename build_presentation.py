"""Build a result-first presentation notebook. Never invokes HFSS."""
from pathlib import Path
import argparse
import json
import shutil
import os
import re

ROOT = Path(__file__).resolve().parent


def build():
    import nbformat as nbf
    cells = []

    def md(text):
        cells.append(nbf.v4.new_markdown_cell(text.strip()))

    def code(text):
        cell = nbf.v4.new_code_cell(text.strip())
        cell.metadata.update(jupyter={"source_hidden": True})
        cells.append(cell)

    md("""
# Transmon Readout Cell
### 基于 Qiskit Metal 与 HFSS 的读出单元设计及耦合权衡

**一个 transmon · 一个 λ/4 CPW 谐振器 · 一条两端口馈线**

**设计问题：**增大读出耦合焊盘，能增加多少状态频率间隔？需要付出多少 Purcell 衰减代价？

本项目完成 160 / 200 / 240 μm 三组几何比较。所有图表来自保存的 HFSS / EPR 结果。
当前 notebook 只读取数据和展示结果，运行全部单元不会启动 HFSS。

**主要发现：**160 → 240 μm，状态频率间隔增加约 78%，单模 Purcell 寿命估算缩短约 44%；
加载线宽始终约 0.36 MHz。按本次筛选准则，160 μm 是下一步验证候选。

**阅读路线：**设计与方法 → 电磁/量子证据 → 三组比较 → 设计选择 → 验证与边界。
""")
    code("""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from IPython.display import display, Image

ROOT = Path.cwd()
if not (ROOT / 'results/comparison.csv').is_file():
    ROOT = ROOT / 'transmon_readout'
assert (ROOT / 'results/comparison.csv').is_file(), '请在项目根目录打开 notebook'
results = pd.read_csv(ROOT / 'results/comparison.csv').sort_values('width_um')

def read_json(name):
    return json.loads((ROOT / 'results' / name).read_text(encoding='utf-8'))

def show_image(name, width=1050):
    display(Image(filename=str(ROOT / 'figures' / name), width=width))

def show_table(frame, formats=None):
    view = frame.style.hide(axis='index')
    if formats:
        view = view.format(formats)
    display(view.set_table_styles([
        {'selector':'th', 'props':[('background-color','#14364c'),('color','white'),('padding','10px'),('text-align','left')]},
        {'selector':'td', 'props':[('padding','9px 10px'),('border-bottom','1px solid #dce5ec')]},
        {'selector':'table', 'props':[('font-size','14px'),('border-collapse','collapse')]}
    ]))
""")
    md("""
## 01 / 设计对象与控制变量

只改变 **量子比特—谐振器读出耦合焊盘宽度**，其余几何与结电感保持相同。
它不是 CPW 中心导体宽度，也不是 transmon 主电容板宽度。

| 结构 | 参数与作用 |
|---|---|
| Transmon | 单 Josephson 结；Lⱼ = 16 nH，结电容在本模型中取 0 |
| CPW | 中心宽度 w = 10 μm，缝隙 s = 6 μm；折叠布线长 4.0 mm |
| 读出耦合焊盘 | Wpad = 160 / 200 / 240 μm；影响量子比特—谐振器耦合 |
| 馈线耦合结构 | 耦合段 250 μm、参数 coupling_space = 5 μm，三组保持相同 |
| 材料与端口 | PEC 金属、500 μm 无损硅，两个 50 Ω 端口 |

Qiskit Metal 使用 TransmonPocket、CoupledLineTee、RouteMeander 等参数化组件创建几何。
完整定义见 `cell.py`。固定频率指工作时不通过 SQUID 磁通调谐；改变版图仍会改变频率。
""")
    code("show_image('layout_W200.png', 950)")
    md("""
## 02 / 从几何到读出指标

两条互补路线：**本征模 + EPR**提供跃迁频率、非谐性和状态频移；
**端口驱动 + 复数 S₂₁ 拟合**提供读出线宽和加载 Q。

两处耦合分别影响不同指标：焊盘主要影响量子比特—谐振器耦合；
谐振器—馈线耦合决定外部能量泄漏。Purcell 寿命由量子参数和外耦合线宽共同估算。
""")
    code("show_image('project_workflow.png')")
    md("""
## 03 / 证据一：找到正确的线性电磁模态

HFSS 用集总电感线性化 Josephson 结，求出自然振荡频率与场分布。
Mode 1 / Mode 2 是两种振荡方式，不是量子比特的基态和激发态。

200 μm 方案中，第一个模态在 transmon 附近有较强电场；第二个模态在折叠 CPW 附近较强。
两图分别归一化，只用于比较各自场的空间形状，不能比较两个模态的总能量。
""")
    code("""
eigen = read_json('eigen_W200.json')
show_table(pd.DataFrame({
    '模态':['量子比特型','读出谐振器型'],
    '线性频率 (GHz)':np.array(eigen['frequencies_raw']) / 1e9
}), {'线性频率 (GHz)':'{:.6f}'})
show_image('eigenmode_fields_W200.png', 950)
""")
    md("""
## 04 / 证据二：加入 Josephson 非线性

EPR 从线性电磁场中提取结参与率，构造量子哈密顿量，再用有限 Fock 基底做数值对角化。
本项目采用每个模态 14 个基态。线性频率因此不能直接当作最终量子比特跃迁频率。

**教材符号：**g、α 是能量；χ、Δ 是角频率。表中非谐性写为 α/h，
完整状态频率间隔写为 ∣2χ∣/(2π)。pyEPR 的对角与非对角 Kerr 元素需要按此换算。
""")
    code("""
epr = read_json('epr_W200.json')['variations']['0']
q = int(np.argmax(np.array(epr['Pm_normed']).ravel()))
r = 1-q
show_table(pd.DataFrame({
    '指标':['量子比特跃迁频率 E₁₀/h','基态读出频率','非谐性 α/h','两状态频率间隔 ∣2χ∣/(2π)'],
    '数值':[epr['f_ND'][q]/1000,epr['f_ND'][r]/1000,-abs(epr['chi_ND'][q][q]),abs(epr['chi_ND'][q][r])],
    '单位':['GHz','GHz','MHz','MHz']
}), {'数值':'{:.6f}'})
""")
    md("""
## 05 / 证据三：用端口频响提取线宽

从端口1输入微波、在端口2观察输出。先宽带定位，再窄带采样，拟合复数 S₂₁。
左图显示实际端口传输凹口；右图去除直通背景，以功率形式显示共振分量及其半高全宽。

这里仍是线性化模型的响应，尚未分别模拟量子比特两个状态的读出曲线。
S₂₁ 中心与 EPR 频率属于不同计算，端口加载条件也不同，不能将两者之差当作状态频移。
""")
    code("""
fit = read_json('fit_W200.json')
show_table(pd.DataFrame({
    '指标':['S₂₁ 拟合中心','读出线宽 Δf','加载品质因数 Qᵣ'],
    '数值':[fit['fr_GHz'],fit['linewidth_MHz'],fit['Q_loaded']],
    '单位':['GHz','MHz','无量纲']
}), {'数值':'{:.6f}'})
show_image('explain_s21_linewidth_W200.png')
""")
    md("""
## 06 / 三组几何比较

表中所有频率均使用普通频率单位。基态读出频率来自 EPR；线宽来自端口驱动拟合；
Purcell 寿命是单模色散模型估算，并非实测 T₁。
""")
    code("""
columns = {
    'width_um':'Wpad (μm)', 'fq_GHz':'E₁₀/h (GHz)',
    'fr_EPR_GHz':'基态读出 (GHz)', 'state_separation_MHz':'状态间隔 (MHz)',
    'kappa_total_MHz':'Δf (MHz)', 'T1_Purcell_estimate_us':'寿命估算 (μs)'
}
summary = results[list(columns)].rename(columns=columns)
formats = {name:'{:.3f}' for name in summary.columns if name != 'Wpad (μm)'}
formats['Wpad (μm)'] = '{:.0f}'
show_table(summary, formats)
show_image('design_tradeoff.png')
""")
    md("""
**如何解释：**焊盘加宽，电容负载与相互作用共同改变，所以两个模态频率也会变化。
状态频率间隔增大约 78%，而线宽变化约 2%以内，说明两处耦合的作用不同。
更强的量子比特—谐振器混合也会增强通过读出线路的能量泄漏，Purcell 寿命估算缩短约 44%。

**注意依赖关系：**g 是由 EPR 频移和色散模型反推的等效估计。
寿命图不是独立的耗散仿真验证；它量化的是该模型下的设计权衡。
""")
    md("""
## 07 / 设计选择：160 μm，作为下一步验证候选

本次筛选准则：状态频率间隔至少达到一条加载线宽；满足近似色散筛选条件后，
优先降低读出线路的衰减。本项目采用的归一化耦合筛选阈值 0.15 是工程筛选规则，
不是普适的色散近似误差保证。

160 μm 的状态间隔已达约 9.9 条线宽，Purcell 寿命估算约 70.4 μs，为三组中最长。
200 μm 是中间候选；240 μm 提供最大频率间隔，但寿命估算降至约 39.3 μs。

这是一组三点比较，不代表全局最优。频率分离很大也不能直接换算为测量保真度。
""")
    code("""
selection = results[['width_um','separation_over_linewidth','g_over_abs_detuning','T1_Purcell_estimate_us']].copy()
selection.columns = ['Wpad (μm)','状态间隔 / 线宽','归一化等效耦合','寿命估算 (μs)']
show_table(selection, {'Wpad (μm)':'{:.0f}','状态间隔 / 线宽':'{:.2f}',
                       '归一化等效耦合':'{:.3f}','寿命估算 (μs)':'{:.1f}'})
show_image('design_selection.png', 850)
""")
    md("""
## 08 / 验证证据与精度边界

- 三组本征模：连续两次自适应迭代的频率变化低于 0.3%。这不是绝对误差保证。
- 三组驱动模型：最大 S 参数变化低于 0.01。
- 复数拟合使用实部与虚部，窄带约 7 个采样间隔覆盖一条线宽。
- 两种采样密度得到的线宽相近；互易性与理想无损功率守恒检查通过。
- 200 μm 增大 Fock 基底后，f01 变化约 4.35 kHz、状态间隔变化约 0.03%。

基底检查不能代替电磁网格检查。χ 与参与率的网格敏感性仍需进一步加密验证。
""")
    code("""
validation = read_json('validation.json')
checks = pd.DataFrame(validation['checks'])
checks = checks[['width_um','eigen_and_driven_converged','complex_fit_rms',
                 'points_per_linewidth','broad_vs_fine_linewidth_change_pct']]
checks.columns = ['Wpad (μm)','两类求解均收敛','复数拟合 RMS','每线宽采样间隔','采样改变后线宽变化 (%)']
show_table(checks, {'Wpad (μm)':'{:.0f}','复数拟合 RMS':'{:.2e}',
                    '每线宽采样间隔':'{:.2f}','采样改变后线宽变化 (%)':'{:.6f}'})
show_image('convergence_summary.png')
""")
    md("""
## 09 / 已验证的边界与下一步

| 当前模型边界 | 下一步验证 |
|---|---|
| PEC、无损硅；结电容取0、封装简化 | 纳入工艺提供的结电容和真实材料/界面/封装参数 |
| g 从 EPR 频移反推 | 扫描结电感或失谐，独立拟合避免交叉 |
| 单模 Purcell 模型 | 考察高阶模态及环境在量子比特频率处的响应 |
| 本征模与驱动端口加载不同 | 统一加载条件，交叉检查中心频率与参与率 |
| 只有线性 S₂₁ | 计算状态相关读出响应、脉冲、噪声与保真度 |
| 仅三点几何比较 | 在明确读出时间和寿命目标后细化扫描 |

**项目结论：**完成三组几何的电磁与量子分析，量化状态频率间隔与读出线路衰减的权衡；
160 μm 为下一步验证候选。尚未证明全局最优、完整器件 T₁ 或测量保真度。
""")
    md("""
## 附录 A / 看懂复数 S₂₁ 对比

左图分别减去了各自的拟合中心，三条凹口重合不代表实际频率相同。
右图是在复平面上随输入频率扫描的轨迹，颜色代表三种几何；不是两个量子态的 IQ 噪声云团。
图上的点来自 HFSS，线来自拟合。轨迹形状相近，与三组线宽接近一致。
""")
    code("show_image('s21_comparison.png')")
    md("""
## 附录 B / 核心公式与教材对应

| 概念 | 教材位置（印刷页码） |
|---|---|
| 线性振子与 Josephson 非线性修正 | §19.4.2，式(19.6)、(19.18)、(19.19)，第266–268页 |
| 色散频移、两状态频率间隔 | §22.4.1，式(22.18)、(22.22)，第318–319页 |
| S₂₁、复平面与 IQ 噪声云团 | §22.5，式(22.23)、Fig. 22.5，第321–322页 |
| 两处耦合与电磁模态 | Fig. 24.2–24.4，第345–348页 |
| 读出线宽与 Q | §24.3.4，式(24.13)中的 Δf = fᵣ/Qᵣ，第351页 |
| EPR 方法入口 | §24.3.4，第352页 |
| 激发态布居与 T₁ | §25.3.1，式(25.4)，第359页 |

Purcell 公式是补充模型。按教材能量型 g 书写，寿命使用 ℏΔ/g。
数据字段 `alpha_MHz`、`g_inferred_MHz` 分别表示 α/h、g/h；
`kappa_total_MHz` 表示 κ/(2π)，即加载线宽 Δf。
""")
    code("show_image('core_formulas.png')")
    md("""
## 附录 C / 复现入口

**只浏览：**当前 notebook 已包含表格与图片；也可直接打开 `Transmon_Readout_Presentation.html`。

**只重算分析，不启动 HFSS：**

```console
python analyze.py
python validate_results.py
```

**从头运行 HFSS：**需要已安装且有授权的 AEDT、完整量子工具环境。
具体步骤见 `docs/REPRODUCING.md`。修改几何后使用新的工程名，避免复用旧设计。

```console
python run_study.py --project my_readout_cell
python analyze.py
python validate_results.py
```

### 参考

- Minev et al., *Energy-participation quantization of Josephson circuits*, npj Quantum Information 7, 131 (2021). https://arxiv.org/abs/2010.00620
- Blais et al., *Circuit Quantum Electrodynamics*, Rev. Mod. Phys. 93, 025005 (2021). https://arxiv.org/abs/2005.12667
- Qiskit Metal transmon/resonator tutorial: https://qiskit-community.github.io/qiskit-metal/tut/4-Analysis/4.13-Analyze-transmon-and-resonator.html
- S₂₁ tutorial: https://qiskit-community.github.io/qiskit-metal/tut/4-Analysis/4.17-Fit-S21-of-Hanger-Resonator-Geometry.html

教材章节用于学习定位；仓库不分发教材 PDF。
""")
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata.update(kernelspec={"display_name":"Quantum Metal 2026","language":"python","name":"qmetal2026"},
                       language_info={"name":"python","version":"3.14.10"})
    for i, cell in enumerate(nb.cells):
        cell.id = f"presentation-{i:03d}"
    nbf.validate(nb)
    return nb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Execute only saved-data presentation cells')
    parser.add_argument('--html', action='store_true', help='Export an HTML presentation with code hidden')
    parser.add_argument('--execution-mode', choices=['inprocess','kernel'], default='inprocess')
    args = parser.parse_args()
    import nbformat
    notebook_path = ROOT / 'Transmon_Readout_Project.ipynb'
    if notebook_path.exists():
        backup = ROOT / 'tmp' / 'Transmon_Readout_Project.before_presentation.ipynb'
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(notebook_path, backup)
    nb = build()
    if args.execute:
        if args.execution_mode == 'kernel':
            from nbclient import NotebookClient
            NotebookClient(nb, timeout=120, startup_timeout=60, kernel_name='qmetal2026',
                           resources={'metadata':{'path':str(ROOT)}}).execute()
        else:
            # Saved-data cells use ordinary IPython display APIs, so they can be
            # executed and captured without launching a second kernel process.
            from IPython.core.interactiveshell import InteractiveShell
            from IPython.utils.capture import capture_output
            shell = InteractiveShell.instance()
            previous = Path.cwd()
            os.chdir(ROOT)
            try:
                count = 0
                for index, cell in enumerate(nb.cells):
                    if cell.cell_type != 'code':
                        continue
                    count += 1
                    with capture_output() as captured:
                        result = shell.run_cell(cell.source, store_history=False)
                    if result.error_before_exec or result.error_in_exec:
                        raise RuntimeError(f'Presentation cell {index+1} failed') from (result.error_before_exec or result.error_in_exec)
                    outputs = []
                    if captured.stdout:
                        outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
                    if captured.stderr:
                        outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
                    for item in captured.outputs:
                        outputs.append(nbformat.v4.new_output('display_data',data=item.data,metadata=item.metadata))
                    cell.execution_count = count
                    cell.outputs = outputs
                    print(f'Executed presentation cell {index+1}', flush=True)
            finally:
                os.chdir(previous)
    nbformat.write(nb, notebook_path)
    print(notebook_path)
    if args.html:
        from nbconvert import HTMLExporter
        exporter = HTMLExporter(template_name='lab', exclude_input=True, exclude_input_prompt=True,
                                exclude_output_prompt=True)
        body, _ = exporter.from_notebook_node(nb)
        # All equations are embedded figures and all outputs are static tables or
        # images. Remove optional CDN scripts so viewing needs no network access.
        body = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', body, flags=re.I)
        style = '<style>body{background:#eef3f7!important}.jp-Notebook{max-width:1180px;margin:32px auto;padding:36px;background:white;border-radius:14px}h1,h2,h3{color:#14364c!important}.jp-RenderedImage img{max-width:100%;height:auto}table{font-size:14px!important}p,li{line-height:1.8}a{color:#156579}</style>'
        body = body.replace('</head>', style+'</head>')
        output = ROOT / 'Transmon_Readout_Presentation.html'
        output.write_text(body, encoding='utf-8')
        print(output)


if __name__ == '__main__':
    main()
