"""Fit measured HFSS complex S21 and compare actual EPR results.

Textbook convention: alpha and g are energies; chi and Delta are angular
frequencies. Internal alpha_MHz and g_inferred_MHz store alpha/h and g/h.
state_separation_MHz stores |2chi|/(2pi); kappa_*_MHz stores kappa/(2pi).
The frequency-valued internal variables below include the required 2pi when
converting a fitted linewidth to a lifetime.
"""
from pathlib import Path
import json
import os
import numpy as np
from scipy.optimize import least_squares
import pandas as pd

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "runtime" / "matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size":12,"axes.labelsize":12,"axes.titlesize":12,
                     "xtick.labelsize":11,"ytick.labelsize":11,"legend.fontsize":10})


def plot_convergence(width=200):
    import re
    fig,axes=plt.subplots(1,2,figsize=(10,3.2))
    paths=[ROOT/"results"/f"convergence_W{width:g}.csv",
           ROOT/"results"/f"driven_convergence_W{width:g}.csv"]
    labels=["Max eigenfrequency change (%)","Max change of S (absolute)"]
    for ax,path,label in zip(axes,paths,labels):
        text=path.read_text()
        values=[]
        for line in text.splitlines():
            if "|" not in line:
                continue
            parts=[s.strip() for s in line.split("|") if s.strip()]
            try:
                values.append([int(parts[0]),float(parts[2])])
            except (ValueError,IndexError):
                continue
        a=np.asarray(values)
        target=float(re.search(r"Target\s*:\s*([\d.]+)",text).group(1))
        ax.semilogy(a[:,0],a[:,1],"o-",color="#176B87")
        ax.axhline(target,ls="--",color="#A45D35",label=f"Target: {target:g}")
        ax.set(xlabel="Adaptive pass",ylabel=label)
        ax.grid(alpha=.2);ax.legend()
    fig.suptitle(f"HFSS convergence | coupling pad {width:g} um",fontsize=13)
    fig.tight_layout();fig.savefig(ROOT/"figures/convergence_summary.png",dpi=200);plt.close(fig)


def fit_s21(path):
    values = np.loadtxt(path, delimiter=",", skiprows=1)
    frequency_ghz, z = values[:,0], values[:,1] + 1j*values[:,2]
    index = int(np.argmin(abs(z)))
    if index < 3 or index > len(z)-4:
        raise ValueError(f"No resolved interior resonance: {path}")
    reference = frequency_ghz[index]
    mask = abs(frequency_ghz-reference) < 0.025
    f, z = frequency_ghz[mask], z[mask]
    x = (f-reference)*1000  # MHz
    if len(x) < 15:
        raise ValueError("Not enough points near resonance")
    edge = np.r_[0: max(3,len(z)//10), len(z)-max(3,len(z)//10):len(z)]
    baseline = np.mean(z[edge])
    width0 = max(np.median(np.diff(x))*3, 0.1)
    best = None
    for sign in (1,-1):
        def model(p):
            fr, logwidth, ar, ai, dr, di, delay = p
            return (ar+1j*ai)*np.exp(-2j*np.pi*x*delay*0.001)*(1-(dr+1j*di)/(
                1+sign*2j*(x-fr)/np.exp(logwidth)))
        def residual(p):
            error = model(p)-z
            return np.r_[error.real,error.imag]
        p0=[0,np.log(width0),baseline.real,baseline.imag,0.8,0,0]
        fit = least_squares(residual, p0,
            bounds=([x.min(),np.log(1e-5),-2,-2,0,-1.5,-100],
                    [x.max(),np.log(100),2,2,1.8,1.5,100]),
            max_nfev=4000, ftol=1e-12, xtol=1e-12, gtol=1e-12)
        if best is None or fit.cost < best[0].cost:
            best=(fit, model(fit.x), sign)
    fit, predicted, sign = best
    p=fit.x
    linewidth=float(np.exp(p[1]))
    fr=float(reference+p[0]/1000)
    result=dict(fr_GHz=fr, linewidth_MHz=linewidth, Q_loaded=fr*1000/linewidth,
        complex_depth=[float(p[4]),float(p[5])],
        external_linewidth_MHz=linewidth*float(p[4]),
        complex_rms=float(np.sqrt(np.mean(abs(predicted-z)**2))),
        points_per_linewidth=linewidth/float(np.median(np.diff(x))),
        window_linewidths=float(np.ptp(x)/linewidth),
        fitted_parameters=p.tolist(), sign=sign,
        source_file=str(Path(path).resolve()))
    return result, f, z, predicted


def evaluate_fit(frequency_ghz, fit):
    p=fit["fitted_parameters"]
    reference=fit["fr_GHz"]-p[0]/1000
    x=(np.asarray(frequency_ghz)-reference)*1000
    return (p[2]+1j*p[3])*np.exp(-2j*np.pi*x*p[6]*0.001)*(1-(p[4]+1j*p[5])/(
        1+fit["sign"]*2j*(x-p[0])/np.exp(p[1])))


def compare(widths=(160,200,240), suffix="fine"):
    rows=[]
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for width in widths:
        tag=f"W{width:g}"
        epr_path=ROOT/"results"/f"epr_{tag}.json"
        s_path=ROOT/"results"/f"s21_{tag}_{suffix}.csv"
        if not epr_path.exists() or not s_path.exists():
            continue
        data=json.loads(epr_path.read_text())
        result=data["variations"]["0"]
        freq=np.asarray(result["f_ND"],dtype=float)
        chi=np.asarray(result["chi_ND"],dtype=float)
        q_index=int(np.argmax(np.asarray(result["Pm_normed"]).ravel()))
        r_index=1-q_index
        fq,fr=freq[q_index],freq[r_index]  # MHz
        alpha=-float(abs(chi[q_index,q_index]))
        split=float(abs(chi[q_index,r_index]))
        signed_chi=-split/2  # Valid here for fq < fr and alpha < 0.
        detuning=fq-fr
        assert detuning < 0 and alpha < 0
        g_eff=np.sqrt(signed_chi*detuning*(detuning+alpha)/alpha)
        fit,f,z,pred=fit_s21(s_path)
        kappa=fit["external_linewidth_MHz"]
        if kappa<=0:
            raise ValueError("Fit produced nonpositive external coupling")
        purcell_us=(detuning/g_eff)**2/(2*np.pi*kappa)
        convergence=(ROOT/"results"/f"convergence_{tag}.csv").read_text()
        row=dict(width_um=width, fq_GHz=fq/1000, fr_EPR_GHz=fr/1000,
            alpha_MHz=alpha, state_separation_MHz=split,
            g_inferred_MHz=float(g_eff), g_over_abs_detuning=float(g_eff/abs(detuning)),
            fr_linear_driven_GHz=fit["fr_GHz"], kappa_total_MHz=fit["linewidth_MHz"],
            kappa_external_MHz=kappa, Q_loaded=fit["Q_loaded"],
            separation_over_linewidth=split/fit["linewidth_MHz"],
            T1_Purcell_estimate_us=float(purcell_us),
            eigen_converged="Converged : Yes" in convergence,
            fit_points_per_linewidth=fit["points_per_linewidth"],
            fit_complex_rms=fit["complex_rms"])
        driven_convergence=ROOT/"results"/f"driven_convergence_{tag}.csv"
        row["driven_converged"]=("Converged : Yes" in driven_convergence.read_text()) if driven_convergence.exists() else False
        coarse,*_=fit_s21(ROOT/"results"/f"s21_{tag}.csv")
        row["sampling_linewidth_change_pct"]=100*abs(coarse["linewidth_MHz"]-fit["linewidth_MHz"])/fit["linewidth_MHz"]
        rows.append(row)
        (ROOT/"results"/f"fit_{tag}.json").write_text(json.dumps(fit,indent=2))
        x=(f-fit["fr_GHz"])*1000
        dense_f=np.linspace(f.min(),f.max(),5001)
        dense=evaluate_fit(dense_f,fit)
        dense_x=(dense_f-fit["fr_GHz"])*1000
        line=axes[0].plot(dense_x,20*np.log10(abs(dense)),label=f"{width:g} um",lw=1.4)[0]
        axes[0].plot(x,20*np.log10(abs(z)),".",ms=3,color=line.get_color(),alpha=.6)
        axes[1].plot(dense.real,dense.imag,label=f"{width:g} um",color=line.get_color(),lw=1.4)
        axes[1].plot(z.real,z.imag,".",ms=3,color=line.get_color(),alpha=.6)
    if not rows:
        raise FileNotFoundError("No complete EPR + fine S21 data; run HFSS first")
    table=pd.DataFrame(rows)
    table.to_csv(ROOT/"results"/"comparison.csv",index=False)
    table.to_json(ROOT/"results"/"comparison.json",orient="records",indent=2)
    axes[0].set(xlabel="Frequency offset from each resonance (MHz)",ylabel="S21 magnitude (dB)",
                title="HFSS samples: dots / fit: lines",xlim=(-2,2),ylim=(-45,1))
    axes[1].set(xlabel="Re(S21)",ylabel="Im(S21)",title="Complex S21")
    for ax in axes:
        ax.grid(alpha=.2); ax.legend()
    fig.tight_layout(); fig.savefig(ROOT/"figures"/"s21_comparison.png",dpi=200);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.2))
    for ax,col,label in zip(axes,
        ["state_separation_MHz","T1_Purcell_estimate_us"],
        ["|2chi| / 2pi (MHz)","Purcell T1 estimate (us)"]):
        ax.plot(table.width_um,table[col],"o-",color="#176B87")
        ax.set(xlabel="Coupling pad width (um)",ylabel=label)
        ax.set_xticks(table.width_um)
        ax.grid(alpha=.2)
    fig.suptitle("Coupling geometry: readout separation and Purcell lifetime",fontsize=13)
    fig.tight_layout();fig.savefig(ROOT/"figures"/"design_tradeoff.png",dpi=200);plt.close(fig)
    print(table.to_string(index=False))
    plot_convergence()
    return table


if __name__ == "__main__":
    compare()
