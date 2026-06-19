from app import bars, config


def _lines(*texts):
    return [{"id": f"rough-{i}", "text": text, "t": i * 1.5} for i, text in enumerate(texts)]


def test_shape_bars_falls_back_without_gateway(monkeypatch):
    monkeypatch.setattr(config, "GATEWAY_KEY", "")
    out = bars.shape_bars(_lines("the shower when you sing in it", "better than beyonce"))
    assert [ln["id"] for ln in out] == ["L0", "L1"]
    assert out[0]["text"] == "the shower when you sing in it"


def test_shape_bars_uses_haiku_model(monkeypatch):
    monkeypatch.setattr(config, "GATEWAY_KEY", "test-key")

    def fake_messages(**kwargs):
        assert kwargs["model"] == "claude-haiku-4-5"
        return {
            "text": """
            [
              {"text":"The shower when you sing in it", "source_start":0, "source_end":0},
              {"text":"Better than Beyonce, I like the sound of fiancee", "source_start":1, "source_end":1}
            ]
            """,
            "model": "claude-haiku-4-5",
        }

    monkeypatch.setattr(bars.llm, "messages", fake_messages)
    out = bars.shape_bars(
        _lines(
            "The shower when you sing in it",
            "Better than Beyonce, I like the sound of fiancee",
        )
    )
    assert [ln["text"] for ln in out] == [
        "The shower when you sing in it",
        "Better than Beyonce, I like the sound of fiancee",
    ]
    assert [ln["id"] for ln in out] == ["L0", "L1"]
    assert out[1]["t"] == 1.5
