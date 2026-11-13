"""Export actual HFSS eigenmode field samples and plot their spatial patterns."""
import argparse
import numpy as np
import pandas as pd
from run_hfss import ROOT, connect


def export(width=200, port=0, project="readout_cell_v2"):
    h=connect(f"W{width:g}_Eigen",ROOT/"models"/f"{project}.aedt","Eigenmode",port)
    import json
    silicon=h.materials["silicon"]
    (ROOT/"results/materials.json").write_text(json.dumps(dict(
        silicon_relative_permittivity=silicon.permittivity.value,
        silicon_conductivity=silicon.conductivity.value,
        silicon_loss_tangent=silicon.dielectric_loss_tangent.value,
        conductor="PEC",nominal_metal_thickness_um=0.2,
        nominal_substrate_thickness_um=500,
        metal_bbox_mm=h.modeler["pad_top_Q1"].bounding_box),indent=2,default=str))
    for mode in (1,2):
        h.osolution.EditSources([
            ["FieldType:=","EigenPeakElectricField"],
            ["Name:=","Modes","Magnitudes:=",["1" if i==mode else "0" for i in (1,2)],
             "Phases:=",["0","0"]]])
        path=ROOT/"results"/f"field_W{width:g}_mode{mode}.fld"
        result=h.post.export_field_file_on_grid(quantity="Mag_E",
            solution="EigenSetup : LastAdaptive",file_name=str(path),
            grid_start=[-1.8,-1.4,0.001],grid_stop=[0.8,1.2,0.001],
            grid_step=[0.02,0.02,0],intrinsics={"Phase":"0deg"},export_in_si_system=True)
        assert result and path.exists(), f"Field export failed: {mode}"
    plot(width)


def plot(width=200):
    import json
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    frequencies=json.loads((ROOT/"results"/f"eigen_W{width:g}.json").read_text())["frequencies_raw"]
    fig,axes=plt.subplots(1,2,figsize=(9,5),layout="constrained")
    for mode,ax in enumerate(axes,1):
        rows=[]
        for line in (ROOT/"results"/f"field_W{width:g}_mode{mode}.fld").read_text().splitlines():
            try:
                row=[float(s) for s in line.split()]
                if len(row)==4 and np.all(np.isfinite(row)):
                    rows.append(row)
            except ValueError:
                continue
        a=np.asarray(rows)
        assert len(a)>1000
        # export_in_si_system=True means sampled coordinates are in meters.
        frame=pd.DataFrame(dict(x=a[:,0]*1000,y=a[:,1]*1000,E=a[:,3]))
        grid=frame.pivot_table(index="y",columns="x",values="E")
        normalized=grid.to_numpy()/np.nanmax(grid.to_numpy())
        im=ax.pcolormesh(grid.columns,grid.index,np.maximum(normalized,1e-5),
            cmap="magma",norm=LogNorm(vmin=1e-4,vmax=1),shading="auto")
        ax.set(aspect="equal",xlabel="x (mm)",ylabel="y (mm)",
            title=f"Mode {mode}: linear f = {frequencies[mode-1]/1e9:.3f} GHz")
        fig.colorbar(im,ax=ax,label="|E| / plane maximum")
    fig.suptitle(f"HFSS linear eigenmode fields | plane z = 1 um | W = {width:g} um")
    fig.savefig(ROOT/"figures"/f"eigenmode_fields_W{width:g}.png",dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--width",type=float,default=200)
    p.add_argument("--port",type=int,default=0)
    p.add_argument("--project",default="readout_cell_v2")
    args=p.parse_args()
    export(args.width,args.port,args.project)
