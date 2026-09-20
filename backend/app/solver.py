"""Exact-integer dispersion compensation planner.

All user supplied decimals (increments, interval bounds, corrections,
insertion losses; at most three places) are scaled by 1000 into integers, so
every comparison is exact integer arithmetic.

A *k = 2 multi-label* layered dynamic program finds the global optimum.
At every station and reachable cumulative value, the two best labels survive
under the total order

    (installed boxes, total insertion loss, box-number sequence)

with the sequence compared lexicographically (``null`` < box id).  Sequence
comparison is implemented by inductive ranks: after pruning a layer, its
survivors (at most two per value, hence O(range) labels) are sorted once and
assigned dense ranks, so comparing two child sequences is an integer
comparison of ``(parent rank, this station's choice)``.  Labels that die at a
value can never parent a global top-2 solution -- two strictly better labels
sharing the same station and value dominate them under every feasible
suffix -- so two labels per value are exactly enough to recover the two
witness sequences demanded on a tie.

Worst case work is O(N * V * B * log(V)) with N <= 80 stations, V <= 40001
scaled values and B <= 12 boxes; combinations are never enumerated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .validation import CandidateBox, LineInput, Station

# Choice code meaning "no box installed at this station".  It sorts before
# every real (positive) box id, matching null < number in the JSON witnesses.
NO_BOX = -1


@dataclass(slots=True)
class Label:
    count: int           # boxes installed up to and including this station
    loss: int            # total insertion loss, scaled (milli-dB)
    parent_rank: int     # rank of ``prev`` among the previous layer survivors
    choice: int          # box id chosen here, or NO_BOX
    prev: Optional["Label"]
    rank: int = 0        # rank of this label among current layer survivors

    def seq_key(self) -> tuple[int, int]:
        """Lexicographic key of the full box-number sequence."""
        return (self.parent_rank, self.choice)

    def obj_key(self) -> tuple[int, int, int, int]:
        return (self.count, self.loss, self.parent_rank, self.choice)


def _merge(
    bucket: dict[int, list[Label]],
    cand: tuple[int, int, int, int, Label],
    value: int,
) -> None:
    """Keep the two best labels (objective then sequence) per value.

    ``cand`` is (count, loss, parent_rank, choice, parent); a Label object
    is allocated only when the candidate survives, keeping object churn low
    on dense layers (millions of candidates, O(range) survivors)."""

    count, loss, parent_rank, choice, parent = cand
    key = (count, loss, parent_rank, choice)
    pair = bucket.get(value)
    if pair is None:
        bucket[value] = [
            Label(count, loss, parent_rank, choice, parent)
        ]
        return
    inserted = False
    for k, existing in enumerate(pair):
        if key < existing.obj_key():
            pair.insert(
                k,
                Label(count, loss, parent_rank, choice, parent),
            )
            inserted = True
            break
    if not inserted and len(pair) < 2:
        pair.append(Label(count, loss, parent_rank, choice, parent))
    if len(pair) > 2:
        del pair[2:]


def _assign_ranks(state: dict[int, list[Label]]) -> None:
    """Assign dense lexicographic ranks to all survivors of one layer.

    Ranks are written onto the labels in place.  A label's own rank is only
    consumed by the *next* layer, so mutating it after the layer has been
    fully pruned is safe."""

    survivors: list[Label] = [lab for pair in state.values() for lab in pair]
    survivors.sort(key=Label.seq_key)
    for rank, lab in enumerate(survivors):
        lab.rank = rank


def _sequence(label: Label, n: int) -> list[Optional[int]]:
    out: list[Optional[int]] = []
    cur: Optional[Label] = label
    while cur is not None and cur.prev is not None:
        out.append(cur.choice if cur.choice != NO_BOX else None)
        cur = cur.prev
    out.reverse()
    assert len(out) == n
    return out


def solve(line: LineInput) -> dict:
    stations: list[Station] = line.stations
    n = len(stations)

    # Station-0 sentinel: empty prefix, cumulative value 0.
    sentinel = Label(0, 0, 0, NO_BOX, None, rank=0)
    state: dict[int, list[Label]] = {0: [sentinel]}

    for j, st in enumerate(stations):
        delta = st.increment_int
        lo, hi = st.lower_int, st.upper_int
        boxes: list[CandidateBox] = st.boxes

        nxt: dict[int, list[Label]] = {}

        for value, pair in state.items():
            base = value + delta
            for parent in pair:
                # Choice: install nothing.
                if lo <= base <= hi:
                    _merge(
                        nxt,
                        (
                            parent.count,
                            parent.loss,
                            parent.rank,
                            NO_BOX,
                            parent,
                        ),
                        base,
                    )
                # Choice: install exactly one candidate box.
                for cand in boxes:
                    nv = base + cand.correction_int
                    if lo <= nv <= hi:
                        _merge(
                            nxt,
                            (
                                parent.count + 1,
                                parent.loss + cand.loss_int,
                                parent.rank,
                                cand.id,
                                parent,
                            ),
                            nv,
                        )

        if not nxt:
            return {
                "status": "infeasible",
                "failed_station": j + 1,
                "reachable_count": 0,
                "message": (
                    f"第 {j + 1} 站后不存在任何满足安全区间的可达状态，"
                    "全局无合法方案"
                ),
            }

        # Prune first (only survivors can matter later), then rank them.
        _assign_ranks(nxt)
        state = nxt

    # Last station: residual participates only in the terminal ranking.
    terminal: list[tuple[int, Label]] = []
    for value, pair in state.items():
        for lab in pair:
            terminal.append((abs(value), lab))
    terminal.sort(
        key=lambda item: (
            item[1].count,
            item[1].loss,
            item[0],
            item[1].rank,
        )
    )

    best_residual, best = terminal[0]
    best_obj = (best.count, best.loss, best_residual)
    winners: list[Label] = []
    for residual, lab in terminal:
        if (lab.count, lab.loss, residual) != best_obj:
            break
        winners.append(lab)
        if len(winners) == 2:
            break

    witnesses = [_sequence(lab, n) for lab in winners]

    return {
        "status": "optimal",
        "stations": [
            {
                "station": i + 1,
                "installed": box_id is not None,
                "box_id": box_id,
            }
            for i, box_id in enumerate(witnesses[0])
        ],
        "witnesses": witnesses,
        "summary": {
            "installed_count": best.count,
            "total_insertion_loss_milli_db": best.loss,
            "final_abs_residual_milli": best_residual,
            "tie": len(witnesses) > 1,
        },
    }


def solve_payload(payload: object) -> dict:
    """Validate, then solve an externally supplied JSON payload."""

    from .validation import validate_line, parse_line

    errors = validate_line(payload)
    if errors:
        raise ValueError(errors)
    return solve(parse_line(payload))
