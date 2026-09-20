"""边界场景：不可行定位、并列前二、满规模性能与状态计数。"""

import random
import sys
import time

sys.path.insert(0, "/workspace/api")

from app.solver import Box, Station, solve


def test_infeasible_location():
    # 站 1 可达，站 2 任何选择都越界（不装=15，装盒=14/16，区间 [0,10]）
    incs = [5, 10]
    stations = [
        Station(0, 10, [Box("A", 2, 1)]),          # 不装=5 OK；装=7 OK
        Station(0, 10, [Box("A", -1, 1), Box("B", 1, 1)]),
    ]
    r = solve(incs, stations)
    assert r["status"] == "infeasible", r
    assert r["infeasible_station"] == 2, r
    print("infeasible location OK")


def test_first_station_infeasible():
    incs = [100, 0]
    stations = [Station(0, 10, []), Station(0, 10, [])]
    r = solve(incs, stations)
    assert r["infeasible_station"] == 1, r
    print("first-station infeasible OK")


def test_tie_top2():
    # 两站区间都足够宽，所有盒零修正零插损：
    # 最优为 0 盒，唯一；改为构造两条并列最优。
    # 站 1：不装 v=0；站 2：不装 v=0。构造站2两种等价最优不可行（同站只能 0 或 1 盒），
    # 改为跨站并列：站1装 A(0,0) 或不装，到站2后累计均 0，目标相同。
    incs = [0, 0]
    stations = [
        Station(0, 0, [Box("A", 0, 0)]),
        Station(0, 0, []),
    ]
    r = solve(incs, stations)
    # 不装 0 盒严格优于装 1 盒，故唯一
    assert r["objective"]["boxes_installed"] == 0
    assert r["unique"] is True
    print("strict minimum OK")

    # 强制必须装 1 盒：站 1 不装 v=0 但区间 [1,1]，A/B 修正均为 1、插损均为 0
    stations2 = [
        Station(1, 1, [Box("A", 1, 0), Box("B", 1, 0)]),
        Station(1, 1, []),
    ]
    r2 = solve([0, 0], stations2)
    assert r2["objective"]["boxes_installed"] == 1
    assert r2["unique"] is False, r2
    assert len(r2["witnesses"]) == 2
    ids = [w["sequence"][0]["choice"]["id"] for w in r2["witnesses"]]
    assert ids == ["A", "B"], ids
    print("tie top-2 OK")


def test_three_way_tie_keeps_two():
    incs = [0, 0]
    stations = [
        Station(1, 1, [Box("A", 1, 0), Box("B", 1, 0), Box("C", 1, 0)]),
        Station(1, 1, []),
    ]
    r = solve(incs, stations)
    ids = [w["sequence"][0]["choice"]["id"] for w in r["witnesses"]]
    assert ids == ["A", "B"], ids
    print("three-way tie keeps two OK")


def test_full_scale_perf():
    random.seed(7)
    n = 80
    incs = [random.randint(-3000, 3000) for _ in range(n)]
    stations = []
    for _ in range(n):
        boxes = [
            Box(
                id=f"H{j:02d}",
                correction=random.randint(-2000, 2000),
                loss=random.randint(0, 500),
            )
            for j in range(12)
        ]
        lo = random.randint(-8000, 0)
        hi = lo + random.randint(2000, 9000)
        stations.append(Station(lo, hi, boxes))
    t0 = time.perf_counter()
    r = solve(incs, stations)
    dt = time.perf_counter() - t0
    assert r["status"] in ("optimal", "infeasible")
    print(f"full-scale 80x12 solve: {dt*1000:.1f} ms, status={r['status']}")
    if r["status"] == "optimal":
        obj = r["objective"]
        # 校验见证可行性
        for w in r["witnesses"]:
            assert len(w["sequence"]) == n
            cum = 0
            loss = cnt = 0
            for i, item in enumerate(w["sequence"]):
                cum += incs[i]
                if item["choice"]:
                    cum += item["choice"]["correction"]
                    loss += item["choice"]["loss"]
                    cnt += 1
                assert stations[i].lower <= cum <= stations[i].upper
                assert item["cumulative"] == cum
            assert cnt == obj["boxes_installed"]
            assert loss == obj["total_loss"]
            assert abs(cum) == obj["final_abs_residual"]
    print("full-scale witnesses verified OK")


def test_worst_case_density():
    # 增量小、区间宽、修正小：可达值密集，验证状态数远小于 13^80
    n = 80
    incs = [0] * n
    stations = [
        Station(-20000, 20000, [Box(f"B{j}", j - 6, j) for j in range(12)])
        for _ in range(n)
    ]
    t0 = time.perf_counter()
    r = solve(incs, stations)
    dt = time.perf_counter() - t0
    assert r["status"] == "optimal"
    print(f"dense 80x12 solve: {dt*1000:.1f} ms, boxes={r['objective']['boxes_installed']}")


if __name__ == "__main__":
    test_infeasible_location()
    test_first_station_infeasible()
    test_tie_top2()
    test_three_way_tie_keeps_two()
    test_full_scale_perf()
    test_worst_case_density()
    print("ALL EDGE TESTS PASSED")
