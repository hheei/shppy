from typing import cast, Optional
from ase import Atoms as ase_Atoms
from ase.io import read, write


class Atoms(ase_Atoms):
    @classmethod
    def read(cls, filename, index = 0, format:Optional[str] = None):
        atoms = read(filename, index = index, format=format)
        assert isinstance(atoms, ase_Atoms)
        atoms.__class__ = cls
        return cast(Atoms, atoms)
    
    @classmethod
    def read_traj(cls, filename, index = slice(None), format:Optional[str] = None):
        return AtomsList.read(filename, index=index, format=format)

class AtomsList:
    def __init__(self, atoms_list):
        for atoms in atoms_list:
            if isinstance(atoms, ase_Atoms):
                atoms.__class__ = Atoms
                
        self.atoms_list: list[Atoms] = atoms_list

    @classmethod
    def read(cls, filename, index = slice(None), format:Optional[str] = None):
        atoms_list = read(filename, index = index, format=format)
        return cls(atoms_list)
    
    def write(self, filename, format:Optional[str] = None):
        write(filename, self.atoms_list, format=format) # type: ignore

    def __getitem__(self, key):
        return self.atoms_list[key]
    
    def __len__(self):
        return len(self.atoms_list)
    
    def __iter__(self):
        return iter(self.atoms_list)
    
    def __repr__(self):
        return f"Atoms({len(self.atoms_list)} frames)"