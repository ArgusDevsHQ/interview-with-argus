from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from net_new.dataset import Dataset


def test_demo_app_opens_and_empty_window_is_valid(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("ARGUS_DATASET", str(root / "data/demo"))
    app = AppTest.from_file(str(root / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert any(box.label == "Company selection" for box in app.radio)
    assert any("Fictional demo" in item.value for item in app.get("html"))
    filing_buttons = [b for b in app.button if "8-K" in b.label]
    assert len(filing_buttons) == 4
    filing_buttons[-1].click().run()
    assert not app.exception
    assert any(
        "A comparison with earlier disclosures is not available" in item.value for item in app.info
    )
    dataset = Dataset(root / "data/demo")
    filter_key = f"chart-filter-{dataset.fingerprint}-{dataset.tickers[0]}"
    app.session_state[filter_key] = (date(2024, 9, 11), date(2024, 9, 13), None)
    app.run()
    assert not app.exception
    assert any("No matching 8-K" in message.value for message in app.info)

    next(button for button in app.button if button.label == "Clear selection").click().run()
    assert not app.exception
    assert len([button for button in app.button if "8-K" in button.label]) == 4


def test_investor_view_has_no_pipeline_or_dataset_controls(monkeypatch):
    import net_new.pipeline

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("ARGUS_DATASET", str(root / "data/demo"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-no-network")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    def no_execution(*args, **kwargs):
        raise AssertionError("Investor interactions must not execute the model")

    monkeypatch.setattr(net_new.pipeline, "run_replay", no_execution)
    app = AppTest.from_file(str(root / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert [radio.label for radio in app.radio] == ["Company selection"]
    assert not app.text_input
    assert not any(button.label in {"Run new analysis", "Open run"} for button in app.button)
    assert not app.get("json")
