#!/usr/bin/env python3
"""Acceptance checks executed by the compose ``verify`` service.

The suite talks to the *real* running API over HTTP (never imports the
application code) and covers:

  1. health and limits endpoints
  2. unique global optimum with full box selection sequence
  3. tie -> exactly the first two lexicographic witness sequences
  4. greedy-zero failure is still solved globally
  5. infeasible -> first station whose reachable state set empties
  6. validation errors located by station and field (HTTP 422)
  7. exact integer arithmetic through the JSON boundary (0.001 steps)
  8. maximum size (80 stations x 12 boxes) solved well under budget

Exit code 0 means all checks passed.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

arg = sys.argv[1] if len(sys.argv) > 1 else "http://api:8000"
BASE = arg if arg.startswith("http://") else f"http://{arg}"

failures: list[str] = []
checks = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global checks
    checks += 1
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(f"{name}: {detail}")


def request(method: str, path: str, body: object = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def wait_for_api(timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/healthz", timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(1)
    return False


def main() -> int:
    print(f"verify target: {BASE}")
    if not wait_for_api():
        print("FATAL: API did not become healthy")
        return 2

    status, body = request("GET", "/healthz")
    check("healthz 200", status == 200 and body == {"status": "ok"})

    status, body = request("GET", "/api/limits")
    check(
        "limits exposed",
        status == 200 and body["stations_max"] == 80 and body["decimal_places"] == 3,
        str(body),
    )

    # 1. Unique optimum.
    line = {
        "stations": [
            {"increment": 6, "lower": 0, "upper": 8,
             "boxes": [{"id": 1, "correction": -3, "loss": 0.5}]},
            {"increment": 5, "lower": 0, "upper": 6,
             "boxes": [{"id": 1, "correction": -4, "loss": 0.2},
                       {"id": 2, "correction": -8, "loss": 0.9}]},
            {"increment": 7, "lower": 0, "upper": 5,
             "boxes": [{"id": 1, "correction": -6, "loss": 0.3},
                       {"id": 2, "correction": -9, "loss": 1.1}]},
        ]
    }
    status, body = request("POST", "/api/solve", line)
    check("unique optimum 200", status == 200, str(body))
    if status == 200:
        check("unique witness", len(body["witnesses"]) == 1, str(body["witnesses"]))
        check(
            "sequence length matches stations",
            len(body["witnesses"][0]) == 3,
        )
        check(
            "lex tie flag false",
            body["summary"]["tie"] is False,
        )

    # 2. Tie: at station 2 a box is mandatory (value 5 is above the upper
    # bound 3); boxes 1 and 2 give identical correction, loss and residual.
    tie_line = {
        "stations": [
            {"increment": 5, "lower": 0, "upper": 9, "boxes": []},
            {"increment": 0, "lower": 0, "upper": 3,
             "boxes": [
                 {"id": 1, "correction": -2, "loss": 0.1},
                 {"id": 2, "correction": -2, "loss": 0.1},
             ]},
        ]
    }
    status, body = request("POST", "/api/solve", tie_line)
    check("tie 200", status == 200, str(body))
    if status == 200:
        w = body["witnesses"]
        check("two witnesses returned", len(w) == 2, str(w))
        check(
            "witnesses sorted by id sequence",
            w == [[None, 1], [None, 2]],
            str(w),
        )
        check(
            "identical objective tuple",
            body["summary"]["tie"] is True,
        )

    # 3. Greedy station-by-station zeroing kills a later station: at station 1
    # zeroing (10 -> 0, inside [0,20]) leaves station 2 unreachable (0 + 5 =
    # 5 below [10,20], box -9 worse); skipping the box keeps 10 -> 15, which
    # is valid everywhere. The global optimum installs ZERO boxes.
    greedy_line = {
        "stations": [
            {"increment": 10, "lower": 0, "upper": 20,
             "boxes": [{"id": 1, "correction": -10, "loss": 0.1}]},
            {"increment": 5, "lower": 10, "upper": 20,
             "boxes": [{"id": 1, "correction": -9, "loss": 0.1}]},
        ]
    }
    status, body = request("POST", "/api/solve", greedy_line)
    check("greedy scenario feasible globally", status == 200, str(body))
    if status == 200:
        check(
            "global plan installs no box where greedy zeroed",
            body["witnesses"][0] == [None, None]
            and body["summary"]["installed_count"] == 0,
            str(body["witnesses"]),
        )

    # 4. Infeasible: first station unreachable.
    status, body = request("POST", "/api/solve", {
        "stations": [
            {"increment": 10, "lower": 0, "upper": 3, "boxes": []},
            {"increment": 0, "lower": 0, "upper": 3, "boxes": []},
        ]
    })
    check("infeasible 409", status == 409, str(body))
    if status == 409:
        check("failed station is 1", body["failed_station"] == 1, str(body))

    status, body = request("POST", "/api/solve", {
        "stations": [
            {"increment": 2, "lower": 0, "upper": 5, "boxes": []},
            {"increment": 10, "lower": 0, "upper": 5, "boxes": []},
        ]
    })
    check("infeasible at station 2",
          status == 409 and body["failed_station"] == 2, str(body))

    # 5. Validation errors located by station and field.
    status, body = request("POST", "/api/solve", {
        "stations": [
            {"increment": 1, "lower": 0, "upper": 2, "boxes": []},
            {"increment": "oops", "lower": 9, "upper": 1,
             "boxes": [
                 {"id": 3, "correction": 0, "loss": -1},
                 {"id": 3, "correction": 0, "loss": 0},
             ]},
        ]
    })
    check("invalid 422", status == 422, str(body))
    if status == 422:
        loc = {(e["station"], e["field"]) for e in body["errors"]}
        check("station 2 increment located", (2, "increment") in loc, str(loc))
        check("station 2 lower>upper located", (2, "lower") in loc, str(loc))
        check("negative loss located", (2, "boxes[0].loss") in loc, str(loc))
        check("duplicate id located", (2, "boxes[1].id") in loc, str(loc))

    # 6. Station count limits.
    status, body = request("POST", "/api/solve", {"stations": []})
    check("too few stations 422", status == 422)
    status, _ = request("POST", "/api/solve",
                        {"stations": [{"increment": 0}] * 81})
    check("too many stations 422", status == 422)
    status, _ = request("POST", "/api/solve", {
        "stations": [
            {"increment": 0, "lower": -1, "upper": 1,
             "boxes": [{"id": i, "correction": 0, "loss": 0}
                       for i in range(13)]},
            {"increment": 0, "lower": -1, "upper": 1, "boxes": []},
        ]
    })
    check("thirteenth box rejected 422", status == 422)

    # 7. Exact arithmetic on the JSON boundary (thousandths).
    import random
    rng = random.Random(42)
    big = {"stations": []}
    for _ in range(80):
        big["stations"].append({
            "increment": rng.choice([-1.5, 0, 1.5]),
            "lower": -20,
            "upper": 20,
            "boxes": [
                {"id": i + 1,
                 "correction": rng.choice([-3, -1.5, 0, 1.5, 3]),
                 "loss": round(rng.random() * 2, 3)}
                for i in range(12)
            ],
        })
    t0 = time.time()
    status, body = request("POST", "/api/solve", big)
    elapsed = time.time() - t0
    check("80x12 solved 200", status == 200, str(body)[:300])
    check("80x12 under 10s", elapsed < 10, f"{elapsed:.2f}s")
    if status == 200:
        check("80 choices returned",
              len(body["witnesses"][0]) == 80, str(len(body["witnesses"][0])))

    # Closed interval boundary inclusive.
    status, body = request("POST", "/api/solve", {
        "stations": [
            {"increment": 5, "lower": 5, "upper": 5, "boxes": []},
            {"increment": -5, "lower": 0, "upper": 0,
             "boxes": [{"id": 1, "correction": 0, "loss": 0}]},
        ]
    })
    check("closed interval boundaries accepted",
          status == 200 and body["witnesses"] == [[None, None]], str(body))

    print(f"\n{checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("ACCEPTANCE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
