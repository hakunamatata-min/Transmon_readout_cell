"""Reproducible HFSS runner. Every stage saves its actual results separately.

Run with the qmetal2026 environment; --phase eigen/epr/driven/all.
No device performance is generated from placeholder/synthetic data.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from cell import ROOT, DEFAULTS, make_cell, export_layout
from compat import enable_compat

os.environ["TEMP"] = str(ROOT / "runtime")
os.environ["TMP"] = str(ROOT / "runtime")
os.environ["PYTHONIOENCODING"] = "utf-8"


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def expression_data(solution, expression, formula="real"):
    if hasattr(solution, "get_expression_data"):
        return solution.get_expression_data(expression=expression, formula=formula)
    values = solution.data_real(expression) if formula == "real" else solution.data_imag(expression)
    return solution.primary_sweep_values, values


def transmission_expression(hfss):
    # AEDT's excitation list order is not a physical port numbering convention.
    # Define S21 explicitly: excite P1, observe P2.
    input_port=next(p for p in hfss.excitation_names if p.split(":")[0]=="Port_P1_in")
    output_port=next(p for p in hfss.excitation_names if p.split(":")[0]=="Port_P2_in")
    return f"S({output_port},{input_port})"


def connect(design_name, project_file, solution_type, port=0):
    from ansys.aedt.core import Hfss, settings
    settings.enable_file_logs = False
    return Hfss(project=str(project_file), design=design_name,
                solution_type=solution_type, version=os.getenv("AEDT_VERSION", "2026.1"),
                new_desktop=False, non_graphical=True, close_on_exit=False,
                port=port)


def build(design, width, kind, project_file, port):
    from qiskit_metal.renderers.renderer_ansys_pyaedt.hfss_renderer_eigenmode_aedt import QHFSSEigenmodePyaedt
    from qiskit_metal.renderers.renderer_ansys_pyaedt.hfss_renderer_drivenmodal_aedt import QHFSSDrivenmodalPyaedt
    name = f"W{width:g}_{kind}"
    hfss = connect(name, project_file, "Eigenmode" if kind == "Eigen" else "Modal", port)
    cls = QHFSSEigenmodePyaedt if kind == "Eigen" else QHFSSDrivenmodalPyaedt
    renderer = cls(design, project_name=hfss.project_name, design_name=name,
                   initiate=False, options=dict(begin_disable_autosave=False,
                   close_enable_autosave=False, sample_holder_top="1.5mm",
                   sample_holder_bottom="-1.5mm"))
    renderer.current_app = hfss
    renderer._desktop = hfss.desktop_class
    if not hfss.modeler.object_names:
        renderer.render_design(selection=None,
            open_pins=[("P1", "in"), ("P2", "in")] if kind == "Eigen" else [],
            port_list=[] if kind == "Eigen" else [("P1", "in", 50), ("P2", "in", 50)],
            jj_to_port=[], ignored_jjs=[], box_plus_buffer=False)
        hfss["Lj"] = f"{DEFAULTS['junction_nH']}nH"
        rlcs = [b for b in hfss.boundaries if b.type == "Lumped RLC"]
        assert len(rlcs) == 1, f"Expected one junction RLC: {[b.name for b in hfss.boundaries]}"
        rlcs[0].props["Inductance"] = "Lj"
        assert rlcs[0].update()
        # Do not use room-temperature silicon conductivity/loss as a cryogenic model.
        mat = hfss.materials["silicon"]
        mat.conductivity = 0
        mat.dielectric_loss_tangent = 0
        assert hfss.save_project(str(project_file))
    objects = hfss.modeler.object_names
    assert {"pad_top_Q1", "pad_bot_Q1", "vacuum_box"}.issubset(objects)
    assert not hfss.modeler.unclassified_names, hfss.modeler.unclassified_names
    if kind != "Eigen":
        assert len(hfss.excitation_names) == 2, hfss.excitation_names
    save_json(ROOT / "results" / f"model_W{width:g}_{kind}.json", dict(
        project=str(project_file), design=name, objects=objects,
        boundaries=[dict(name=b.name, type=b.type, props=dict(b.props)) for b in hfss.boundaries],
        solution_type=hfss.solution_type, excitations=hfss.excitation_names))
    print("MODEL_READY", name, len(objects), "objects", flush=True)
    return hfss, renderer


def solve_eigen(hfss, renderer, width, passes=16):
    if "EigenSetup" not in hfss.setup_names:
        setup = renderer.add_hfss_em_setup(name="EigenSetup", MinimumFrequency=2,
            NumModes=2, MaxDeltaFreq=0.3, MaximumPasses=passes,
            MinimumPasses=3, MinimumConvergedPasses=2, PercentRefinement=25, BasisOrder=1)
        setup.props["SaveFields"] = True
        setup.update()
    else:
        setup = hfss.get_setup("EigenSetup")
        setup.props["MaximumPasses"] = passes
        setup.update()
    if not hfss.mesh.meshoperations:
        jj = next(n for n in hfss.modeler.object_names if n.startswith("JJ_rect_"))
        assert hfss.mesh.assign_length_mesh(assignment=[jj], inside_selection=False,
            maximum_length="5um", maximum_elements=None, name="JunctionMesh")
    assert hfss.save_project()
    print("SOLVING_EIGEN", width, flush=True)
    assert hfss.analyze_setup("EigenSetup", cores=2, tasks=1, gpus=0,
                             use_auto_settings=False, blocking=True)
    hfss=connect(hfss.design_name,Path(hfss.project_file),"Eigenmode",hfss.desktop_class.port)
    assert hfss.save_project()
    solution = hfss.post.get_solution_data(expressions=["Mode(1)", "Mode(2)"],
        setup_sweep_name="EigenSetup : LastAdaptive", report_category="Eigenmode Parameters")
    assert solution
    freqs = [float(expression_data(solution, f"Mode({i})")[1][0]) for i in (1, 2)]
    data = dict(width_um=width, frequencies_raw=freqs,
                units=dict(solution.units_data), setup=dict(hfss.get_setup("EigenSetup").props))
    solution.export_data_to_csv(str(ROOT / "results" / f"eigen_W{width:g}.csv"))
    hfss.export_convergence("EigenSetup", output_file=str(ROOT / "results" / f"convergence_W{width:g}.csv"))
    save_json(ROOT / "results" / f"eigen_W{width:g}.json", data)
    print("EIGEN_RESULTS", data, flush=True)
    return data


def run_epr(hfss, width):
    import pyEPR as epr
    from pyEPR import ansys
    epr.config.root_dir = str(ROOT / "results" / "epr")
    # pyEPR's field/calculator wrappers can use the existing AEDT API handles.
    # This binds the explicit project/design and avoids attaching to another GUI.
    p = epr.ProjectInfo(project_name=hfss.project_name, design_name=hfss.design_name,
                        setup_name="EigenSetup", do_connect=False)
    p.app = hfss
    p.desktop = ansys.HfssDesktop(None, hfss.odesktop)
    p.project = ansys.HfssProject(p.desktop, hfss.oproject)
    p.design = ansys.HfssDesign(p.project, hfss.odesign)
    p.setup = p.design.get_setup("EigenSetup")
    p.dissipative["pinfo"] = p
    rects = [n for n in hfss.modeler.object_names if n.startswith("JJ_rect_")]
    lines = [n for n in hfss.modeler.object_names if n.startswith("JJ_") and not n.startswith("JJ_rect_")]
    assert len(rects) == len(lines) == 1, (rects, lines)
    p.junctions["j0"] = dict(Lj_variable="Lj", rect=rects[0], line=lines[0], length=30e-6)
    p.validate_junction_info()
    distributed = epr.DistributedAnalysis(p)
    distributed.do_EPR_analysis()
    quantum = epr.QuantumAnalysis(distributed.data_filename)
    results = quantum.analyze_all_variations(analyze_previous=True, cos_trunc=10, fock_trunc=14)
    quantum.report_results(numeric=True)
    compact = {}
    for variation, result in results.items():
        import numpy as np
        compact[variation] = {}
        for key in ("f_0", "f_1", "f_ND", "chi_O1", "chi_ND", "Pm_normed", "Pm_raw"):
            value = np.real_if_close(np.asarray(result[key]), tol=1000)
            assert not np.iscomplexobj(value), (key, value)
            compact[variation][key] = value.tolist()
    save_json(ROOT / "results" / f"epr_W{width:g}.json", dict(
        distributed_file=str(distributed.data_filename), variations=compact,
        frequency_unit="MHz", cos_trunc=10, fock_trunc=14,
        chi_convention="positive magnitudes; diagonal = |anharmonicity|; off-diagonal = full cross-Kerr = |2chi|"))
    print("EPR_SAVED", distributed.data_filename, flush=True)
    return quantum


def solve_driven(hfss, width, center_ghz=6.5):
    if "ReadoutSetup" not in hfss.setup_names:
        setup = hfss.create_setup("ReadoutSetup")
        setup.props.update(Frequency=f"{center_ghz}GHz", MaximumPasses=16,
            MinimumPasses=3, MinimumConvergedPasses=2, MaxDeltaS=0.01,
            PercentRefinement=25, BasisOrder=1)
        setup.update()
    setup=hfss.get_setup("ReadoutSetup")
    setup.props["MaximumPasses"]=16
    # Eigenmode endcaps and driven port sheets differ geometrically, so AEDT's
    # mesh-link equivalence check rejects a direct link. Refine independently.
    setup.props["MeshLink"]["ImportMesh"]=False
    setup.update()
    existing_mesh = {m.name for m in hfss.mesh.meshoperations}
    if "JunctionMesh" not in existing_mesh:
        jj=next(n for n in hfss.modeler.object_names if n.startswith("JJ_rect_"))
        assert hfss.mesh.assign_length_mesh([jj],inside_selection=False,
            maximum_length="5um",maximum_elements=None,name="JunctionMesh")
    if "ReadoutMesh" not in existing_mesh:
        assert hfss.mesh.assign_length_mesh(
            ["trace_Readout_shortline","second_cpw_Tee_shortline"],
            inside_selection=False,maximum_length="20um",maximum_elements=None,name="ReadoutMesh")
    if "Locate" not in hfss.get_setup("ReadoutSetup").get_sweep_names():
        sweep = hfss.create_linear_count_sweep(setup="ReadoutSetup", unit="GHz",
            start_frequency=center_ghz-0.06, stop_frequency=center_ghz+0.06,
            num_of_freq_points=241, name="Locate", save_fields=False, sweep_type="Fast")
        assert sweep
    hfss.save_project()
    print("SOLVING_DRIVEN", width, center_ghz, flush=True)
    assert hfss.analyze_setup("ReadoutSetup", cores=2, tasks=1, gpus=0,
                             use_auto_settings=False, blocking=True)
    # Acquire fresh API handles after a long solve (AEDT may invalidate handles).
    hfss=connect(hfss.design_name, Path(hfss.project_file), "Modal", hfss.desktop_class.port)
    export_driven(hfss,width)
    hfss.save_project()


def export_driven(hfss,width):
    import numpy as np
    expression = transmission_expression(hfss)
    data = hfss.post.get_solution_data(expressions=[expression],
        setup_sweep_name="ReadoutSetup : Locate", domain="Sweep")
    assert data
    x, real = expression_data(data, expression, "real")
    _, imag = expression_data(data, expression, "imag")
    out = np.column_stack([x, real, imag])
    np.savetxt(ROOT / "results" / f"s21_W{width:g}.csv", out, delimiter=",",
               header="frequency_GHz,S21_real,S21_imag", comments="")
    idx = np.argmin(abs(out[:, 1]+1j*out[:, 2]))
    print("S21_MIN", out[idx], flush=True)
    save_json(ROOT / "results" / f"driven_W{width:g}.json", dict(
        frequency_unit=data.units_sweeps, expression=expression,
        minimum_frequency_GHz=float(out[idx,0]), minimum_magnitude=float(abs(out[idx,1]+1j*out[idx,2]))))
    hfss.export_convergence("ReadoutSetup", output_file=str(ROOT / "results" / f"driven_convergence_W{width:g}.csv"))


def solve_fine(hfss, width):
    import numpy as np
    locate = np.loadtxt(ROOT / "results" / f"s21_W{width:g}.csv", delimiter=",", skiprows=1)
    index = int(np.argmin(abs(locate[:,1]+1j*locate[:,2])))
    assert 3 <= index <= len(locate)-4, "Locate sweep missed the resonance; adjust center first"
    center = float(locate[index,0])
    if "Fine" not in hfss.get_setup("ReadoutSetup").get_sweep_names():
        assert hfss.create_linear_count_sweep(setup="ReadoutSetup", unit="GHz",
            start_frequency=center-0.01, stop_frequency=center+0.01,
            num_of_freq_points=401, name="Fine", save_fields=False, sweep_type="Fast")
    hfss.save_project()
    assert hfss.analyze_setup("ReadoutSetup", cores=2, tasks=1, gpus=0,
                             use_auto_settings=False, blocking=True)
    hfss=connect(hfss.design_name,Path(hfss.project_file),"Modal",hfss.desktop_class.port)
    hfss.save_project()
    export_fine(hfss,width)


def export_fine(hfss,width):
    import numpy as np
    expression=transmission_expression(hfss)
    output_port,input_port=expression[2:-1].split(",")
    reverse=f"S({input_port},{output_port})"
    reflection=f"S({input_port},{input_port})"
    data=hfss.post.get_solution_data(expressions=[expression,reverse,reflection],
        setup_sweep_name="ReadoutSetup : Fine", domain="Sweep")
    assert data
    x,real=expression_data(data,expression,"real")
    _,imag=expression_data(data,expression,"imag")
    out=np.column_stack([x,real,imag])
    z=np.asarray(real)+1j*np.asarray(imag)
    zr=np.asarray(expression_data(data,reverse,"real")[1])+1j*np.asarray(expression_data(data,reverse,"imag")[1])
    refl=np.asarray(expression_data(data,reflection,"real")[1])+1j*np.asarray(expression_data(data,reflection,"imag")[1])
    save_json(ROOT/"results"/f"physical_checks_W{width:g}.json",dict(
        s21_expression=expression,sweep="ReadoutSetup : Fine",
        max_reciprocity_error=float(np.max(abs(z-zr))),
        max_lossless_power_balance_error=float(np.max(abs(abs(z)**2+abs(refl)**2-1)))))
    np.savetxt(ROOT/"results"/f"s21_W{width:g}_fine.csv",out,delimiter=",",
        header="frequency_GHz,S21_real,S21_imag",comments="")
    from analyze import fit_s21
    result,*_=fit_s21(ROOT/"results"/f"s21_W{width:g}_fine.csv")
    save_json(ROOT/"results"/f"fit_W{width:g}.json",result)
    print("FINE_FIT",result,flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["build", "eigen", "epr", "driven", "extract", "fine", "all"], default="eigen")
    parser.add_argument("--width", type=float, default=200)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--center", type=float, default=None)
    parser.add_argument("--passes", type=int, default=16)
    parser.add_argument("--project", default="readout_cell_v2")
    args = parser.parse_args()
    enable_compat()
    design = make_cell(args.width)
    export_layout(design, args.width)
    project_file = ROOT / "models" / f"{args.project}.aedt"
    stages = ["eigen", "epr", "driven", "fine"] if args.phase == "all" else [args.phase]
    state = dict(started=datetime.now().isoformat(), args=vars(args), completed=[])
    state_path = ROOT / "results" / f"status_W{args.width:g}.json"
    save_json(state_path, state)
    try:
        for stage in stages:
            kind = "Driven" if stage in ("driven", "extract", "fine") else "Eigen"
            h, r = build(design, args.width, kind, project_file, args.port)
            if stage == "eigen":
                solve_eigen(h, r, args.width, args.passes)
            elif stage == "epr":
                run_epr(h, args.width)
            elif stage == "driven":
                center = args.center
                if center is None:
                    eig = json.loads((ROOT / "results" / f"eigen_W{args.width:g}.json").read_text())
                    center = max(eig["frequencies_raw"]) / 1e9
                solve_driven(h, args.width, center)
            elif stage == "fine":
                solve_fine(h, args.width)
            elif stage == "extract":
                export_driven(h,args.width)
                if "Fine" in h.get_setup("ReadoutSetup").get_sweep_names():
                    export_fine(h,args.width)
                h.save_project()
            state["completed"].append(stage)
            save_json(state_path, state)
    except Exception as exc:
        state["error"] = repr(exc)
        save_json(state_path, state)
        raise


if __name__ == "__main__":
    main()
