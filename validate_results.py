"""Check the actual study artifacts and physical/numerical consistency."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent


def validate():
    table=pd.read_csv(ROOT/"results/comparison.csv")
    assert sorted(table.width_um.tolist())==[160,200,240], "Need all three widths"
    checks=[]
    geometry=[]
    for _,row in table.iterrows():
        tag=f"W{row.width_um:g}"
        g=json.loads((ROOT/"results"/f"geometry_{tag}.json").read_text())
        g.pop("pad_width_um")
        # Numerically equivalent unit strings (e.g. -500um / -500.0um)
        # should not be interpreted as a geometry change.
        for layer in g["stack"]:
            layer["thickness"]=float(layer["thickness"].removesuffix("um"))
        geometry.append(g)
        eigen=json.loads((ROOT/"results"/f"eigen_{tag}.json").read_text())
        epr=json.loads((ROOT/"results"/f"epr_{tag}.json").read_text())
        r=epr["variations"]["0"]
        assert np.allclose(np.array(r["f_0"])*1e6,eigen["frequencies_raw"],rtol=1e-10,atol=0.1)
        assert epr["cos_trunc"]==10 and epr["fock_trunc"]==14
        assert np.all((np.array(r["Pm_normed"])>=0)&(np.array(r["Pm_normed"])<=1.01))
        assert row.eigen_converged and row.driven_converged
        assert row.fit_points_per_linewidth>=5
        assert row.sampling_linewidth_change_pct<5
        assert row.fit_complex_rms<0.01
        assert row.kappa_external_MHz>0 and row.kappa_total_MHz>0
        assert row.kappa_external_MHz<=1.02*row.kappa_total_MHz
        assert row.g_over_abs_detuning<0.15
        data=np.loadtxt(ROOT/"results"/f"s21_{tag}_fine.csv",delimiter=",",skiprows=1)
        assert np.isfinite(data).all() and np.all(np.diff(data[:,0])>0)
        assert np.max(abs(data[:,1]+1j*data[:,2]))<=1.02
        model=json.loads((ROOT/"results"/f"model_{tag}_Driven.json").read_text())
        assert len(model["excitations"])==2
        physical=json.loads((ROOT/"results"/f"physical_checks_{tag}.json").read_text())
        assert physical["max_reciprocity_error"]<0.01
        assert physical["max_lossless_power_balance_error"]<0.02
        checks.append(dict(width_um=row.width_um,
            eigen_and_driven_converged=True, units_cross_checked=True,
            complex_fit_rms=float(row.fit_complex_rms),
            points_per_linewidth=float(row.fit_points_per_linewidth),
            broad_vs_fine_linewidth_change_pct=float(row.sampling_linewidth_change_pct),
            max_reciprocity_error=physical["max_reciprocity_error"],
            max_lossless_power_balance_error=physical["max_lossless_power_balance_error"]))
    assert geometry[0]==geometry[1]==geometry[2], "More than the coupling width changed"
    payload=dict(passed=True,geometry_invariance_passed=True,checks=checks,
        limitations=["Purcell estimate uses a single-mode dispersive model",
                     "g is inferred from EPR cross-Kerr, not independently extracted",
                     "Ideal PEC / lossless substrate; no measured device T1 or fidelity"])
    (ROOT/"results/validation.json").write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))


if __name__=="__main__":
    validate()
