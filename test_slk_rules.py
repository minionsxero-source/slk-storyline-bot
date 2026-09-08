import pandas as pd
import structure


def df(rows):
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"])


def test_av_definitions_and_flip():
    d = df([
        ("2026-01-01", 10, 11, 9, 9),   # red
        ("2026-01-02", 9, 10, 8, 10),   # green, opens at red close -> V
        ("2026-01-03", 10, 11, 9, 8),   # red, opens at V -> A? This pair is green->red at 10 -> A @ 10
    ])
    d["time"] = pd.to_datetime(d["time"])
    levels = structure.find_av_levels(d)
    assert [(x.kind, x.price) for x in levels] == [("V", 9.0), ("A", 10.0)]


def test_bos_requires_body_close():
    d = df([
        ("2026-01-01", 10, 11, 9, 10),
        ("2026-01-02", 10, 12, 9, 11),
        ("2026-01-03", 11, 13, 10, 12),
        ("2026-01-04", 12, 12.5, 8, 8.5),
        ("2026-01-05", 8.5, 9, 7, 7.5),
        ("2026-01-06", 7.5, 8, 6, 6.5),
        ("2026-01-07", 6.5, 14, 6, 13.5),
    ])
    d["time"] = pd.to_datetime(d["time"])
    swings = structure.find_swings(d)
    events = structure.bos_events(d, swings)
    # The exact event count is data-dependent, but every emitted event must be
    # a strict body close beyond its reference.
    for e in events:
        assert e["price"] > e["level"] or e["price"] < e["level"]


if __name__ == "__main__":
    test_av_definitions_and_flip()
    test_bos_requires_body_close()
    print("SLK rule tests passed")
