import numpy as np
from pathlib import Path
from ase.data import atomic_numbers
from ase.atoms import Atoms

def parse_vasp_locpot(fileobj):
    name = fileobj.readline().strip()
    scale = float(fileobj.readline().strip())
    cell = np.array(
        [list(map(
            float, 
            fileobj.readline().strip().split()
            )) for _ in range(3)]
    ) * scale
    
    symbols = fileobj.readline().strip().split()
    counts = map(int, fileobj.readline().strip().split())
    numbers = [atomic_numbers[s] for s, c in zip(symbols, counts) for _ in range(c)]
    coord = fileobj.readline().strip()
    reduced_positions = np.fromfile(fileobj, 
                                    dtype = float, 
                                    count = len(numbers) * 3, 
                                    sep = " "
                                    ).reshape(-1, 3)
    positions = reduced_positions @ cell.T
    
    atoms = Atoms(numbers = numbers, 
                  positions = positions, 
                  cell = cell, 
                  pbc = True
                  )
    
    nx, ny, nz = map(int, fileobj.readline().strip().split())
    vol = np.fromfile(fileobj, dtype = float, count = nx * ny * nz, sep = " ").reshape(nx, ny, nz)
    
    return atoms, vol
    
if __name__ == "__main__":
    with open("LOCPOT", "r") as f:
        parse_vasp_locpot(f)