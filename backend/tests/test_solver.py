"""Solver correctness tests, including a brute-force oracle comparison.

The production solver never enumerates combinations; the test oracle below
*does* enumerate on tiny random instances solely to cross-check the dynamic
program. Run: python -m pytest tests/ -q  (or python tests/test_solver.py).
"""

from __future__ import annotations

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.solver import solve  # noqa: E402
from app.validation import (  # noqa: E402
    CandidateBox,
    LineInput,
    Station,
    validate_line,
    parse_line,
)


def brute_force(line: LineInput):
    """Enumerate every choice sequence (oracle for tiny instances)."""

    stations = line.stations
    n = len(stations)

    reachable = {0: [()]}  # value -> list of choice tuples (None or box id)
    failed = None
    for j, st in enumerate(stations):
        nxt: dict[int, list] = {}
        for value, seqs in reachable.items():
            base = value + st.increment_int
            choices: list[tuple[int | None, int]] = [(None, 0)]
            choices.extend(
                (b.id, b.loss_int)
                for b in st.boxes
            )
            corrections = {None: 0}
            losses = {None: 0}
            for b in st.boxes:
                corrections[b.id] = b.correction_int
                losses[b.id] = b.loss_int
            for seq in seqs:
                for cid, _l in choices:
                    nv = base + corrections[cid]
                    if st.lower_int <= nv <= st.upper_int:
                        nxt.setdefault(nv, []).append(seq + (cid,))
        if not nxt:
            failed = j + 1
            break
        reachable = nxt

    if failed is not None:
        return {"status": "infeasible", "failed_station": failed}

    best = []
    for value, seqs in reachable.items():
        for seq in seqs:
            count = sum(1 for x in seq if x is not None)
            loss = 0
            by_station_box = {}
            for st, cid in zip(stations, seq):
                if cid is not None:
                    for b in st.boxes:
                        if b.id == cid:
                            loss += b.loss_int
            best.append((count, loss, abs(value), seq))

    def seq_key(seq):
        return tuple(-1 if x is None else x for x in seq)

    best.sort(key=lambda t: (t[0], t[1], t[2], seq_key(t[3])))
    obj = best[0][:3]
    winners = sorted(
        {t[3] for t in best if (t[0], t[1], t[2]) == obj},
        key=seq_key,
    )
    return {
        "status": "optimal",
        "count": obj[0],
        "loss": obj[1],
        "residual": obj[2],
        "witnesses": [list(w) for w in winners[:2]],
    }


def make_line(raw):
    return parse_line(raw)


def test_simple_unique():
    line = make_line(
        {
            "stations": [
                {"increment": 5, "lower": 0, "upper": 10, "boxes": []},
                {
                    "increment": 6,
                    "lower": 0,
                    "upper": 10,
                    "boxes": [
                        {"id": 1, "correction": -2, "loss": 0.5}
                    ],
                },
            ]
        }
    )
    r = solve(line)
    assert r["status"] == "optimal"
    assert r["witnesses"][0] == [None, 1]
    assert r["summary"]["installed_count"] == 1


def test_min_boxes_takes_precedence():
    # A zero-box solution exists; even if a boxed one has lower residual,
    # installing fewer boxes must win.
    line = make_line(
        {
            "stations": [
                {"increment": 1, "lower": 0, "upper": 5, "boxes": []},
                {
                    "increment": 1,
                    "lower": 0,
                    "upper": 5,
                    "boxes": [
                        {"id": 7, "correction": -1, "loss": 0.0}
                    ],
                },
            ]
        }
    )
    r = solve(line)
    assert r["witnesses"][0] == [None, None]
    assert r["summary"]["installed_count"] == 0
    assert r["summary"]["final_abs_residual_milli"] == 2000


def test_infeasible_station():
    line = make_line(
        {
            "stations": [
                {"increment": 10, "lower": 0, "upper": 5, "boxes": []},
                {"increment": 0, "lower": 0, "upper": 5, "boxes": []},
            ]
        }
    )
    r = solve(line)
    assert r["status"] == "infeasible"
    assert r["failed_station"] == 1


def test_infeasible_at_second_station():
    line = make_line(
        {
            "stations": [
                {"increment": 3, "lower": 0, "upper": 5, "boxes": []},
                {"increment": 10, "lower": 0, "upper": 5, "boxes": []},
            ]
        }
    )
    r = solve(line)
    assert r["failed_station"] == 2


def test_validation_locates_station_and_field():
    errors = validate_line(
        {
            "stations": [
                {"increment": 1, "lower": 0, "upper": 2},
                {
                    "increment": "abc",
                    "lower": 9,
                    "upper": 1,
                    "boxes": [
                        {"id": 1, "correction": 0, "loss": -1},
                        {"id": 1, "correction": 0, "loss": 0},
                    ],
                },
            ]
        }
    )
    fields = {(e.station, e.field) for e in errors}
    assert (2, "increment") in fields
    assert (2, "lower") in fields  # lower > upper
    assert (2, "boxes[0].loss") in fields
    assert (2, "boxes[1].id") in fields  # duplicate id


def test_station_count_limits():
    errors = validate_line({"stations": []})
    assert any("至少" in e.message for e in errors)
    errors = validate_line(
        {"stations": [{"increment": 0}] * 81}
    )
    assert any("至多" in e.message for e in errors)


def test_too_many_boxes_and_decimal_places():
    st = {
        "increment": 0,
        "lower": -1,
        "upper": 1,
        "boxes": [
            {"id": i, "correction": 0, "loss": 0} for i in range(13)
        ],
    }
    errors = validate_line({"stations": [st, st]})
    assert any(e.field == "boxes" and "12" in e.message for e in errors)

    errors = validate_line(
        {
            "stations": [
                {"increment": 0.0001, "lower": 0, "upper": 1},
                {"increment": 0, "lower": 0, "upper": 1},
            ]
        }
    )
    assert any("小数位" in e.message for e in errors)


def test_random_vs_bruteforce():
    rng = random.Random(20260919)
    for trial in range(300):
        n = rng.randint(2, 5)
        raw_stations = []
        for _ in range(n):
            nboxes = rng.randint(0, 4)
            ids = rng.sample(range(1, 9), nboxes)
            boxes = [
                {
                    "id": bid,
                    "correction": rng.choice(
                        [-3, -2, -1, 1, 2, 3, 0]
                    ),
                    "loss": rng.choice([0, 0, 1, 2, 5]) / 10,
                }
                for bid in ids
            ]
            raw_stations.append(
                {
                    "increment": rng.randint(-4, 4),
                    "lower": rng.randint(-6, 2),
                    "upper": rng.randint(2, 8),
                    "boxes": boxes,
                }
            )
        payload = {"stations": raw_stations}
        assert validate_line(payload) == []
        line = parse_line(payload)
        got = solve(line)
        want = brute_force(line)
        if want["status"] == "infeasible":
            assert got["status"] == "infeasible", (trial, payload, got)
            assert got["failed_station"] == want["failed_station"], (
                trial,
                payload,
            )
        else:
            assert got["status"] == "optimal", (trial, payload)
            s = got["summary"]
            assert s["installed_count"] == want["count"]
            assert s["total_insertion_loss_milli_db"] == want["loss"]
            assert (
                s["final_abs_residual_milli"] == want["residual"]
            )
            assert got["witnesses"] == want["witnesses"], (
                trial,
                payload,
                got["witnesses"],
                want["witnesses"],
            )


def test_max_size_performance_and_exactness():
    # 80 stations, 12 boxes each; must finish quickly without floats.
    rng = random.Random(7)
    raw_stations = []
    for _ in range(80):
        raw_stations.append(
            {
                "increment": rng.choice([-1.5, 0, 1.5]),
                "lower": -20,
                "upper": 20,
                "boxes": [
                    {
                        "id": i + 1,
                        "correction": rng.choice([-3, -1.5, 0, 1.5, 3]),
                        "loss": round(rng.random() * 2, 3),
                    }
                    for i in range(12)
                ],
            }
        )
    line = parse_line({"stations": raw_stations})
    import time

    t0 = time.perf_counter()
    r = solve(line)
    elapsed = time.perf_counter() - t0
    assert r["status"] == "optimal"
    assert elapsed < 10, elapsed
    assert len(r["witnesses"][0]) == 80


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
