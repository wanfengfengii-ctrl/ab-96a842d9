"""精确整数动态规划求解器。

所有物理量在进入本模块前都已按 1000 缩放为整数（毫单位），
全程只做整数运算，杜绝浮点误差。

问题模型
--------
线路有 n 个段（2 <= n <= 80），每个段之后有一个站点：
- 段 i 带来色散增量 inc[i]；
- 到达站点 i 后的累计值 = 上一站累计 + inc[i] + 所选候选盒修正量（不装则为 0）；
- 结果必须落在站点闭区间 [lo[i], hi[i]] 内；
- 每站不装盒，或在至多 12 个候选盒中选一个。

目标（全局、字典序）：
1. 安装盒数最少；
2. 总插损最小；
3. 末站累计值的绝对值最小。

不枚举完整组合：按“站点 × 可达累计整数值”做分层 DP，
每层每个值只保留按 (安装数, 插损) 的非支配前沿，并为每个
前沿状态保留按“各站编号序列”字典序最小的两条见证路径。

top-2 充分性：若某条全局最优完整路径在中间层的前缀，在相同
(v, c, l) 状态下仅排第 3，则前两条更小前缀接上同一后缀会产生
两条更优完整路径，与“第 2 优”矛盾；因此每层每状态保留两条
见证足以在末站还原全局前两份并列见证。
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass

NO_BOX = 0  # 决策码：本站不装盒（在每站编号序中排在最前）


@dataclass
class Box:
    id: str
    correction: int  # 缩放后的修正量
    loss: int        # 缩放后的非负插损


@dataclass
class Station:
    lower: int
    upper: int
    boxes: list[Box]

    def decision_order(self) -> list[int]:
        """返回候选盒下标按编号（id）升序的排列。

        决策码 0 固定表示不装盒；决策码 k(>=1) 对应本排列的第 k-1 个盒。
        这样见证路径按决策码比较，正好等于按“各站编号序列”字典序比较。
        """
        return sorted(range(len(self.boxes)), key=lambda j: self.boxes[j].id)


@dataclass
class Layer:
    """某一站处理完后的 DP 层。

    状态主存（并行数组，按下标一一对应，同一 v 的状态按 c 升序连续存放）：
      vv: 累计值, cc: 安装数, ll: 总插损, aa/bb: 两条见证的末节点 id
    index: v -> (起始下标, 个数)
    见证节点（每个节点是一条到本站为止的编号序列，节点 id 即其字典序名次）：
      np: 前驱节点 id（上一层，上一层同样 id==名次）, dd: 本站决策码
    """

    vv: array
    cc: array
    ll: array
    aa: array
    bb: array
    index: dict[int, tuple[int, int]]
    np: array
    dd: array


def _root_layer() -> Layer:
    """第 0 层：未经过任何段，累计值为 0，只有空序列根节点。"""
    return Layer(
        vv=array("i", [0]),
        cc=array("b", [0]),
        ll=array("i", [0]),
        aa=array("i", [0]),
        bb=array("i", [0]),
        index={0: (0, 1)},
        np=array("i", [-1]),
        dd=array("b", [0]),
    )


def _advance(prev: Layer, inc: int, station: Station) -> Layer | None:
    """从第 i-1 层推进到第 i 层；无可达状态时返回 None。"""
    lo, hi = station.lower, station.upper
    order = station.decision_order()
    # 决策码 k -> (修正量, 插损)；决策码 0 表示不装盒。
    corr = [0] + [station.boxes[j].correction for j in order]
    loss = [0] + [station.boxes[j].loss for j in order]

    # 候选聚合：键 (目标累计值 v, 安装数 c)。
    # best[key] = 该键下最小插损；win[key] = 取得最小插损的两条最小编号序列，
    # 每条序列以 (前驱节点在 prev 层的名次, 本站决策码) 表示，可 O(1) 比较。
    best: dict[tuple[int, int], int] = {}
    win: dict[tuple[int, int], tuple[tuple[int, int], tuple[int, int]]] = {}

    pvv, pcc, pll, paa, pbb = prev.vv, prev.cc, prev.ll, prev.aa, prev.bb
    n_entries = len(pvv)
    for e in range(n_entries):
        u = pvv[e]
        c0 = pcc[e]
        l0 = pll[e]
        # 上一层节点已按字典序物理压缩，节点 id 即名次，可直接比较。
        s1 = (paa[e], NO_BOX)
        s2 = (pbb[e], NO_BOX)
        base = u + inc

        # 决策 0：不装盒
        v = base
        if lo <= v <= hi:
            key = (v, c0)
            cur = best.get(key)
            if cur is None or l0 <= cur:
                if cur is None or l0 < cur:
                    best[key] = l0
                    win[key] = (s1, s2)
                else:
                    w = win[key]
                    win[key] = _top2(w[0], w[1], s1, s2)

        # 决策 k：选编号序中的第 k-1 个盒
        for k in range(1, len(corr)):
            v = base + corr[k]
            if not (lo <= v <= hi):
                continue
            key = (v, c0 + 1)
            l = l0 + loss[k]
            t1 = (s1[0], k)
            t2 = (s2[0], k)
            cur = best.get(key)
            if cur is None or l <= cur:
                if cur is None or l < cur:
                    best[key] = l
                    win[key] = (t1, t2)
                else:
                    w = win[key]
                    win[key] = _top2(w[0], w[1], t1, t2)

    if not best:
        return None

    # 按目标值 v 分组，组内按安装数 c 升序做支配剪枝：
    # c 更大且插损不更小的状态被严格支配，删除。
    groups: dict[int, list[tuple[int, int, tuple, tuple]]] = {}
    for (v, c), l in best.items():
        w = win[(v, c)]
        groups.setdefault(v, []).append((c, l, w[0], w[1]))

    vv = array("i")
    cc = array("b")
    ll = array("i")
    aa = array("i")
    bb = array("i")
    index: dict[int, tuple[int, int]] = {}

    np = array("i")
    dd = array("b")
    node_id: dict[tuple[int, int], int] = {}

    def get_node(rprev: int, d: int) -> int:
        nk = (rprev, d)
        nid = node_id.get(nk)
        if nid is None:
            nid = len(np)
            node_id[nk] = nid
            np.append(rprev)
            dd.append(d)
        return nid

    for v, items in groups.items():
        items.sort(key=lambda t: t[0])
        start = len(vv)
        min_l: int | None = None
        for c, l, w1, w2 in items:
            if min_l is not None and l >= min_l:
                continue  # 被安装数更少、插损不更大的状态支配
            min_l = l
            n1 = get_node(w1[0], w1[1])
            n2 = get_node(w2[0], w2[1])
            vv.append(v)
            cc.append(c)
            ll.append(l)
            aa.append(n1)
            bb.append(n2)
        count = len(vv) - start
        if count:
            index[v] = (start, count)

    if not vv:
        return None

    # 节点按 (前驱名次, 本站决策码) 全局字典序物理压缩：
    # 排序后下标即节点 id（== 名次），再重映射全部见证引用，
    # 使下一层可直接用节点 id 做 O(1) 字典序比较与回溯。
    m = len(np)
    order_nodes = sorted(range(m), key=lambda nid: (np[nid], dd[nid]))
    remap = [0] * m
    np2 = array("i")
    dd2 = array("b")
    for rank, nid in enumerate(order_nodes):
        remap[nid] = rank
        np2.append(np[nid])
        dd2.append(dd[nid])
    for e in range(len(aa)):
        aa[e] = remap[aa[e]]
        bb[e] = remap[bb[e]]

    return Layer(vv, cc, ll, aa, bb, index, np2, dd2)


def _top2(a, b, c, d):
    """四个 (前驱名次, 决策码) 中取最小的两个（两两可能相同，去重）。"""
    uniq = {a, b, c, d}
    s = sorted(uniq)
    if len(s) == 1:
        return s[0], s[0]
    return s[0], s[1]


def solve(increments: list[int], stations: list[Station]) -> dict:
    """运行精确整数 DP，返回可直接序列化的结果字典。"""
    n = len(increments)

    layer = _root_layer()
    layers: list[Layer] = [layer]
    infeasible_station: int | None = None

    for i in range(n):
        layer = _advance(layer, increments[i], stations[i])
        if layer is None:
            infeasible_station = i + 1
            break
        layers.append(layer)

    if infeasible_station is not None:
        return {
            "status": "infeasible",
            "infeasible_station": infeasible_station,
            "objective": None,
            "witnesses": [],
        }

    # 末站跨所有可达值找 (安装数, 总插损, |末站累计值|) 的全局最优。
    final = layers[-1]
    best_key: tuple[int, int, int] | None = None
    best_nodes: list[int] = []
    for e in range(len(final.vv)):
        v = final.vv[e]
        key = (final.cc[e], final.ll[e], abs(v))
        if best_key is None or key < best_key:
            best_key = key
            best_nodes = [final.aa[e], final.bb[e]]
        elif key == best_key:
            best_nodes.append(final.aa[e])
            best_nodes.append(final.bb[e])

    # 节点 id 已按完整编号序列字典序物理排序，id 大小即序列字典序。
    ranked = sorted(set(best_nodes))
    witnesses = [_decode(layers, nid, increments, stations) for nid in ranked[:2]]

    boxes_count, total_loss, final_abs = best_key
    return {
        "status": "optimal",
        "infeasible_station": None,
        "objective": {
            "boxes_installed": boxes_count,
            "total_loss": total_loss,
            "final_abs_residual": final_abs,
        },
        "witnesses": witnesses,
        "unique": len(ranked) == 1,
    }


def _decode(
    layers: list[Layer],
    leaf: int,
    increments: list[int],
    stations: list[Station],
) -> dict:
    """沿见证节点逐层回溯，还原每站决策与站后累计值。"""
    n = len(increments)
    decisions = [0] * n
    node = leaf
    for i in range(n, 0, -1):
        lyr = layers[i]
        decisions[i - 1] = lyr.dd[node]
        node = lyr.np[node]

    sequence = []
    cumulative = 0
    for i in range(n):
        st = stations[i]
        cumulative += increments[i]
        d = decisions[i]
        if d == NO_BOX:
            chosen = None
        else:
            box = st.boxes[st.decision_order()[d - 1]]
            cumulative += box.correction
            chosen = {
                "id": box.id,
                "correction": box.correction,
                "loss": box.loss,
            }
        sequence.append(
            {
                "station": i + 1,
                "choice": chosen,
                "cumulative": cumulative,
            }
        )

    return {"sequence": sequence}
