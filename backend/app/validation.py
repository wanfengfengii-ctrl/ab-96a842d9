"""Input parsing and exact-integer validation for the planner API."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

SCALE = 1000
MIN_SCALED = -20000
MAX_SCALED = 20000
MIN_STATIONS = 2
MAX_STATIONS = 80
MAX_BOXES = 12
THOUSANDTHS = Decimal("0.001")


@dataclass(frozen=True)
class CandidateBox:
    id: int
    correction_int: int
    loss_int: int


@dataclass(frozen=True)
class Station:
    increment_int: int
    lower_int: int
    upper_int: int
    boxes: list[CandidateBox] = field(default_factory=list)


@dataclass(frozen=True)
class LineInput:
    stations: list[Station]


@dataclass(frozen=True)
class ValidationErrorRecord:
    station: int | None          # 1-based station index, None = top level
    field: str                   # dotted field path, e.g. "boxes[2].loss"
    message: str


def _parse_milli(
    value: Any,
    errors: list[ValidationErrorRecord],
    station_idx: int | None,
    path: str,
    *,
    allow_negative: bool = True,
) -> int | None:
    """Parse a number/string with at most 3 decimals into milli-units.

    Values must lie in [-20000, 20000] after scaling.  Strings are accepted
    so users can paste exact decimals ("1.235"); everything goes through
    Decimal, never float, so comparisons stay exact.
    """

    if isinstance(value, bool) or not isinstance(value, (int, str, float)):
        errors.append(
            ValidationErrorRecord(
                station_idx,
                path,
                "必须是数字（至多三位小数）",
            )
        )
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        errors.append(
            ValidationErrorRecord(station_idx, path, "不是合法数字")
        )
        return None
    if not d.is_finite():
        errors.append(
            ValidationErrorRecord(station_idx, path, "数值必须有限")
        )
        return None
    # At most three decimal places.
    if d.as_tuple().exponent < -3:
        errors.append(
            ValidationErrorRecord(
                station_idx, path, "小数位不能超过三位"
            )
        )
        return None
    milli = int(d * 1000)
    if milli < MIN_SCALED or milli > MAX_SCALED:
        errors.append(
            ValidationErrorRecord(
                station_idx,
                path,
                f"缩放后必须落在 [{MIN_SCALED}, {MAX_SCALED}] 之内",
            )
        )
        return None
    if not allow_negative and milli < 0:
        errors.append(
            ValidationErrorRecord(station_idx, path, "不能为负数")
        )
        return None
    return milli


def parse_line(payload: Any) -> LineInput:
    """Parse strictly (used after validation has reported all errors)."""

    errors: list[ValidationErrorRecord] = []
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    raw_stations = payload.get("stations")
    if not isinstance(raw_stations, list):
        raise ValueError("stations must be a list")

    stations: list[Station] = []
    for i, raw_st in enumerate(raw_stations):
        if not isinstance(raw_st, dict):
            raise ValueError(f"station {i + 1} must be an object")
        inc = _parse_milli(
            raw_st.get("increment", 0), errors, i + 1, "increment"
        )
        lo = _parse_milli(raw_st.get("lower", 0), errors, i + 1, "lower")
        hi = _parse_milli(raw_st.get("upper", 0), errors, i + 1, "upper")
        boxes_raw = raw_st.get("boxes", [])
        boxes: list[CandidateBox] = []
        if not isinstance(boxes_raw, list):
            errors.append(
                ValidationErrorRecord(i + 1, "boxes", "必须是数组")
            )
            boxes_raw = []
        for b_i, raw_box in enumerate(boxes_raw):
            if not isinstance(raw_box, dict):
                errors.append(
                    ValidationErrorRecord(
                        i + 1, f"boxes[{b_i}]", "候选盒必须是对象"
                    )
                )
                continue
            bid = raw_box.get("id")
            if (
                not isinstance(bid, int)
                or isinstance(bid, bool)
                or bid < 1
            ):
                errors.append(
                    ValidationErrorRecord(
                        i + 1, f"boxes[{b_i}].id", "编号必须是正整数"
                    )
                )
                continue
            corr = _parse_milli(
                raw_box.get("correction", 0),
                errors,
                i + 1,
                f"boxes[{b_i}].correction",
            )
            loss = _parse_milli(
                raw_box.get("loss", 0),
                errors,
                i + 1,
                f"boxes[{b_i}].loss",
                allow_negative=False,
            )
            if corr is not None and loss is not None:
                boxes.append(CandidateBox(bid, corr, loss))
        if inc is not None and lo is not None and hi is not None:
            stations.append(Station(inc, lo, hi, boxes))
    if errors:
        raise ValueError("validation failed")
    return LineInput(stations)


def validate_line(payload: Any) -> list[ValidationErrorRecord]:
    """Full structural validation. Returns all located errors at once."""

    errors: list[ValidationErrorRecord] = []

    if not isinstance(payload, dict):
        return [
            ValidationErrorRecord(None, "$", "请求体必须是 JSON 对象")
        ]

    if "stations" not in payload:
        errors.append(
            ValidationErrorRecord(None, "stations", "缺少 stations 字段")
        )
        return errors

    raw_stations = payload["stations"]
    if not isinstance(raw_stations, list):
        errors.append(
            ValidationErrorRecord(None, "stations", "必须是数组")
        )
        return errors

    n = len(raw_stations)
    if n < MIN_STATIONS:
        errors.append(
            ValidationErrorRecord(
                None, "stations", f"线路段数至少为 {MIN_STATIONS}"
            )
        )
    if n > MAX_STATIONS:
        errors.append(
            ValidationErrorRecord(
                None, "stations", f"线路段数至多为 {MAX_STATIONS}"
            )
        )

    for i, raw_st in enumerate(raw_stations):
        station_no = i + 1
        if not isinstance(raw_st, dict):
            errors.append(
                ValidationErrorRecord(
                    station_no, "$", "站点必须是 JSON 对象"
                )
            )
            continue

        for fname in ("increment", "lower", "upper"):
            if fname in raw_st:
                _parse_milli(
                    raw_st[fname], errors, station_no, fname
                )
            # missing is fine: default 0

        if "lower" in raw_st and "upper" in raw_st:
            lo = _parse_milli(
                raw_st["lower"], [], station_no, "lower"
            )
            hi = _parse_milli(
                raw_st["upper"], [], station_no, "upper"
            )
            if lo is not None and hi is not None and lo > hi:
                errors.append(
                    ValidationErrorRecord(
                        station_no, "lower", "下界不能大于上界"
                    )
                )

        boxes_raw = raw_st.get("boxes", [])
        if not isinstance(boxes_raw, list):
            errors.append(
                ValidationErrorRecord(station_no, "boxes", "必须是数组")
            )
            continue
        if len(boxes_raw) > MAX_BOXES:
            errors.append(
                ValidationErrorRecord(
                    station_no,
                    "boxes",
                    f"每站候选盒至多 {MAX_BOXES} 个",
                )
            )
        seen_ids: set[int] = set()
        for b_i, raw_box in enumerate(boxes_raw[:MAX_BOXES]):
            path_box = f"boxes[{b_i}]"
            if not isinstance(raw_box, dict):
                errors.append(
                    ValidationErrorRecord(
                        station_no, path_box, "候选盒必须是对象"
                    )
                )
                continue
            bid = raw_box.get("id")
            id_path = f"{path_box}.id"
            if bid is None:
                errors.append(
                    ValidationErrorRecord(
                        station_no, id_path, "缺少唯一编号"
                    )
                )
            elif not isinstance(bid, int) or isinstance(bid, bool):
                errors.append(
                    ValidationErrorRecord(
                        station_no, id_path, "编号必须是整数"
                    )
                )
            elif bid < 1:
                errors.append(
                    ValidationErrorRecord(
                        station_no,
                        id_path,
                        "编号必须是正整数（从 1 开始）",
                    )
                )
            elif bid in seen_ids:
                errors.append(
                    ValidationErrorRecord(
                        station_no,
                        id_path,
                        f"编号 {bid} 在本站重复",
                    )
                )
            else:
                seen_ids.add(bid)

            if "correction" in raw_box:
                _parse_milli(
                    raw_box["correction"],
                    errors,
                    station_no,
                    f"{path_box}.correction",
                )
            if "loss" in raw_box:
                _parse_milli(
                    raw_box["loss"],
                    errors,
                    station_no,
                    f"{path_box}.loss",
                    allow_negative=False,
                )
            else:
                # loss defaults to zero but record the default silently.
                pass

    return errors
