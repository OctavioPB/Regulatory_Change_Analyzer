"""Regulation identity: only versions of the same circular are diffed against each other."""
import pytest

from src.nlp.regulation_id import regulation_key, title_prefilter


@pytest.mark.parametrize("title,key", [
    ("Circular 12/2025 — Modificación límites SOFOM", "circular:12/2025"),
    ("Circular CNBV 7/2026", "circular:7/2026"),
    ("CIRCULAR No. 03/2024 relativa a ...", "circular:3/2024"),
    ("Circular Núm. 14 / 2023", "circular:14/2023"),
    ("Resolución que modifica la Circular 12/2025", "circular:12/2025"),
    ("Resolución que modifica la Circular Única de Bancos", "circular-unica:bancos"),
    ("Circular 5/2025 que modifica la Circular Única de Emisoras", "circular:5/2025"),
    ("SEC Proposes Rule on Crypto Asset Custody", None),
    ("Aviso 12/2025", None),
    ("", None),
])
def test_regulation_key(title, key):
    assert regulation_key(title) == key


def test_different_circulars_have_different_keys():
    assert regulation_key("Circular 12/2025 — A") != regulation_key("Circular 15/2025 — B")
    assert regulation_key("Circular 1/2025") != regulation_key("Circular 1/2024")


def test_prefilter_matches_every_spelling_of_the_key():
    import fnmatch
    pattern = title_prefilter("circular:3/2024").replace("%", "*")
    for title in ("circular no. 03/2024", "circular 3 / 2024"):
        assert fnmatch.fnmatch(title, pattern)
