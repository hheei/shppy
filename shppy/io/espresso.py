import xmltodict as x2d
import shlex
import numpy as np
import re
from shppy import Atoms
from pathlib import Path
from typing import overload, Any, Optional
from dataclasses import dataclass, field

_RE_INT = re.compile(r"^[+-]?\d+$")
_RE_FLOAT = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][+-]?\d+)?$")
_RE_BOOL_T = re.compile(r"(?i)^\.?T(RUE)?\.?$")
_RE_BOOL_F = re.compile(r"(?i)^\.?F(ALSE)?\.?$")
B2A = 0.529177210903
HA2EV = 27.211386245988

def _format_scalar(value) -> str:
    if isinstance(value, bool):
        return ".true." if value else ".false."
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        s = f"{value:.12g}"
        if "e" in s or "E" in s:
            mant, exp = re.split(r"[eE]", s)
            if "." not in mant:
                mant = mant + "."
            exp_i = int(exp)
            return f"{mant}d{exp_i}"
        return s
    else:
        return f"'{value}'"


def _parse_scalar(s: str):
    s = s.strip()
    if not s:
        return ""

    elif (s.startswith("'") and s.endswith("'")) or (
        s.startswith('"') and s.endswith('"')
    ):
        quote = s[0]
        content = s[1:-1]
        return content.replace(quote + quote, quote)  # 處理 '' -> '

    elif _RE_BOOL_T.fullmatch(s):
        return True
    elif _RE_BOOL_F.fullmatch(s):
        return False

    elif _RE_INT.fullmatch(s):
        try:
            return int(s)
        except ValueError:
            pass

    elif _RE_FLOAT.fullmatch(s):
        try:
            return float(s.replace("D", "e").replace("d", "e"))
        except ValueError:
            pass

    return s


def _nm_parser(text: str) -> dict[str, str]:
    lexer = shlex.shlex(text, punctuation_chars=False)
    lexer.commenters = "#!"
    lexer.whitespace += ","
    lexer.wordchars += ".-+*/"

    tokens = list(lexer)
    tokens.reverse()
    result = {}
    i = 0
    while i < len(tokens):
        try:
            j = tokens.index("=", i)
            key = tokens[j + 1]
            if j == i:
                value = ""
            elif j - i == 1:
                value = _parse_scalar(tokens[j - 1])
            else:
                value = list(_parse_scalar(token) for token in tokens[i:j][::-1])
            result[key] = value
            i = j + 2
        except ValueError:
            break
    
    return result


def _split_sections(text: str, cards: list[str] | None = None) -> dict[str, Any]:
    out = {}
    regex = r"(?:^&(\w+)((?:'[^']*'|\"[^\"]*\"|[^/\"']+)*)/)"

    if cards is not None:
        cards_regex = "|".join(cards)
        cards_regex = rf"(?:^({cards_regex})\b(?:[ \t]+([^\n\r]+?))?[ \t]*(?:\r?\n|\Z)(.*?)(?=^&|^(?:{cards_regex})\b|\Z))"
        regex = f"{regex}|{cards_regex}"

    pattern = re.compile(regex, re.MULTILINE | re.DOTALL)

    for m in pattern.finditer(text):
        if m.group(1):
            key = m.group(1).strip().lower()
            value = _nm_parser(m.group(2))
            out[key] = value

        elif m.group(3):
            key = m.group(3).strip().lower()
            value = m.group(5).strip()
            out[key] = value
            if m.group(4):
                out[f"{key}_mode"] = m.group(4).strip()

    return out

def _from_atomic_structure(dic):
    symbols = [at["@name"] for at in dic["atomic_positions"]["atom"]]
    positions = [
        list(map(float, at["#text"].split()))
        for at in dic["atomic_positions"]["atom"]
    ]
    positions = np.array(positions)
    positions *= B2A
    cell = dic["cell"]
    cell = [list(map(float, cell[x].split())) for x in ["a1", "a2", "a3"]]
    cell = np.array(cell)
    cell *= B2A

    return Atoms(symbols=symbols, positions=positions, cell=cell, pbc=True)



@dataclass
class OutEnergy:
    etot: float
    eband: Optional[float] = None
    ehart: Optional[float] = None
    vtxc: Optional[float] = None
    etxc: Optional[float] = None
    ewald: Optional[float] = None
    demet: Optional[float] = None
    efieldcorr: Optional[float] = None
    potentiostat_contr: Optional[float] = None
    gatefield_contr: Optional[float] = None
    vdW_term: Optional[float] = None
    esol: Optional[float] = None
    levelshift_contr: Optional[float] = None

class XML:
    def __init__(self, path):
        path = Path(path)
        dic = x2d.parse(path.read_text())["qes:espresso"]
        self.inp = XMLIn(path, dic["input"])
        self.step = XMLStep(path, dic["step"])
        self.out = XMLOut(path, dic["output"])
    
    def traj(self) -> list[Atoms]:
        return [self.inp.atoms, *self.step.atoms, self.out.atoms]
    
    
    
class XMLIn:
    def __init__(self, path, dic: dict[str, dict[str, Any]]):
        self.control = dic.pop("control_variables")
        self.electrons = dic.pop("electron_control", {})
        self.spin = dic.pop("spin", {})
        self.dft = dic.pop("dft", {})
        self.ions = dic.pop("ion_control", {})
        
        d = dic.pop("atomic_species")
        self.atomic_species = [(at["@name"], float(at["mass"]), Path(path).parents[2] / self.control["pseudo_dir"] / at["pseudo_file"]) for at in d["species"]]
        self.k_points = dic.pop("k_points_IBZ", {})
        self.bc = dic.pop("boundary_conditions", {})
        # atoms
        dat = dic.pop("atomic_structure")
        self.atoms = _from_atomic_structure(dat)
        # mask
        dat = dic.pop("free_positions")['#text']
        mask = np.fromstring(dat, sep="\n").reshape(-1, 3).astype(bool)
        self.atoms.set_array("mask", mask)
        
        self.data = dic
    
class XMLStep:
    def __init__(self, path, data: list[dict[str, dict[str, Any]]]):
        ca, nss, se, atoms, te, st = [], [], [], [], {}, []
        if not isinstance(data, list):
            data = [data]
        for dat in data:
            scf = dat["scf_conv"]
            ca.append(scf["convergence_achieved"])
            nss.append(scf["n_scf_steps"])
            se.append(scf["scf_error"])

            atoms.append(_from_atomic_structure(dat["atomic_structure"]))
            
            for key, val in dat["total_energy"].items():
                te.setdefault(key, []).append(float(val))
            
            atoms[-1].set_array("forces", np.fromstring(dat["forces"]["#text"], sep="\n").reshape(-1, 3) * HA2EV / B2A)
            st.append(np.fromstring(dat["stress"]["#text"], sep="\n").reshape(3, 3) * HA2EV / B2A**3)
        
        self.scf_convergence_achieved = np.array(ca, dtype=bool)
        self.n_scf_steps = np.array(nss, dtype=int)
        self.scf_error = np.array(se, dtype=float)
        self.atoms: list[Atoms] = atoms
        self.total_energy = {k: np.array(v, dtype=float) for k, v in te.items()}
        self.stress = np.stack(st)
    
class XMLOut:
    def __init__(self, path, dic: dict[str, dict[str, Any]]):
        d = dic.pop("convergence_info")
        self.convergence = {"scf_convergence_achieved": bool(d["scf_conv"]["convergence_achieved"]),
                            "n_scf_steps": int(d["scf_conv"]["n_scf_steps"]),
                            "scf_error": float(d["scf_conv"]["scf_error"]),
                            "opt_convergence_achieved": bool(d["opt_conv"]["convergence_achieved"]),
                            "n_opt_steps": int(d["opt_conv"]["n_opt_steps"]),
                            "opt_error": float(d["opt_conv"]["grad_norm"])
                            }
        self.algorithm = {k: bool(v) for k, v in dic.pop("algorithmic_info", {}).items()}
        self.symmetries = dic.pop("symmetries", {})
        self.basis_set = dic.pop("basis_set", {})
        self.dft = dic.pop("dft", {})
        self.bc = dic.pop("boundary_conditions", {})
        self.magnetization = dic.pop("magnetization", {})
        self.total_energy = {k: float(v) * HA2EV for k, v in dic.pop("total_energy", {}).items()}
        
        d = dic.pop("atomic_species")
        self.atomic_species = [(at["@name"], float(at["mass"]), Path(path).parents[2] / d["@pseudo_dir"] / at["pseudo_file"]) for at in d["species"]]
        self.atoms = _from_atomic_structure(dic.pop("atomic_structure"))
        
        d = dic.pop("band_structure")
        self.band_structure = dict(lsda = bool(d["lsda"]), 
                                   noncolin = bool(d["noncolin"]), 
                                   spinorbit = bool(d["spinorbit"]),
                                   nbnd = int(d["nbnd"]),
                                   nelec = float(d["nelec"]),
                                   fermi_energy = float(d["fermi_energy"]) * HA2EV,
                                   starting_k_points = d["starting_k_points"],
                                   smearing = d["smearing"],
                                   ks_energies = d["ks_energies"]
        )
        
        d = dic.pop("forces")
        self.atoms.set_array("forces", np.fromstring(d["#text"], sep="\n").reshape(-1, 3) * HA2EV / B2A)
        
        d = dic.pop("stress")
        self.stress = np.fromstring(d["#text"], sep="\n").reshape(3, 3) * HA2EV / B2A**3
        
        self.data = dic
        

@dataclass
class PWIn:
    control: dict[str, Any]
    system: dict[str, Any]
    electrons: dict[str, Any]
    ions: dict[str, Any] = field(default_factory=dict)
    cell: dict[str, Any] = field(default_factory=dict)
    fcp: dict[str, Any] = field(default_factory=dict)
    rism: dict[str, Any] = field(default_factory=dict)

    atomic_species: list[tuple[str, float, str]] = field(default_factory=list)
    atoms: Atoms = field(default_factory=Atoms)

    k_points_mode: str = "gamma"
    k_points: str = ""
    additional_k_points: str = ""

    occupations: str = ""
    constraints: str = ""
    solvents: str = ""

    hubbard_mode: str = "atomic"
    hubbard: str = ""

    cards = [
        "K_POINTS",
        "ADDITIONAL_K_POINTS",
        "CELL_PARAMETERS",
        "ATOMIC_SPECIES",
        "ATOMIC_POSITIONS",
        "ATOMIC_VELOCITIES",
        "ATOMIC_FORCES",
        "OCCUPATIONS",
        "CONSTRAINTS",
        "SOLVENTS",
        "HUBBARD",
    ]

    @classmethod
    def read(cls, path):
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        dic = _split_sections(text, cls.cards)

        if "celldm(1)" in dic["system"]:
            scale = dic["system"]["celldm(1)"] * 0.529177210903
        elif "a" in dic["system"]:
            scale = dic["system"]["a"]
        else:
            scale = 1.0

        # ATOMIC_SPECIES
        data = dic.pop("atomic_species")
        res = []
        for line in data.splitlines():
            ele, mass, pseudo = line.split()
            res.append((ele, float(mass), pseudo))
        dic["atomic_species"] = res

        # CELL_PARAMETERS
        data = dic.pop("cell_parameters")
        cell = np.fromstring(data, sep="\n").reshape(3, 3)
        mode = dic.pop("cell_parameters_mode", "angstrom").lower()
        if mode == "bohr":
            cell *= 0.529177210903
        elif mode == "alat":
            cell *= scale

        # ATOMIC_POSITIONS
        data = dic.pop("atomic_positions")
        symbols, positions, mask = [], [], []
        for line in data.splitlines():
            line = line.strip()
            if line.startswith(("#", "!")) or not line:
                continue
            s, px, py, pz, *m = line.split()
            symbols.append(s)
            positions.append((float(px), float(py), float(pz)))
            if len(m) == 0:
                mask.append([1, 1, 1])
            else:
                mask.append([int(x) for x in m])

        positions = np.array(positions)
        mode = dic.pop("atomic_positions_mode", "angstrom").lower()
        if mode == "bohr":
            positions *= 0.529177210903
        elif mode == "alat":
            positions *= scale
        elif mode in {"crystal", "crystal_sg"}:
            positions = positions @ cell

        atoms = Atoms(symbols, positions=np.array(positions), cell=cell, pbc=True)

        atoms.set_array("mask", np.array(mask, dtype=bool))
        dic["atoms"] = atoms

        # ATOMIC_FORCES
        data = dic.pop("atomic_forces", None)
        if data is not None:
            forces = []
            for line in data.splitlines():
                line = line.strip()
                if line.startswith(("#", "!")) or not line:
                    continue
                _, fx, fy, fz = line.split()
                forces.append((float(fx), float(fy), float(fz)))

            forces = np.array(forces)
            atoms.set_array("forces", forces)

        # ATOMIC_VELOCITIES
        data = dic.pop("atomic_velocities", None)
        if data is not None:
            velocities = []
            for line in data.splitlines():
                line = line.strip()
                if line.startswith(("#", "!")) or not line:
                    continue
                _, vx, vy, vz = line.split()
                velocities.append((float(vx), float(vy), float(vz)))

            velocities = np.array(velocities)
            atoms.set_velocities(velocities)

        return cls(**dic)

    def write(self, path):
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# This file is generated by shppy\n")
            f.write(
                "# For detailed parameters, refer to https://www.quantum-espresso.org/Doc/INPUT_PW.html\n"
            )
            for nm in ("control", "system", "electrons", "ions", "cell", "fcp", "rism"):
                data = getattr(self, nm)
                if not data:
                    continue
                MAXLEN = len(max(data.keys(), key=len))
                f.write(f"&{nm.upper()}\n")
                for k, v in sorted(getattr(self, nm).items(), key=lambda x: x[0]):
                    f.write(f"  {k:<{MAXLEN}} = {_format_scalar(v)}\n")
                f.write("/\n\n")

            # K_POINTS
            f.write(f"K_POINTS {self.k_points_mode}\n")
            f.write(self.k_points)
            f.write("\n")

            # ADDITIONAL_K_POINTS
            if self.additional_k_points:
                f.write(f"ADDITIONAL_K_POINTS {self.k_points_mode}\n")
                f.write(self.additional_k_points)
                f.write("\n")

            # CELL_PARAMETERS
            f.write(f"CELL_PARAMETERS angstrom\n")
            for vec in self.atoms.cell.array:
                f.write(f"  {vec[0]:16.12g} {vec[1]:16.12g} {vec[2]:16.12g}\n")
            f.write("\n")

            # ATOMIC_SPECIES
            f.write("ATOMIC_SPECIES\n")
            for s, m, p in self.atomic_species:
                f.write(f"  {s:3s} {m:16.12g} {p}\n")
            f.write("\n")

            if len(self.atoms) > 0:
                # ATOMIC_POSITIONS
                symb = self.atoms.get_chemical_symbols()
                f.write(f"ATOMIC_POSITIONS angstrom\n")
                mask = self.atoms.arrays.get("mask", None)
                for i, (s, pos) in enumerate(zip(symb, self.atoms.get_positions())):
                    f.write(f"  {s:3s} {pos[0]:16.12g} {pos[1]:16.12g} {pos[2]:16.12g}")
                    if mask is None or np.all(mask[i]):
                        f.write("\n")
                    else:
                        f.write(f"    {int(mask[i,0])} {int(mask[i,1])} {int(mask[i,2])}\n")
                f.write("\n")

                # ATOMIC_VELOCITIES
                if "momenta" in self.atoms.arrays:
                    f.write(f"ATOMIC_VELOCITIES\n")
                    m = self.atoms.get_velocities()
                    for s, vec in zip(symb, m):
                        f.write(
                            f"  {s:3s} {vec[0]:16.12g} {vec[1]:16.12g} {vec[2]:16.12g}\n"
                        )
                    f.write("\n")

                # ATOMIC_FORCES
                if "forces" in self.atoms.arrays:
                    f.write("ATOMIC_FORCES\n")
                    for i, (s, force) in enumerate(
                        zip(
                            self.atoms.get_chemical_symbols(),
                            self.atoms.arrays["forces"],
                        )
                    ):
                        f.write(
                            f"  {s:3s} {force[0]:16.12g} {force[1]:16.12g} {force[2]:16.12g}\n"
                        )
                    f.write("\n")

            # OCCUPATIONS
            if self.occupations:
                f.write("OCCUPATIONS\n")
                f.write(self.occupations)
                f.write("\n")

            # CONSTRAINTS
            if self.constraints:
                f.write("CONSTRAINTS\n")
                f.write(self.constraints)
                f.write("\n")

            # SOLVENTS
            if self.solvents:
                f.write("SOLVENTS\n")
                f.write(self.solvents)
                f.write("\n")

            # HUBBARD
            if self.hubbard:
                f.write(f"HUBBARD {self.hubbard_mode}\n")
                f.write(self.hubbard)
                f.write("\n")


@dataclass
class PPIn:
    inputpp: dict[str, Any]
    plot: dict[str, Any]

    @classmethod
    def read(cls, path):
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        dic = _split_sections(text, None)
        return cls(**dic)

    def write(self, path):
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# This file is generated by shppy\n")
            f.write(
                "# For detailed parameters, refer to https://www.quantum-espresso.org/Doc/INPUT_PP.html\n"
            )
            for nm in ("inputpp", "plot"):
                data = getattr(self, nm)
                if not data:
                    continue
                MAXLEN = max(data.keys(), key=len)
                f.write(f"&{nm.upper()}\n")
                for k, v in sorted(getattr(self, nm).items(), key=lambda x: x[0]):
                    f.write(f"  {k:<{MAXLEN}} = {_format_scalar(v)}\n")
                f.write("/\n")