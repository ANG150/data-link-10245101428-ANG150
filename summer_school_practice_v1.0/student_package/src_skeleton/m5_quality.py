from __future__ import annotations

from typing import Any


BATCH_TIME = 1710000120


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return False
    return str(value).strip().lower() in ("true", "1", "yes")


def check_record(record: dict[str, Any], batch_time: int = BATCH_TIME) -> list[dict[str, Any]]:
    """检查位置缺失(R1)、时间延迟(R2)和航向越界(R4)。"""
    alerts: list[dict[str, Any]] = []
    target_id = record.get("target_id")
    lat = _to_float(record.get("lat"))
    lon = _to_float(record.get("lon"))
    heading = _to_float(record.get("heading"))
    record_time = _to_int(record.get("timestamp") or record.get("latest_time"))

    # R1 POSITION_MISSING：lat或lon为空，HIGH
    if lat is None or lon is None:
        alerts.append({
            "alert_time": batch_time,
            "target_id": target_id,
            "alert_type": "POSITION_MISSING",
            "severity": "HIGH",
            "field": "lat" if lat is None else "lon",
            "description": "位置缺失：纬度或经度为空",
        })

    # R2 DATA_DELAYED：batch_time-record_time>60秒，MEDIUM
    if record_time is not None and (batch_time - record_time) > 60:
        alerts.append({
            "alert_time": batch_time,
            "target_id": target_id,
            "alert_type": "DATA_DELAYED",
            "severity": "MEDIUM",
            "field": "timestamp",
            "description": f"数据延迟：{batch_time} - {record_time} = {batch_time - record_time}秒 > 60",
        })

    # R4 HEADING_OUT_OF_RANGE：heading非空且(heading<0或heading>=360)，MEDIUM
    if heading is not None and (heading < 0 or heading >= 360):
        alerts.append({
            "alert_time": batch_time,
            "target_id": target_id,
            "alert_type": "HEADING_OUT_OF_RANGE",
            "severity": "MEDIUM",
            "field": "heading",
            "description": f"航向越界：heading={heading}，应满足0<=heading<360",
        })

    return alerts


def check_duplicates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """使用target_id+timestamp联合键检查重复(R3)。"""
    alerts: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for record in records:
        key = (record.get("target_id"), record.get("timestamp"))
        if key in seen:
            alerts.append({
                "alert_time": BATCH_TIME,
                "target_id": record.get("target_id"),
                "alert_type": "DUPLICATE_RECORD",
                "severity": "MEDIUM",
                "field": "target_id+timestamp",
                "description": f"联合键重复：target_id={key[0]}, timestamp={key[1]}",
            })
        else:
            seen.add(key)
    return alerts


def build_quality_situation(
    records: list[dict[str, Any]], alerts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """按HIGH > MEDIUM > NONE合成质量态势。"""
    seen: set[tuple[Any, Any]] = set()
    rows: list[dict[str, Any]] = []
    for record in records:
        target_id = record.get("target_id")
        lat = _to_float(record.get("lat"))
        lon = _to_float(record.get("lon"))
        heading = _to_float(record.get("heading"))
        record_time = _to_int(record.get("timestamp") or record.get("latest_time"))

        position_valid = lat is not None and lon is not None
        delayed = record_time is not None and (BATCH_TIME - record_time) > 60
        key = (target_id, record.get("timestamp"))
        duplicate_detected = key in seen
        seen.add(key)
        heading_valid = heading is not None and (0 <= heading < 360)
        message_valid = _to_bool(record.get("message_valid"))

        if not position_valid:
            anomaly_level = "HIGH"
        elif delayed or duplicate_detected or not heading_valid:
            anomaly_level = "MEDIUM"
        else:
            anomaly_level = "NONE"

        display_status = (
            "ERROR" if anomaly_level == "HIGH"
            else "WARNING" if anomaly_level == "MEDIUM"
            else "NORMAL"
        )

        rows.append({
            "target_id": target_id,
            "timestamp": record.get("timestamp") or record.get("latest_time") or "",
            "position_valid": position_valid,
            "delayed": delayed,
            "duplicate_detected": duplicate_detected,
            "heading_valid": heading_valid,
            "message_valid": message_valid,
            "anomaly_level": anomaly_level,
            "display_status": display_status,
        })
    return rows
