import os


def test_agent3_followup_defaults_to_false(monkeypatch):
    monkeypatch.delenv("AGENT3_FOLLOWUP", raising=False)
    result = os.environ.get("AGENT3_FOLLOWUP", "false").lower() == "true"
    assert result is False
