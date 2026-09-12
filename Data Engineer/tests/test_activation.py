import json
import shutil

import pytest
from streamlit.testing.v1 import AppTest
from test_workflow import DEMO

from net_new.activation import activate
from net_new.dataset import Dataset
from net_new.pipeline import InvestorPrediction, run_replay


def test_model_run_activates_and_renders_its_own_content(tmp_path, monkeypatch):
    root = tmp_path / "company"
    shutil.copytree(DEMO, root)
    dataset = Dataset(root)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("ARGUS_DATASET", str(root))

    def predict(context, settings):
        return InvestorPrediction(
            headline="Generated headline " + context["filing_id"],
            overview="Generated investor overview.",
            findings=[],
            limitations="",
        ), {}

    monkeypatch.setattr("net_new.pipeline.fresh_prediction", predict)
    run_replay(dataset, "openai", root / "generated")
    activate(dataset, root / "generated")
    assert json.loads((root / "manifest.json").read_text())["default_run"] == "generated"
    app = AppTest.from_file(str(DEMO.parents[1] / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Generated headline" in x.value for x in app.get("html"))
    assert any("Generated investor overview." in x.value for x in app.markdown)


def test_incomplete_run_does_not_replace_active_content(tmp_path, monkeypatch):
    root = tmp_path / "company"
    shutil.copytree(DEMO, root)
    dataset = Dataset(root)
    original = (root / "manifest.json").read_bytes()
    run_replay(dataset, "extractive-preview", root / "incomplete")
    metadata_path = root / "incomplete/run.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["config"]["provider"] = "openai"
    metadata_path.write_text(json.dumps(metadata))
    records = root / "incomplete/records.jsonl"
    records.write_text(records.read_text().splitlines()[0] + "\n")
    with pytest.raises(ValueError, match="every replay filing"):
        activate(dataset, root / "incomplete")
    assert (root / "manifest.json").read_bytes() == original
