"""pytest kökü: modüller repo kökünden ve lora/ altından içe aktarılır."""

import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent
for yol in (KOK, KOK / "lora"):
    if str(yol) not in sys.path:
        sys.path.insert(0, str(yol))


def pytest_collection_modifyitems(config, items):
    # test_cikar_bin.GercekLinkTesti Apple clang, Mach-O ld ve strip -x ister; Linux'ta
    # çalıştırılamaz. CI bu sınıfı macOS işinde ayrıca koşar.
    if sys.platform == "darwin":
        return
    isaret = pytest.mark.skip(reason="Mach-O link/strip gerektirir; yalnız macOS'ta koşar")
    for item in items:
        if item.cls is not None and item.cls.__name__ == "GercekLinkTesti":
            item.add_marker(isaret)
