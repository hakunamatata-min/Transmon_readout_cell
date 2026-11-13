"""Illustrate the saved HFSS S21 fit; does not launch or rerun any solver."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "runtime" / "matplotlib"))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    fit = json.loads((ROOT / "results/fit_W200.json").read_text())
    raw = np.loadtxt(ROOT / "results/s21_W200_fine.csv", delimiter=",", skiprows=1)
    fr, width = fit["fr_GHz"], fit["linewidth_MHz"]
    p = fit["fitted_parameters"]
    depth = complex(p[4], p[5])
    reference = fr - p[0] / 1000

    def baseline(f):
        x = (np.asarray(f) - reference) * 1000
        return complex(p[2], p[3]) * np.exp(-2j * np.pi * x * p[6] * 0.001)

    def response(f):
        offset = (np.asarray(f) - fr) * 1000
        return 1 / (1 + fit["sign"] * 2j * offset / width)

    f = raw[:, 0]
    z = raw[:, 1] + 1j * raw[:, 2]
    dense = fr + np.linspace(-0.8, 0.8, 2001) / 1000
    fitted = baseline(dense) * (1 - depth * response(dense))
    extracted = (1 - z / baseline(f)) / depth
    plt.rcParams.update({"font.family": "Microsoft YaHei", "font.size": 11,
                         "axes.unicode_minus": False, "mathtext.fontset": "dejavusans"})
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.8, 4.5), layout="constrained")
    offset = (f - fr) * 1000
    dense_offset = (dense - fr) * 1000
    left.plot(dense_offset, np.abs(fitted) ** 2, color="#156579", lw=2,
              label="复数 S21 拟合")
    left.plot(offset, np.abs(z) ** 2, ".", color="#b35b35", ms=6,
              label="HFSS 采样点")
    left.axvline(0, color="#606b75", ls=":", lw=1)
    left.set(title="端口传输：共振附近出现凹口", ylabel=r"传输功率比 $|S_{21}|^2$")
    left.legend(loc="lower right", fontsize=10)

    right.plot(dense_offset, np.abs(response(dense)) ** 2,
               color="#156579", lw=2, label="单极点拟合的共振分量")
    right.plot(offset, np.abs(extracted) ** 2, ".", color="#b35b35", ms=6,
               label="采样数据去除拟合背景后")
    right.axhline(0.5, color="#8b9299", ls="--", lw=1)
    for x in (-width / 2, width / 2):
        right.vlines(x, 0, 0.5, color="#8b9299", ls=":", lw=1)
    right.annotate("", xy=(-width / 2, 0.5), xytext=(width / 2, 0.5),
                   arrowprops=dict(arrowstyle="<->", lw=1.8, color="#b35b35"))
    right.text(0, 0.59, f"半高全宽 Δf = {width:.6f} MHz",
               ha="center", color="#963e21", fontsize=11)
    right.text(0.76, 0.52, "半高", ha="right", fontsize=10, color="#606b75")
    right.set(title="去除直通背景后的共振响应", ylabel="归一化共振分量（功率形式）")
    right.legend(loc="upper right", fontsize=9)
    for ax in (left, right):
        ax.set(xlim=(-0.8, 0.8), ylim=(-0.03, 1.07),
               xlabel=f"相对 {fr:.6f} GHz 的频率偏移（MHz）")
        ax.grid(alpha=0.17)
    fig.suptitle(f"200 μm 方案：真实 HFSS 数据与拟合  |  加载 Q = {fit['Q_loaded']:.0f}",
                 fontsize=13)
    output = ROOT / "figures/explain_s21_linewidth_W200.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    print(output)
    print(f"Energy lifetime: {1 / (2 * np.pi * width):.6f} us")
    print(f"State separation / linewidth: {5.05445523443985 / width:.6f}")


if __name__ == "__main__":
    main()
