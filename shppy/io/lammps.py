import numpy as np

def to_tip4p_data(atoms, padding = [0, 0, 0], typemap = ("H", "O"), model="tip4p/ice"):
    disp = atoms.get_celldisp().flatten()
    cell = np.diag(atoms.cell)
    
    if model == "tip4p/ice":
        mass = {"O": 15.9994, "H": 1.00794}
        charge = {"O": -1.1794, "H": 0.5897}
        pair = {"O": "0.21084 3.16680", "H": "0.00000 0.00000"}
        bond = 0.9572
        angle = 104.52
    else:
        raise ValueError(f"Model {model} not supported")
    
    return "\n".join([
        f"# {model} (written by shppy)",
        "",
        f"{len(atoms)} atoms",
        "2 atom types",
        f"{len(atoms) // 3 * 2} bonds",
        "1 bond types",
        f"{len(atoms) // 3} angles",
        "1 angle types",
        "",
        f"{-padding[0]+disp[0]:.1f} {cell[0] + padding[0]+disp[0]:.1f} xlo xhi",
        f"{-padding[1]+disp[1]:.1f} {cell[1] + padding[1]+disp[1]:.1f} ylo yhi",
        f"{-padding[2]+disp[2]:.1f} {cell[2] + padding[2]+disp[2]:.1f} zlo zhi",
        "",
        "Masses",
        "",
        *(f"{i+1} {mass[typemap[i]]}" for i in range(len(typemap))),
        "",
        "Pair Coeffs",
        "",
        *(f"{i+1} {pair[typemap[i]]}" for i in range(len(typemap))),
        "",
        "Bond Coeffs",
        "",
        f"1 10000 {bond}",
        "",
        "Angle Coeffs",
        "",
        f"1 10000 {angle}",
        "",
        "Atoms",
        "",
        *(f"{i+1} {i//3 + 1} {typemap.index(atoms.symbols[i]) + 1} {charge[atoms.symbols[i]]} {atoms.positions[i,0]:.4f} {atoms.positions[i,1]:.4f} {atoms.positions[i,2]:.4f} 0 0 0" for i in range(len(atoms))),
        "",
        "Bonds",
        "",
        *(f"{i+1} 1 {1 + (i//2 * 3)} {(i//2) * 3 + 2 + i % 2}" for i in range(len(atoms) // 3 * 2)),
        "",
        "Angles",
        "",
        *(f"{i+1} 1 {i*3 + 2} {i*3 +1} {i*3 + 3}" for i in range(len(atoms) // 3)),
    ])