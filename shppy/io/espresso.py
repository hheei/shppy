import xmltodict as x2d
import numpy as np
import re
from shppy import Atoms
from pathlib import Path
from typing import overload, Any
from dataclasses import dataclass, field

@dataclass
class OutEnergy:
    etot: float
    eband: float
    ehart: float
    vtxc: float
    etxc: float
    ewald: float
    demet: float

class EspressoParser:
    def __init__(self, path):
        """
        Support parsing qe-7.5 output XML format.

        Args:
            path (str): Path to the file.
        """
        path = Path(path)
        if path.suffix == ".xml":
            # Parse Espresso XML output
            with open(path, "r") as f:
                self._data = x2d.parse(f.read())['qes:espresso']
                self.bc: str = self._data["input"]["boundary_conditions"]["assume_isolated"]
                self.pbc = (True, True, self.bc != "esm")
                self._hf_unit = self._data["@Units"] == "Hartree atomic units"
                self.out_energy = OutEnergy(**{k: float(v) for k, v in self._data["output"]["total_energy"].items()})
        else:
            raise NotImplementedError("Only XML output parsing is implemented for now.")
    
    def from_atomic_structure(self, data):
        symbols = [at["@name"] for at in data["atomic_positions"]["atom"]]
        positions = [list(map(float,at["#text"].split())) for at in data["atomic_positions"]["atom"]]
        positions = np.array(positions)
        positions *= 0.529177210903 # Bohr to Angstrom conversion
        cell = data["cell"]
        cell = [list(map(float, cell[x].split())) for x in ["a1", "a2", "a3"]]
        cell = np.array(cell)
        cell *= 0.529177210903 # Bohr to Angstrom conversion
        
        return Atoms(symbols = symbols, positions = positions, cell = cell, pbc = self.pbc)
    
    def in_atoms(self):
        pbc = [True, True, True]
        is_esm = self._data["input"]["boundary_conditions"]["assume_isolated"] == "esm"
        if is_esm:
            pbc[2] = False
        
        atoms = self.from_atomic_structure(self._data["input"]["atomic_structure"])
        
        if is_esm:
            atoms.positions[:, 2] *= -1
            atoms.positions[:, 2] += atoms.cell.array[2, 2] / 2
        
        return self.from_atomic_structure(self._data["input"]["atomic_structure"])

    @overload
    def step_atoms(self, index: int) -> Atoms: ...
    @overload
    def step_atoms(self, index: slice = slice(None)) -> list[Atoms]: ...

    def step_atoms(self, index: int | slice = slice(None)):
        pbc = [True, True, True]
        is_esm = self._data["input"]["boundary_conditions"]["assume_isolated"] == "esm"
        if is_esm:
            pbc[2] = False
        if isinstance(index, slice):
            lst_atoms = [self.from_atomic_structure(step["atomic_structure"]) for step in self._data["step"][index]]
            if is_esm:
                for atoms in lst_atoms:
                    atoms.positions[:, 2] *= -1
                    atoms.positions[:, 2] += atoms.cell.array[2, 2] / 2 
            return lst_atoms
        elif isinstance(index, int):
            atoms = self.from_atomic_structure(self._data["step"][index]["atomic_structure"])
            if is_esm:
                atoms.positions[:, 2] *= -1
                atoms.positions[:, 2] += atoms.cell.array[2, 2] / 2
            return atoms
        else:
            raise TypeError("Index must be an integer or a slice.")
        
    def out_atoms(self):
        pbc = [True, True, True]
        is_esm = self._data["output"]["boundary_conditions"]["assume_isolated"] == "esm"
        if is_esm:
            pbc[2] = False
        atoms = self.from_atomic_structure(self._data["output"]["atomic_structure"])
        if is_esm:
            atoms.positions[:, 2] *= -1
            atoms.positions[:, 2] += atoms.cell.array[2, 2] / 2
        return atoms
    
@dataclass
class EspressoIn:
    """
    Please Refer to https://www.quantum-espresso.org/Doc/INPUT_PW.html#id32
    """
    control: dict[str, Any]
    system: dict[str, Any]
    electrons: dict[str, Any]
    ions: dict[str, Any] = field(default_factory=dict)
    cell: dict[str, Any] = field(default_factory=dict)
    fcp: dict[str, Any] = field(default_factory=dict)
    rism: dict[str, Any] = field(default_factory=dict)
    
    atomic_species: list[tuple[str, float, str]] = field(default_factory=list)
    atomic_unit: str = "angstrom"
    atoms: Atoms = field(default_factory=Atoms)
    mask: np.ndarray = field(default_factory=lambda: np.ones((0, 3), dtype=int))
    
    k_points_mode = "gamma"
    k_points: str = "" #TODO
    
    cell_parameters_mode = "angstrom"
    cell_parameters: np.ndarray = field(default_factory=lambda: np.diag(np.ones(3)))
    
    occupation: list[list[float]] = field(default_factory=lambda: [[]])
    
    constraints: str = "" #TODO
    
    additional_k_points: str = "" #TODO
    
    solvents: str = "" #TODO
    
    hubbard_unit: str = "atomic"
    hubbard: str = "" #TODO

    _BOHR_TO_ANG = 0.529177210903

    @staticmethod
    def _strip_comments(text: str) -> str:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        stripped: list[str] = []
        for line in lines:
            cut = len(line)
            for marker in ("!", "#"):
                idx = line.find(marker)
                if idx != -1:
                    cut = min(cut, idx)
            stripped.append(line[:cut])
        return "\n".join(stripped)

    @staticmethod
    def _extract_namelist(text: str, name: str) -> str | None:
        pattern = re.compile(
            rf"(?ims)^\s*&{re.escape(name)}\b(?P<body>.*?)(?=^\s*/\s*$)"
        )
        match = pattern.search(text)
        return match.group("body") if match else None

    @staticmethod
    def _parse_scalar(text: str) -> Any:
        s = text.strip()
        if len(s) >= 2 and ((s[0] == "'" and s[-1] == "'") or (s[0] == '"' and s[-1] == '"')):
            return s[1:-1]

        low = s.lower()
        if low in {".true.", "true"}:
            return True
        if low in {".false.", "false"}:
            return False

        int_pat = re.compile(r"^[+-]?\d+$")
        float_pat = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][+-]?\d+)?$")
        if int_pat.match(s):
            try:
                return int(s)
            except ValueError:
                pass
        if float_pat.match(s):
            try:
                return float(s.replace("D", "e").replace("d", "e"))
            except ValueError:
                pass
        return s

    @classmethod
    def _parse_namelist(cls, body: str | None) -> dict[str, Any]:
        if not body:
            return {}
        compact = " ".join(body.split())
        item_re = re.compile(
            r"([A-Za-z_][\w().]*)\s*=\s*(.*?)"
            r"(?=\s*,\s*[A-Za-z_][\w().]*\s*=|\s+[A-Za-z_][\w().]*\s*=|\s*$)"
        )
        out: dict[str, Any] = {}
        for m in item_re.finditer(compact):
            key = m.group(1).strip().lower()
            value = m.group(2).strip().rstrip(",")
            out[key] = cls._parse_scalar(value)
        return out

    @staticmethod
    def _extract_card(text: str, name: str) -> tuple[str, str] | None:
        card_names = [
            "ATOMIC_SPECIES",
            "ATOMIC_POSITIONS",
            "K_POINTS",
            "CELL_PARAMETERS",
            "OCCUPATIONS",
            "CONSTRAINTS",
            "ATOMIC_VELOCITIES",
            "ATOMIC_FORCES",
            "ADDITIONAL_K_POINTS",
            "SOLVENTS",
            "HUBBARD",
        ]
        stop_headers = "|".join(card_names)
        pattern = re.compile(
            rf"(?ims)^\s*{re.escape(name)}\b(?:\s*\{{([^}}]+)\}}|\s+([^\n\s]+))?\s*\n"
            rf"(.*?)(?=^\s*(?:{stop_headers})\b|^\s*&\w+\b|\Z)"
        )
        m = pattern.search(text)
        if not m:
            return None
        mode = (m.group(1) or m.group(2) or "").strip().lower()
        body = m.group(3).strip("\n")
        return mode, body

    @classmethod
    def _scale_from_system(cls, system: dict[str, Any]) -> float | None:
        if "celldm(1)" in system:
            try:
                return float(system["celldm(1)"]) * cls._BOHR_TO_ANG
            except ValueError:
                return None
        if "a" in system:
            try:
                return float(system["a"])
            except ValueError:
                return None
        return None

    @classmethod
    def _convert_positions(cls, positions: np.ndarray, unit: str, cell: np.ndarray | None, system: dict[str, Any]) -> np.ndarray:
        unit = unit.lower()
        out = np.array(positions, dtype=float)
        if unit == "angstrom" or unit == "":
            return out
        if unit == "bohr":
            return out * cls._BOHR_TO_ANG
        if unit == "alat":
            scale = cls._scale_from_system(system)
            return out * scale if scale is not None else out
        if unit in {"crystal", "crystal_sg"} and cell is not None and cell.shape == (3, 3):
            return out @ cell
        return out

    @classmethod
    def _convert_cell(cls, cell: np.ndarray, unit: str, system: dict[str, Any]) -> np.ndarray:
        unit = unit.lower()
        out = np.array(cell, dtype=float)
        if unit == "angstrom" or unit == "":
            return out
        if unit == "bohr":
            return out * cls._BOHR_TO_ANG
        if unit == "alat":
            scale = cls._scale_from_system(system)
            return out * scale if scale is not None else out
        return out

    @staticmethod
    def _parse_triplet_lines(body: str) -> list[list[float]]:
        out: list[list[float]] = []
        for line in body.splitlines():
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 4:
                continue
            try:
                out.append([float(parts[1]), float(parts[2]), float(parts[3])])
            except ValueError:
                continue
        return out
    
    @classmethod
    def read(cls, path) -> "EspressoIn":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        clean = cls._strip_comments(text)

        control_body = cls._extract_namelist(clean, "CONTROL")
        system_body = cls._extract_namelist(clean, "SYSTEM")
        electrons_body = cls._extract_namelist(clean, "ELECTRONS")
        ions_body = cls._extract_namelist(clean, "IONS")
        cell_body = cls._extract_namelist(clean, "CELL")
        fcp_body = cls._extract_namelist(clean, "FCP")
        rism_body = cls._extract_namelist(clean, "RISM")

        control = cls._parse_namelist(control_body)
        system = cls._parse_namelist(system_body)
        electrons = cls._parse_namelist(electrons_body)
        ions = cls._parse_namelist(ions_body)
        cell_namelist = cls._parse_namelist(cell_body)
        fcp = cls._parse_namelist(fcp_body)
        rism = cls._parse_namelist(rism_body)

        atomic_species: list[tuple[str, float, str]] = []
        species_card = cls._extract_card(clean, "ATOMIC_SPECIES")
        if species_card:
            _, body = species_card
            for line in body.splitlines():
                s = line.strip()
                if not s:
                    continue
                parts = s.split()
                if len(parts) < 3:
                    continue
                try:
                    atomic_species.append((parts[0], float(parts[1]), parts[2]))
                except ValueError:
                    continue

        cell_parameters_mode = "angstrom"
        cell_parameters = np.diag(np.ones(3))
        parsed_cell: np.ndarray | None = None
        cell_card = cls._extract_card(clean, "CELL_PARAMETERS")
        if cell_card:
            mode, body = cell_card
            cell_parameters_mode = mode or "angstrom"
            rows: list[list[float]] = []
            for line in body.splitlines():
                s = line.strip()
                if not s:
                    continue
                vals = s.split()
                if len(vals) < 3:
                    continue
                try:
                    rows.append([float(vals[0]), float(vals[1]), float(vals[2])])
                except ValueError:
                    continue
                if len(rows) == 3:
                    break
            if len(rows) == 3:
                parsed_cell = cls._convert_cell(np.array(rows, dtype=float), cell_parameters_mode, system)
                cell_parameters = parsed_cell

        atomic_unit = "angstrom"
        atoms = Atoms()
        positions_card = cls._extract_card(clean, "ATOMIC_POSITIONS")
        if positions_card:
            mode, body = positions_card
            atomic_unit = mode or "angstrom"
            symbols: list[str] = []
            coords: list[list[float]] = []
            masks: list[list[int]] = []
            for line in body.splitlines():
                s = line.strip()
                if not s:
                    continue
                parts = s.split()
                if len(parts) < 4:
                    continue
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                except ValueError:
                    continue
                symbols.append(parts[0])
                coords.append([x, y, z])
                if len(parts) >= 7:
                    try:
                        m0, m1, m2 = int(float(parts[4])), int(float(parts[5])), int(float(parts[6]))
                        masks.append([1 if m0 != 0 else 0, 1 if m1 != 0 else 0, 1 if m2 != 0 else 0])
                    except ValueError:
                        masks.append([1, 1, 1])
                else:
                    masks.append([1, 1, 1])

            if symbols:
                raw_positions = np.array(coords, dtype=float)
                cart_positions = cls._convert_positions(raw_positions, atomic_unit, parsed_cell, system)
                atoms = Atoms(symbols=symbols, positions=cart_positions)
                if parsed_cell is not None:
                    atoms.set_cell(parsed_cell)
                parsed_mask = np.array(masks, dtype=int)
            else:
                parsed_mask = np.ones((0, 3), dtype=int)
        else:
            parsed_mask = np.ones((0, 3), dtype=int)

        k_points_mode = "gamma"
        k_points = ""
        k_card = cls._extract_card(clean, "K_POINTS")
        if k_card:
            k_mode, k_body = k_card
            k_points_mode = k_mode or "gamma"
            k_points = k_body.strip()

        occupation: list[list[float]] = [[]]
        occ_card = cls._extract_card(clean, "OCCUPATIONS")
        if occ_card:
            _, occ_body = occ_card
            parsed_occ: list[list[float]] = []
            for line in occ_body.splitlines():
                s = line.strip()
                if not s:
                    continue
                numbers = re.findall(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][+-]?\d+)?", s)
                if numbers:
                    parsed_occ.append([float(x) for x in numbers])
            if parsed_occ:
                occupation = parsed_occ

        constraints = ""
        con_card = cls._extract_card(clean, "CONSTRAINTS")
        if con_card:
            _, constraints = con_card
            constraints = constraints.strip()

        additional_k_points = ""
        add_k_card = cls._extract_card(clean, "ADDITIONAL_K_POINTS")
        if add_k_card:
            _, additional_k_points = add_k_card
            additional_k_points = additional_k_points.strip()

        solvents = ""
        sol_card = cls._extract_card(clean, "SOLVENTS")
        if sol_card:
            _, solvents = sol_card
            solvents = solvents.strip()

        hubbard_unit = "atomic"
        hubbard = ""
        hub_card = cls._extract_card(clean, "HUBBARD")
        if hub_card:
            h_mode, hubbard = hub_card
            hubbard_unit = h_mode or "atomic"
            hubbard = hubbard.strip()

        init_kwargs: dict[str, Any] = {
            "control": control,
            "system": system,
            "electrons": electrons,
        }

        if ions_body is not None:
            init_kwargs["ions"] = ions
        if cell_body is not None:
            init_kwargs["cell"] = cell_namelist
        if fcp_body is not None:
            init_kwargs["fcp"] = fcp
        if rism_body is not None:
            init_kwargs["rism"] = rism

        if species_card is not None:
            init_kwargs["atomic_species"] = atomic_species
        if positions_card is not None and len(atoms) > 0:
            init_kwargs["atomic_unit"] = atomic_unit
            init_kwargs["atoms"] = atoms
            init_kwargs["mask"] = parsed_mask
        if cell_card is not None and parsed_cell is not None:
            init_kwargs["cell_parameters"] = cell_parameters
        if occ_card is not None and occupation != [[]]:
            init_kwargs["occupation"] = occupation
        if con_card is not None:
            init_kwargs["constraints"] = constraints
        if add_k_card is not None:
            init_kwargs["additional_k_points"] = additional_k_points
        if sol_card is not None:
            init_kwargs["solvents"] = solvents
        if k_card is not None:
            init_kwargs["k_points"] = k_points
        if hub_card is not None:
            init_kwargs["hubbard"] = hubbard

        obj = cls(**init_kwargs)

        if k_card is not None:
            obj.k_points_mode = k_points_mode
        if cell_card is not None and parsed_cell is not None:
            obj.cell_parameters_mode = cell_parameters_mode
        if hub_card is not None:
            obj.hubbard_unit = hubbard_unit

        v_card = cls._extract_card(clean, "ATOMIC_VELOCITIES")
        if v_card and len(obj.atoms) > 0:
            _, v_body = v_card
            vel = cls._parse_triplet_lines(v_body)
            if len(vel) == len(obj.atoms):
                obj.atoms.set_velocities(np.array(vel, dtype=float))

        f_card = cls._extract_card(clean, "ATOMIC_FORCES")
        if f_card and len(obj.atoms) > 0:
            _, f_body = f_card
            frc = cls._parse_triplet_lines(f_body)
            if len(frc) == len(obj.atoms):
                obj.atoms.set_array("forces", np.array(frc, dtype=float))

        return obj

    @staticmethod
    def _format_float_fortran(value: float) -> str:
        s = f"{value:.12g}"
        if "e" in s or "E" in s:
            mant, exp = re.split(r"[eE]", s)
            if "." not in mant:
                mant = mant + "."
            exp_i = int(exp)
            return f"{mant}d{exp_i}"
        return s

    @staticmethod
    def _format_namelist_value(value: Any) -> str:
        if isinstance(value, bool):
            return ".true." if value else ".false."
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return EspressoIn._format_float_fortran(value)
        if isinstance(value, str):
            stripped = value.strip()
            parsed = EspressoIn._parse_scalar(stripped)
            if isinstance(parsed, bool):
                return ".true." if parsed else ".false."
            if isinstance(parsed, int):
                return str(parsed)
            if isinstance(parsed, float):
                return EspressoIn._format_float_fortran(parsed)
            if stripped.startswith("'") and stripped.endswith("'"):
                return stripped
            if stripped.startswith('"') and stripped.endswith('"'):
                return stripped
            return f"'{stripped}'"
        return str(value)

    @classmethod
    def _append_namelist(cls, lines: list[str], name: str, data: dict[str, Any]) -> None:
        if not data:
            return
        lines.append(f"&{name}")
        max_key_len = max((len(str(key)) for key in data.keys()), default=0)
        for key, value in data.items():
            key_str = str(key)
            lines.append(f"  {key_str:<{max_key_len}} = {cls._format_namelist_value(value)}")
        lines.append("/")
        lines.append("")

    def write(self, path):
        out_path = Path(path)
        lines: list[str] = [
            "# This file is generated by shppy",
            "# For detailed parameters, refer to https://www.quantum-espresso.org/Doc/INPUT_PW.html#id32",
            "",
        ]

        self._append_namelist(lines, "CONTROL", self.control)
        self._append_namelist(lines, "SYSTEM", self.system)
        self._append_namelist(lines, "ELECTRONS", self.electrons)
        self._append_namelist(lines, "IONS", self.ions)
        self._append_namelist(lines, "CELL", self.cell)
        self._append_namelist(lines, "FCP", self.fcp)
        self._append_namelist(lines, "RISM", self.rism)

        if self.k_points_mode == "gamma" or self.k_points.strip():
            header = "K_POINTS"
            if self.k_points_mode:
                header += f" {self.k_points_mode}"
            lines.append(header)
            if self.k_points.strip():
                lines.extend(x.rstrip() for x in self.k_points.splitlines())
            lines.append("")
            
        if self.additional_k_points.strip():
            lines.append("ADDITIONAL_K_POINTS")
            lines.extend(x.rstrip() for x in self.additional_k_points.splitlines())
            lines.append("")

        if self.atomic_species:
            lines.append("ATOMIC_SPECIES")
            for symbol, mass, pseudo in self.atomic_species:
                lines.append(f"  {symbol} {mass:.10g} {pseudo}")
            lines.append("")

        if isinstance(self.cell_parameters, np.ndarray) and self.cell_parameters.shape == (3, 3):
            header = "CELL_PARAMETERS"
            if self.cell_parameters_mode:
                header += f" {self.cell_parameters_mode}"
            lines.append(header)
            for row in self.cell_parameters:
                lines.append(f"  {row[0]:16.12g} {row[1]:16.12g} {row[2]:16.12g}")
            lines.append("")

        if len(self.atoms) > 0:
            header = "ATOMIC_POSITIONS"
            if self.atomic_unit:
                header += f" {self.atomic_unit}"
            lines.append(header)

            atom_pos = self.atoms.get_positions()
            atom_sym = self.atoms.get_chemical_symbols()
            mask = self.mask if isinstance(self.mask, np.ndarray) else np.ones((0, 3), dtype=int)
            if mask.shape != (len(self.atoms), 3):
                mask = np.ones((len(self.atoms), 3), dtype=int)

            for symbol, pos, m in zip(atom_sym, atom_pos, mask):
                base = f"  {symbol:2s} {pos[0]:15.10f} {pos[1]:15.10f} {pos[2]:15.10f}"
                if int(m[0]) == 1 and int(m[1]) == 1 and int(m[2]) == 1:
                    lines.append(base)
                else:
                    lines.append(f"{base}    {int(m[0])} {int(m[1])} {int(m[2])}")
            lines.append("")

            if "momenta" in self.atoms.arrays:
                velocities = self.atoms.get_velocities()
                if velocities is not None and len(velocities) == len(self.atoms):
                    lines.append("ATOMIC_VELOCITIES")
                    for symbol, vec in zip(atom_sym, velocities):
                        lines.append(f"  {symbol} {vec[0]:15.10g} {vec[1]:15.10g} {vec[2]:15.10g}")
                    lines.append("")

            forces = self.atoms.arrays.get("forces") if hasattr(self.atoms, "arrays") else None
            if forces is not None and len(forces) == len(self.atoms):
                lines.append("ATOMIC_FORCES")
                for symbol, vec in zip(atom_sym, forces):
                    lines.append(f"  {symbol} {vec[0]:15.10g} {vec[1]:15.10g} {vec[2]:15.10g}")
                lines.append("")
                
        if self.occupation and not (len(self.occupation) == 1 and len(self.occupation[0]) == 0):
            lines.append("OCCUPATIONS")
            for row in self.occupation:
                if row:
                    lines.append("  " + " ".join(f"{v:8.5g}" for v in row))
            lines.append("")

        if self.constraints.strip():
            lines.append("CONSTRAINTS")
            lines.extend(x.rstrip() for x in self.constraints.splitlines())
            lines.append("")
            
        if self.solvents.strip():
            lines.append("SOLVENTS")
            lines.extend(x.rstrip() for x in self.solvents.splitlines())
            lines.append("")

        if self.hubbard.strip():
            header = "HUBBARD"
            if self.hubbard_unit:
                header += f" {self.hubbard_unit}"
            lines.append(header)
            lines.extend(x.rstrip() for x in self.hubbard.splitlines())
            lines.append("")

        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        
