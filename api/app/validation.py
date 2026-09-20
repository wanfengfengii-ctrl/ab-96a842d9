"""输入解析与精确校验。

数值以 JSON 数字字面量或字符串给出，统一用 Decimal 读取（禁止
NaN/Infinity），再精确缩放到整数（乘 1000）。任何超过三位小数、
越界或类型错误都被收集为带站点/字段定位的错误。
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from .solver import Box, Station

SCALE = 1000
MIN_V = -20000
MAX_V = 20000
MIN_SEGMENTS = 2
MAX_SEGMENTS = 80
MAX_BOXES = 12

# 允许的小数位数：题目要求“最多三位小数”。
MAX_DIGITS_AFTER_DOT = 3


class ValidationReport(Exception):
    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


def parse_json_decimal(body: bytes) -> Any:
    text = body.decode("utf-8")
    try:
        return json.loads(text, parse_float=Decimal, parse_int=Decimal)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationReport(
            [{"field": "body", "message": f"请求体不是合法 JSON：{exc}"}]
        )


def _quantize(value: Decimal) -> int:
    """把 Decimal 精确乘 1000 转整数；非三位以内小数视为非法。"""
    if not value.is_finite():
        raise InvalidOperation("非有限数值")
    exp = value.as_tuple().exponent
    if isinstance(exp, int) and exp < -MAX_DIGITS_AFTER_DOT:
        raise InvalidOperation("超过三位小数")
    scaled = value * SCALE
    if scaled != scaled.to_integral_value():
        raise InvalidOperation("超过三位小数")
    return int(scaled)


def _coerce_number(raw: Any) -> Decimal:
    """字段允许是 JSON 数值或字符串，但必须是十进制有限数。"""
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):  # bool 是 int 子类，显式排除
        raise InvalidOperation("必须是数值或数字字符串")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            raise InvalidOperation("空字符串")
        return Decimal(s)
    raise InvalidOperation("必须是数值或数字字符串")


def _read_scaled(
    errors: list[dict[str, str]], field: str, raw: Any, *, nonneg: bool = False
) -> int | None:
    try:
        dec = _coerce_number(raw)
        val = _quantize(dec)
    except (InvalidOperation, ValueError):
        errors.append(
            {"field": field, "message": "必须是最多三位小数的十进制数"}
        )
        return None
    if not (MIN_V <= val <= MAX_V):
        errors.append(
            {
                "field": field,
                "message": f"缩放后须落在 [{MIN_V}, {MAX_V}]，当前 {val}",
            }
        )
        return None
    if nonneg and val < 0:
        errors.append({"field": field, "message": "插损必须非负"})
        return None
    return val


def validate_payload(raw: Any) -> tuple[list[int], list[Station]]:
    """校验整个请求，返回 (增量列表, 站点列表)；错误全部收集后一次性抛出。"""
    errors: list[dict[str, str]] = []

    if not isinstance(raw, dict):
        raise ValidationReport(
            [{"field": "body", "message": "请求体必须是 JSON 对象"}]
        )

    segments = raw.get("segments")
    if not isinstance(segments, list):
        raise ValidationReport(
            [{"field": "segments", "message": "segments 必须是数组"}]
        )

    n = len(segments)
    if not (MIN_SEGMENTS <= n <= MAX_SEGMENTS):
        raise ValidationReport(
            [
                {
                    "field": "segments",
                    "message": f"段数必须在 {MIN_SEGMENTS} 至 {MAX_SEGMENTS} 之间，当前 {n}",
                }
            ]
        )

    increments: list[int | None] = []
    for i, seg in enumerate(segments):
        field = f"segments[{i}].increment"
        if not isinstance(seg, dict):
            errors.append({"field": field, "message": "段必须是对象"})
            increments.append(None)
            continue
        increments.append(_read_scaled(errors, field, seg.get("increment")))

    stations_raw = raw.get("stations")
    if not isinstance(stations_raw, list):
        raise ValidationReport(
            [{"field": "stations", "message": "stations 必须是数组"}]
        )
    if len(stations_raw) != n:
        raise ValidationReport(
            [
                {
                    "field": "stations",
                    "message": f"站点数 {len(stations_raw)} 必须等于段数 {n}",
                }
            ]
        )

    stations: list[Station] = []
    for i, st_raw in enumerate(stations_raw):
        sfield = f"stations[{i}]"
        if not isinstance(st_raw, dict):
            errors.append({"field": sfield, "message": "站点必须是对象"})
            stations.append(Station(0, -1, []))  # 占位，继续校验其余站点
            continue

        lo = _read_scaled(errors, f"{sfield}.lower", st_raw.get("lower"))
        hi = _read_scaled(errors, f"{sfield}.upper", st_raw.get("upper"))
        if lo is not None and hi is not None and lo > hi:
            errors.append(
                {
                    "field": f"{sfield}.upper",
                    "message": f"区间下界 {lo} 不能大于上界 {hi}",
                }
            )

        boxes_raw = st_raw.get("boxes", [])
        if not isinstance(boxes_raw, list):
            errors.append(
                {"field": f"{sfield}.boxes", "message": "候选盒必须是数组"}
            )
            boxes_raw = []

        boxes: list[Box] = []
        if len(boxes_raw) > MAX_BOXES:
            errors.append(
                {
                    "field": f"{sfield}.boxes",
                    "message": f"每站候选盒至多 {MAX_BOXES} 个，当前 {len(boxes_raw)}",
                }
            )
            boxes_raw = boxes_raw[:MAX_BOXES]

        seen_ids: set[str] = set()
        for j, b_raw in enumerate(boxes_raw):
            bfield = f"{sfield}.boxes[{j}]"
            if not isinstance(b_raw, dict):
                errors.append({"field": bfield, "message": "候选盒必须是对象"})
                continue
            bid = b_raw.get("id")
            if not isinstance(bid, str) or not bid.strip():
                errors.append(
                    {"field": f"{bfield}.id", "message": "盒编号必须是非空字符串"}
                )
                continue
            if bid in seen_ids:
                errors.append(
                    {"field": f"{bfield}.id", "message": f"盒编号 {bid} 在本站重复"}
                )
                continue
            seen_ids.add(bid)

            corr = _read_scaled(
                errors, f"{bfield}.correction", b_raw.get("correction")
            )
            loss = _read_scaled(
                errors, f"{bfield}.loss", b_raw.get("loss"), nonneg=True
            )
            if corr is not None and loss is not None:
                boxes.append(Box(id=bid, correction=corr, loss=loss))

        if lo is None:
            lo = 0
        if hi is None:
            hi = lo if lo is not None else 0
        stations.append(Station(lower=lo, upper=hi, boxes=boxes))

    if errors:
        raise ValidationReport(errors)

    return [v if v is not None else 0 for v in increments], stations
