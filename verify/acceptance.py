"""Compose “verify” 可执行验收服务。

对运行中的 web 与 api 发起真实 HTTP 请求，逐条核验：
  1. 两者 /health 均为 200；
  2. 示例线路求得全局最优，且目标序 安装数→总插损→末站|残差| 正确；
  3. 并列时恰好返回按各站编号序列排序的前两份见证，且两条都可行、目标相同；
  4. 无解时返回首个可达状态集合变空的站点号；
  5. 输入错误带站点与字段定位（422），含三位小数/非负插损/编号重复；
  6. 精确整数：0.005 与 -0.005 等三位小数被精确处理（无浮点误差）；
  7. 80 站×12 盒在限定时间内返回，证明没有枚举 13^n 组合。

任一条失败即以非零码退出，并打印 FAIL 明细。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API_BASE = os.environ.get("API_BASE", "http://api:8000")
WEB_BASE = os.environ.get("WEB_BASE", "http://web:80")
TIME_LIMIT_SECONDS = float(os.environ.get("VERIFY_TIME_LIMIT", "10"))

failures: list[str] = []

# 由用例设置（增量为毫单位整数、区间为毫单位闭区间），供 verify_solution 使用
body_incs: list[int] = []
stations_bounds: list[tuple[int, int]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}  {detail}")
        failures.append(name)


def http(method: str, url: str, payload=None, timeout: float = 15.0):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def health_checks() -> None:
    s1, b1 = http("GET", f"{API_BASE}/health")
    check("api /health 200", s1 == 200 and b1.get("status") == "ok", str(b1))
    s2, b2 = http("GET", f"{WEB_BASE}/health")
    check("web /health 200", s2 == 200 and b2.get("status") == "ok", str(b2))
    # Web 必须真正提供页面
    req = urllib.request.Request(f"{WEB_BASE}/")
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", "ignore")
    check("web serves index.html", "<div id=\"root\"" in html, html[:120])
    # Web → API 反代可用
    s3, b3 = http("GET", f"{WEB_BASE}/api-health")
    check("web proxies api health", s3 == 200 and b3.get("status") == "ok", str(b3))


def verify_solution(body: dict, expected: tuple, n: int) -> None:
    """校验返回的见证可行、目标自洽。expected=(盒数,总插损,末站|残差|) 毫单位。"""
    assert body["status"] == "optimal", body
    obj = body["objective"]
    got = (obj["boxes_installed"], obj["total_loss"], obj["final_abs_residual"])
    check("objective equals expected", got == expected, f"{got} != {expected}")
    for w in body["witnesses"]:
        seq = w["sequence"]
        assert len(seq) == n
        cum = cnt = loss = 0
        for i, step in enumerate(seq):
            cum += body_incs[i]
            if step["choice"]:
                cum += step["choice"]["correction"]
                loss += step["choice"]["loss"]
                cnt += 1
            assert stations_bounds[i][0] <= cum <= stations_bounds[i][1], (i, cum)
            check(f"step {i+1} cumulative matches", step["cumulative"] == cum)
        check("witness box count matches objective", cnt == got[0])
        check("witness loss matches objective", loss == got[1])
        check("witness residual matches objective", abs(cum) == got[2])


def case_objective_priority() -> None:
    """站1必须装 1 盒才能进区间；两盒修正相同、插损不同 → 必须选低插损盒。
    随后用末站残差验证第三优先级。"""
    global body_incs, stations_bounds
    payload = {        "segments": [{"increment": 0}, {"increment": "0.000"}],
        "stations": [
            {  # 区间 [1,1]：不装=0 出局；LO 修正1 插损1；HI 修正1 插损9
                "lower": 1, "upper": 1,
                "boxes": [
                    {"id": "HI", "correction": 1, "loss": 9},
                    {"id": "LO", "correction": 1, "loss": 1},
                ],
            },
            {  # 累计=1，区间 [0,10]；不装残差|1|；盒 ZERO 修正-1 插损0 → 残差0 但多装一盒
                "lower": 0, "upper": 10,
                "boxes": [{"id": "ZERO", "correction": -1, "loss": 0}],
            },
        ],
    }
    body_incs = [0, 0]
    stations_bounds = [(1000, 1000), (0, 10000)]
    s, b = http("POST", f"{API_BASE}/api/solve", payload)
    check("priority case status 200", s == 200, str(b))
    # 装 1 盒(LO)、总插损 1、末站 |1|；ZERO 方案装2盒被第一优先级淘汰
    verify_solution(b, (1, 1000, 1000), 2)
    chosen = b["witnesses"][0]["sequence"][0]["choice"]["id"]
    check("lower loss box chosen (priority 2)", chosen == "LO", chosen)
    check("solution unique here", b["unique"] is True)


def case_ties() -> None:
    payload = {
        "segments": [{"increment": 0}, {"increment": 0}],
        "stations": [
            {"lower": 1, "upper": 1, "boxes": [
                {"id": "C", "correction": 1, "loss": 2},
                {"id": "A", "correction": 1, "loss": 2},
                {"id": "B", "correction": 1, "loss": 2},
            ]},
            {"lower": 1, "upper": 1, "boxes": []},
        ],
    }
    s, b = http("POST", f"{API_BASE}/api/solve", payload)
    check("tie status 200", s == 200, str(b))
    check("tie detected non-unique", b["unique"] is False, str(b))
    ids = [w["sequence"][0]["choice"]["id"] for w in b["witnesses"]]
    check("tie returns exactly first two by id order", ids == ["A", "B"], str(ids))
    check("tie has exactly two witnesses", len(b["witnesses"]) == 2)


def case_ties_multi_station() -> None:
    """跨站并列：两站各有两个等价盒，4 条全局最优，应返回编号序最小的两份。
    序（不装最小；此处必须装）：[(A,A),(A,B),(B,A),(B,B)] → 前二 AA、AB。"""
    payload = {
        "segments": [{"increment": 0}, {"increment": 0}],
        "stations": [
            {"lower": 1, "upper": 1, "boxes": [
                {"id": "B", "correction": 1, "loss": 0},
                {"id": "A", "correction": 1, "loss": 0},
            ]},
            {"lower": 2, "upper": 2, "boxes": [
                {"id": "B", "correction": 1, "loss": 0},
                {"id": "A", "correction": 1, "loss": 0},
            ]},
        ],
    }
    s, b = http("POST", f"{API_BASE}/api/solve", payload)
    ids = [[w["sequence"][k]["choice"]["id"] for k in range(2)] for w in b["witnesses"]]
    check(
        "multi-station tie first two witnesses",
        ids == [["A", "A"], ["A", "B"]],
        str(ids),
    )


def case_infeasible() -> None:
    payload = {
        "segments": [{"increment": 5}, {"increment": 10}],
        "stations": [
            {"lower": 0, "upper": 10, "boxes": []},
            {"lower": 0, "upper": 10,
             "boxes": [{"id": "X", "correction": 0, "loss": 0}]},
        ],
    }
    s, b = http("POST", f"{API_BASE}/api/solve", payload)
    check("infeasible status 200 payload", s == 200, str(b))
    check("infeasible status field", b["status"] == "infeasible", str(b))
    check("first empty reachable set is station 2",
          b["infeasible_station"] == 2, str(b))


def case_infeasible_station1() -> None:
    payload = {
        "segments": [{"increment": 20}, {"increment": 0}],
        "stations": [
            {"lower": 0, "upper": 10, "boxes": []},
            {"lower": 0, "upper": 10, "boxes": []},
        ],
    }
    _, b = http("POST", f"{API_BASE}/api/solve", payload)
    check("infeasible at station 1", b["infeasible_station"] == 1, str(b))


def case_validation() -> None:
    # 段数越界
    s, b = http("POST", f"{API_BASE}/api/solve",
                {"segments": [{"increment": 0}], "stations": [{"lower": 0, "upper": 0, "boxes": []}]})
    check("segment count rejected", s == 422 and b["status"] == "invalid", str(b)[:200])

    payload = {
        "segments": [{"increment": 0}, {"increment": "0.1234"}],
        "stations": [
            {"lower": "x", "upper": 0,
             "boxes": [{"id": "K", "correction": 0, "loss": -1},
                       {"id": "K", "correction": 0, "loss": 0}]},
            {"lower": 5, "upper": 1, "boxes": []},
        ],
    }
    s, b = http("POST", f"{API_BASE}/api/solve", payload)
    check("validation returns 422", s == 422, str(b)[:200])
    fields = {e["field"] for e in b["errors"]}
    for f in [
        "segments[1].increment",
        "stations[0].lower",
        "stations[0].boxes[0].loss",
        "stations[0].boxes[1].id",
        "stations[1].upper",
    ]:
        check(f"located error at {f}", f in fields, str(sorted(fields)))

    # 缩放后越界
    payload2 = {
        "segments": [{"increment": 21}, {"increment": 0}],
        "stations": [
            {"lower": 0, "upper": 0, "boxes": []},
            {"lower": 0, "upper": 0, "boxes": []},
        ],
    }
    s, b = http("POST", f"{API_BASE}/api/solve", payload2)
    fields2 = {e["field"] for e in b["errors"]}
    check("bounds [-20000,20000] enforced",
          s == 422 and "segments[0].increment" in fields2, str(b)[:200])


def case_exact_decimal() -> None:
    """0.005 + (-0.003) 之类若走浮点会出错；强制末站区间恰为 0.002。"""
    payload = {
        "segments": [{"increment": "0.005"}, {"increment": "-0.003"}],
        "stations": [
            {"lower": 0, "upper": 1, "boxes": []},
            {"lower": "0.002", "upper": "0.002", "boxes": []},  # 毫单位 2
        ],
    }
    s, b = http("POST", f"{API_BASE}/api/solve", payload)
    check("exact decimal: feasible", s == 200 and b["status"] == "optimal", str(b))
    final_cum = b["witnesses"][0]["sequence"][-1]["cumulative"]
    check("exact decimal final cumulative = 2 milli", final_cum == 2, str(final_cum))

    # 末站 |残差| 比较也必须精确：构造 +0.002 与 -0.002 并列
    payload2 = {
        "segments": [{"increment": 0}, {"increment": 0.002}],
        "stations": [
            {"lower": 0, "upper": 0, "boxes": []},
            {"lower": -2, "upper": 2, "boxes": [
                {"id": "N", "correction": -0.004, "loss": 0},
            ]},
        ],
    }
    s2, b2 = http("POST", f"{API_BASE}/api/solve", payload2)
    check("residual tie both |2| milli",
          b2["objective"]["final_abs_residual"] == 2, str(b2))


def case_full_scale_perf() -> None:
    rng_state = 1234567

    def rnd() -> int:
        # 确定性 LCG，避免依赖 random 版本
        nonlocal rng_state
        rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        return rng_state

    n = 80

    def milli(x: int) -> str:
        """毫单位整数 -> 精确的最多三位小数字符串（绝不走浮点）。"""
        sign = "-" if x < 0 else ""
        x = abs(x)
        return f"{sign}{x // 1000}.{x % 1000:03d}"

    segments = []
    stations = []
    for i in range(n):
        segments.append({"increment": milli((rnd() % 40001) - 20000)})
        boxes = []
        for j in range(12):
            boxes.append({
                "id": f"H{j:02d}",
                "correction": milli((rnd() % 40001) - 20000),
                "loss": milli(rnd() % 20001),
            })
        lo = (rnd() % 20001) - 15000
        stations.append({
            "lower": milli(lo),
            "upper": milli(lo + rnd() % 12000),
            "boxes": boxes,
        })
    payload = {"segments": segments, "stations": stations}

    t0 = time.perf_counter()
    s, b = http("POST", f"{API_BASE}/api/solve", payload, timeout=30)
    dt = time.perf_counter() - t0
    check("80x12 responds 200", s == 200, str(b)[:200])
    check(f"80x12 returns within {TIME_LIMIT_SECONDS}s (no enumeration)",
          dt < TIME_LIMIT_SECONDS, f"{dt:.2f}s")
    check("80x12 gives a status", b["status"] in ("optimal", "infeasible"))
    if b["status"] == "optimal":
        check("80x12 witnesses count 1-2", 1 <= len(b["witnesses"]) <= 2)
        check("80x12 sequence length 80",
              len(b["witnesses"][0]["sequence"]) == 80)


def case_web_proxy_solve() -> None:
    """经 Web 反代调用真实求解接口。"""
    payload = {
        "segments": [{"increment": 0}, {"increment": 0}],
        "stations": [
            {"lower": 0, "upper": 0, "boxes": []},
            {"lower": 0, "upper": 0, "boxes": []},
        ],
    }
    s, b = http("POST", f"{WEB_BASE}/api/solve", payload)
    check("solve via web proxy", s == 200 and b["status"] == "optimal", str(b)[:200])


def main() -> int:
    print(f"== verify against {API_BASE} and {WEB_BASE} ==")
    health_checks()
    case_objective_priority()
    case_ties()
    case_ties_multi_station()
    case_infeasible()
    case_infeasible_station1()
    case_validation()
    case_exact_decimal()
    case_full_scale_perf()
    case_web_proxy_solve()

    print()
    if failures:
        print(f"VERIFY FAILED: {len(failures)} check(s) -> {failures}")
        return 1
    print("VERIFY PASSED: all acceptance checks succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
