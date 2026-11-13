"""One fixed-frequency transmon, quarter-wave CPW and two-port feedline.

Uses standard Quantum Metal components. Topology follows the official Metal
transmon/resonator and hanger-resonator tutorials (Apache-2.0), with project-
specific placement, dimensions, stack and a single coupling-width parameter.
"""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parent
for directory in ("results", "figures", "models", "logs", "runtime"):
    (ROOT / directory).mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "runtime" / "matplotlib"))
# AEDT installation discovery is delegated to PyAEDT. Configure ANSYSEM_ROOT261
# in your environment if your installation is not registered with AEDT.

DEFAULTS = dict(pad_width_um=200.0, junction_nH=16.0,
                resonator_length_mm=4.0, coupling_length_um=250.0,
                coupling_space_um=5.0, silicon_um=500.0)


def make_cell(pad_width_um=200.0):
    from qiskit_metal import Dict
    from qiskit_metal.designs.design_multiplanar import MultiPlanar
    from qiskit_metal.qlibrary.qubits.transmon_pocket import TransmonPocket
    from qiskit_metal.qlibrary.couplers.coupled_line_tee import CoupledLineTee
    from qiskit_metal.qlibrary.terminations.launchpad_wb_driven import LaunchpadWirebondDriven
    from qiskit_metal.qlibrary.tlines.straight_path import RouteStraight
    from qiskit_metal.qlibrary.tlines.meandered import RouteMeander

    design = MultiPlanar(overwrite_enabled=True)
    design.chips.main.size.update(size_x="5mm", size_y="4mm")
    design.variables.update(cpw_width="10um", cpw_gap="6um")
    # PEC conductors, 200 nm thick; 500 um silicon; no fabricated-loss claims.
    stack = design.ls.ls_df
    stack.loc[stack.layer == 1, "thickness"] = "0.2um"
    stack.loc[stack.layer == 3, "thickness"] = f"-{DEFAULTS['silicon_um']}um"
    q = TransmonPocket(design, "Q1", options=Dict(
        pos_x="-0.8mm", pos_y="-0.8mm", orientation="90",
        pad_width="425um", pad_height="90um", pad_gap="30um",
        pocket_width="650um", pocket_height="650um",
        aedt_hfss_inductance=DEFAULTS["junction_nH"] * 1e-9,
        aedt_hfss_capacitance=0,
        connection_pads=Dict(readout=Dict(
            loc_W=1, loc_H=1, pad_width=f"{pad_width_um}um",
            pad_height="30um", pad_gap="15um"))))
    tee = CoupledLineTee(design, "Tee", options=Dict(
        pos_x="0mm", pos_y="1mm", orientation="0",
        coupling_length=f"{DEFAULTS['coupling_length_um']}um",
        coupling_space=f"{DEFAULTS['coupling_space_um']}um",
        open_termination=False, fillet="25um", down_length="100um"))
    for name, x, angle in (("P1", -2, 0), ("P2", 2, 180)):
        LaunchpadWirebondDriven(design, name, options=Dict(
            pos_x=f"{x}mm", pos_y="1mm", orientation=str(angle)))
    RouteStraight(design, "FeedLeft", options=Dict(pin_inputs=Dict(
        start_pin=Dict(component="P1", pin="tie"),
        end_pin=Dict(component="Tee", pin="prime_start"))))
    RouteStraight(design, "FeedRight", options=Dict(pin_inputs=Dict(
        start_pin=Dict(component="Tee", pin="prime_end"),
        end_pin=Dict(component="P2", pin="tie"))))
    resonator = RouteMeander(design, "Readout", options=Dict(
        total_length=f"{DEFAULTS['resonator_length_mm']}mm", fillet="60um",
        lead=Dict(start_straight="150um", end_straight="150um"),
        meander=Dict(spacing="150um", asymmetry="0um"),
        pin_inputs=Dict(start_pin=Dict(component="Q1", pin="readout"),
                        end_pin=Dict(component="Tee", pin="second_end"))))
    assert design.ls.is_layer_data_unique()
    return design


def export_layout(design, pad_width_um=200.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from qiskit_metal.renderers.renderer_mpl.mpl_renderer import QMplRenderer
    fig, ax = plt.subplots(figsize=(10, 6))
    renderer = QMplRenderer(design)
    renderer.render(ax)
    ax.set_aspect("equal")
    ax.autoscale()
    ax.set_xlabel("x (mm)",fontsize=12); ax.set_ylabel("y (mm)",fontsize=12)
    ax.tick_params(labelsize=11)
    ax.set_title(f"Transmon readout cell | coupling pad {pad_width_um:g} um",fontsize=14)
    for label, xy, text in [
        ("Transmon Q1",(-0.8,-0.8),(-1.9,-1.35)),
        ("Readout resonator",(-0.45,-0.2),(0.65,-0.65)),
        ("Feedline",(0.9,1.0),(0.7,1.5)),
        ("Resonator-feedline coupler",(0.04,0.97),(-1.4,1.65))]:
        ax.annotate(label,xy=xy,xytext=text,fontsize=11,color="#19445D",
            arrowprops=dict(arrowstyle="->",color="#19445D",lw=.8))
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / f"layout_W{pad_width_um:g}.png", dpi=180)
    plt.close(fig)
    manifest = dict(DEFAULTS, pad_width_um=pad_width_um,
                    components=list(design.components),
                    stack=design.ls.ls_df.to_dict(orient="records"),
                    resonator_options=dict(design.components["Readout"].options))
    (ROOT / "results" / f"geometry_W{pad_width_um:g}.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    d = make_cell()
    print(export_layout(d))
