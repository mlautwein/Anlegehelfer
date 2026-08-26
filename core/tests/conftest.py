from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "core" / "src"
FIXTURES = REPO / "fixtures" / "synthetic"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Jeder Test bekommt ein frisches lokales Datenverzeichnis."""
    monkeypatch.setenv("LIMS_DATA_DIR", str(tmp_path / "lims-data"))
    yield


@pytest.fixture()
def fixtures_dir() -> Path:
    assert FIXTURES.is_dir(), "Fixtures fehlen - scripts/make_fixtures.py ausfuehren"
    return FIXTURES


@pytest.fixture()
def db_con(tmp_path):
    from lims_assistant.store import db

    con = db.connect(tmp_path / "test.sqlite")
    yield con
    con.close()


@pytest.fixture()
def settings():
    from lims_assistant.config import Settings

    return Settings()


def analyze_fixture(con, settings, sources, hint_text="", llm_adapter=None, session_id=None):
    from lims_assistant.contracts.models import AnalyzePayload
    from lims_assistant.pipeline.analyze import run_analyze

    payload = AnalyzePayload(
        session_id=session_id, sources=sources, hint_text=hint_text
    )
    return run_analyze(con, settings, payload, llm_adapter=llm_adapter)


@pytest.fixture()
def run_pdf(db_con, settings, fixtures_dir):
    from lims_assistant.contracts.models import AnalyzeSource

    def _run(name: str, **kwargs):
        return analyze_fixture(
            db_con,
            settings,
            [AnalyzeSource(type="pdf", paths=[str(fixtures_dir / name)])],
            **kwargs,
        )

    return _run
