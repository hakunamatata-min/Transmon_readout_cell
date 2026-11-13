"""Process-local adapters for Quantum Metal 0.9 / PyAEDT 1.9.

Installed packages are never modified. Adapters only translate known renamed
arguments or the legacy lumped-port method, preserving integration directions.
"""
from functools import wraps
from inspect import signature


def enable_compat():
    from ansys.aedt.core import Hfss
    from ansys.aedt.core.modeler.cad.primitives import GeometryModeler

    def adapt(owner, name, renames):
        original = getattr(owner, name)
        if getattr(original, "_readout_adapter", False):
            return
        params = signature(original).parameters
        renames = {a: b for a, b in renames.items() if a not in params and b in params}
        if not renames:
            return

        @wraps(original)
        def wrapped(*args, **kwargs):
            for old, new in renames.items():
                if old in kwargs:
                    if new in kwargs:
                        raise TypeError(f"Both {old} and {new} supplied")
                    kwargs[new] = kwargs.pop(old)
            return original(*args, **kwargs)
        wrapped._readout_adapter = True
        setattr(owner, name, wrapped)

    adapt(GeometryModeler, "create_polyline", {"matname": "material"})
    adapt(GeometryModeler, "thicken_sheet", {"bBothSides": "both_sides"})
    adapt(GeometryModeler, "subtract", {"keepOriginals": "keep_originals"})
    if not hasattr(GeometryModeler, "object_id_dict"):
        GeometryModeler.object_id_dict = property(
            lambda m: {name: m[name].id for name in m.object_names})
    adapt(Hfss, "assign_lumped_rlc_to_sheet", {
        "sheet_name": "assignment", "axisdir": "start_direction",
        "sourcename": "name", "Rvalue": "resistance",
        "Lvalue": "inductance", "Cvalue": "capacitance"})
    if not hasattr(Hfss, "create_lumped_port_to_sheet"):
        def legacy_port(self, sheet_name, portname=None, axisdir=0, impedance=50):
            return self.lumped_port(assignment=sheet_name,
                                    integration_line=axisdir,
                                    impedance=impedance, name=portname)
        Hfss.create_lumped_port_to_sheet = legacy_port
