from pathlib import Path

import pytest

from shppy.atom import Atoms
from shppy.io.espresso import EspressoParser

FIXTURE_PATH = Path(__file__).parent / "data" / "espresso" / "ice_mol.xml"
assert FIXTURE_PATH.exists(), "tests/data/espresso/ice_mol.xml fixture is missing"


@pytest.fixture(scope="module")
def espresso_parser():
    return EspressoParser(FIXTURE_PATH)


def test_parser_loads_metadata(espresso_parser):
    assert espresso_parser.bc
    assert isinstance(espresso_parser.pbc, tuple)
    assert isinstance(espresso_parser.out_energy.etot, float)
    assert isinstance(espresso_parser._hf_unit, bool)


def test_step_atoms_single(espresso_parser):
    atoms = espresso_parser.step_atoms(0)
    assert isinstance(atoms, Atoms)
    assert len(atoms) > 0
    assert tuple(bool(flag) for flag in atoms.pbc) == espresso_parser.pbc


def test_step_atoms_slice(espresso_parser):
    atoms_list = espresso_parser.step_atoms(slice(0, 2))
    assert isinstance(atoms_list, list)
    assert len(atoms_list) == 2
    for atoms in atoms_list:
        assert isinstance(atoms, Atoms)
        assert atoms.cell.array.shape == (3, 3)
