"""DP 正确性对拍：随机小规模用例，对照完整枚举。"""

import itertools
import random
import sys

sys.path.insert(0, "/workspace/api")

from app.solver import Box, Station, solve


def brute(increments, stations):
    n = len(increments)
    best = None
    all_opt = []
    for choices in itertools.product(
        *[range(len(s.boxes) + 1) for s in stations]
    ):
        v, cnt, loss = 0, 0, 0
        ok = True
        seq = []
        for i, ch in enumerate(choices):
            v += increments[i]
            if ch != 0:
                b = stations[i].boxes[ch - 1]
                v += b.correction
                loss += b.loss
                cnt += 1
            if not (stations[i].lower <= v <= stations[i].upper):
                ok = False
                break
            seq.append(None if ch == 0 else stations[i].boxes[ch - 1].id)
        if not ok:
            continue
        key = (cnt, loss, abs(v))
        if best is None or key < best:
            best = key
            all_opt = [seq]
        elif key == best:
            all_opt.append(seq)
    if best is None:
        return None, []
    all_opt.sort(key=lambda s: [(0, "") if x is None else (1, x) for x in s])
    return best, all_opt[:2]


def dp_result(increments, stations):
    r = solve(increments, stations)
    if r["status"] == "infeasible":
        return None, []
    seqs = []
    for w in r["witnesses"]:
        seqs.append(
            [
                None if item["choice"] is None else item["choice"]["id"]
                for item in w["sequence"]
            ]
        )
    key = (
        r["objective"]["boxes_installed"],
        r["objective"]["total_loss"],
        r["objective"]["final_abs_residual"],
    )
    return key, seqs


def main():
    random.seed(20260919)
    trials = 4000
    for t in range(trials):
        n = random.randint(2, 5)
        incs = [random.randint(-6, 6) for _ in range(n)]
        stations = []
        for i in range(n):
            m = random.randint(0, 3)
            ids = random.sample(
                [f"B{x}" for x in range(6)], m
            )
            boxes = [
                Box(
                    id=bid,
                    correction=random.randint(-6, 6),
                    loss=random.randint(0, 5),
                )
                for bid in ids
            ]
            lo, hi = sorted([random.randint(-10, 2), random.randint(-2, 10)])
            stations.append(Station(lo, hi, boxes))

        bk, bw = brute(incs, stations)
        dk, dw = dp_result(incs, stations)
        if bk != dk:
            print("MISMATCH objective", t, bk, dk)
            print(incs, [(s.lower, s.upper, [(b.id, b.correction, b.loss) for b in s.boxes]) for s in stations])
            sys.exit(1)
        if bw != dw:
            print("MISMATCH witnesses", t)
            print("brute", bw)
            print("dp   ", dw)
            print(incs, [(s.lower, s.upper, [(b.id, b.correction, b.loss) for b in s.boxes]) for s in stations])
            sys.exit(1)
    print(f"OK {trials} trials")


if __name__ == "__main__":
    main()
