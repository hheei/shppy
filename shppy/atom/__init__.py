from ase import Atoms as ase_Atoms
from ase.io import read, write

class Atoms(ase_Atoms):
    @classmethod
    def read(cls, filename, index = 0, format=None):
        atoms = read(filename, index = index, format=format)
        assert isinstance(atoms, ase_Atoms)
        atoms.__class__ = cls
        return atoms
    
    @classmethod
    def read_traj(cls, filename, index = slice(None), format=None):
        atoms_list = read(filename, index = index, format=format)
        assert isinstance(atoms_list, list)
        for atoms in atoms_list:
            atoms.__class__ = cls
        return atoms_list
    