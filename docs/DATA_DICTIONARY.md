# 数据字典与符号

沿用学习教材：g、α、E꜀、Eⱼ 为能量；χ、Δ、ω 为角频率。
内部 Python 为方便计算使用频率单位，但对外标签明确写出 h 或 2π。

| `comparison.csv` 字段 | 实际表示 | 单位 |
|---|---|---|
| width_um | 读出耦合焊盘宽度 Wpad | μm |
| fq_GHz | 读出无激发条件下的量子比特跃迁 E₁₀/h | GHz |
| fr_EPR_GHz | 量子比特在基态时，读出模态零到一个激发的跃迁频率 | GHz |
| alpha_MHz | α/h，负值 | MHz |
| state_separation_MHz | ∣2χ∣/(2π)，两个状态的完整读出频率间隔 | MHz |
| g_inferred_MHz | 等效 g/h，由色散模型与 EPR 频移反推 | MHz |
| g_over_abs_detuning | ∣g/(ℏΔ)∣，近似色散筛选指标 | 无量纲 |
| fr_linear_driven_GHz | 50 Ω 端口线性驱动模型的 S21 拟合中心 | GHz |
| kappa_total_MHz | κ/(2π)，加载线宽 Δf | MHz |
| kappa_external_MHz | κext/(2π)，外耦合线宽 | MHz |
| Q_loaded | 拟合中心频率 / 加载线宽，单位一致后计算 | 无量纲 |
| separation_over_linewidth | 完整状态频率间隔 / 加载线宽 | 无量纲 |
| T1_Purcell_estimate_us | 单模色散模型下的 Purcell 寿命估算 | μs |
| eigen_converged / driven_converged | 是否满足对应求解的设置标准 | 布尔值 |
| fit_complex_rms | 复数 S21 拟合残差的 RMS | 无量纲 |
| fit_points_per_linewidth | 一条线宽覆盖的频率采样间隔数 | 无量纲 |
| sampling_linewidth_change_pct | 两种扫频采样的拟合线宽相对差 | % |

## 文件来源

- `s21_W*_fine.csv`：HFSS 窄带复数端口数据，频率 GHz、S21 实部与虚部。
- `s21_W*.csv`：定位扫频的复数数据。
- `eigen_W*.json`：HFSS 线性模态频率与求解设置，频率原值 Hz。
- `epr_W*.json`：pyEPR 摘要。`f_0`、`f_1`、`f_ND` 分别为线性、首阶修正与数值对角化频率，均为 MHz。
- `chi_ND`：本项目保存的正值 Kerr 矩阵；对角为非谐性大小，非对角为完整 cross-Kerr 间隔。
- `Pm_normed`：用于量子化的归一化结电感能量参与率。
- `fit_W*.json`：复数拟合参数与线宽；`source_file` 为相对数据路径。
- `convergence_*.csv`：求解器网格收敛记录。
- `physical_checks_*.json`：互易性与理想无损功率守恒检查。
- `quantum_truncation_W200.json`：基准方案的余弦展开/Fock 基底敏感性比较。

`fr_EPR_GHz` 和 `fr_linear_driven_GHz` 不是同一模型中的两个量子态频率。
不要将它们相减当作 χ；本征模与驱动模型的加载边界也不同。

## 数据与结论的依赖

状态频移 → 色散模型反推等效 g → 结合外耦合线宽估算 Purcell 寿命。
因此寿命不是一份独立耗散实验/仿真证据。取近似色散指标小于0.15仅是本项目筛选规则。
三点曲线用于指导下一轮设计；未验证真实读出噪声、保真度或总 T₁。
