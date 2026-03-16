#%%
import xmltodict as x2d
import numpy as np
from shppy import Atoms
from pathlib import Path
from typing import overload
from dataclasses import dataclass

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
        positions *= 0.529177 # Bohr to Angstrom conversion
        cell = data["cell"]
        cell = [list(map(float, cell[x].split())) for x in ["a1", "a2", "a3"]]
        cell = np.array(cell)
        cell *= 0.529177 # Bohr to Angstrom conversion
        
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

if __name__ == "__main__":
    fixture = Path(__file__).resolve().parents[2] / "tests" / "data" / "espresso" / "ice_mol.xml"
    try:
        ep = EspressoParser(fixture)
    except FileNotFoundError:
        print(f"Sample file not found at {fixture}. Run this example from the repo root where tests/data exists.")
    else:
        b = ep.step_atoms(1)
        print(b)
