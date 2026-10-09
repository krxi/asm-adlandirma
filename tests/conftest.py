import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ornek  # noqa: E402


@pytest.fixture
def ornek_kok(tmp_path):
    """tmp_path/veri altında küçük örnek veri; testler cwd'yi buraya alabilir."""
    ornek.kur(tmp_path)
    return tmp_path
