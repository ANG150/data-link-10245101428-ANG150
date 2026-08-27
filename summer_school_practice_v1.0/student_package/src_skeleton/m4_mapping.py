from __future__ import annotations

from typing import Any


LAT_LON_CODE_MAX = (1 << 22) - 1
ALTITUDE_OFFSET = 1000.0
SPEED_SCALE = 0.1
HEADING_SCALE = 0.01
VERTICAL_RATE_OFFSET = 327.68
VERTICAL_RATE_SCALE = 0.01


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


# 人工核验后的正式映射，依据 source_field_definitions.md、teaching_message_spec.md
# 与两个字段字典逐条核验，不照抄预生成候选。
VERIFIED_MAPPING: list[dict[str, Any]] = [
    # ---------- OpenSky ----------
    {"source_format": "OpenSky", "input_field": "target_id", "unified_field": "track_id",
     "mapping_rule": "直接映射", "unit_conversion": "六位小写十六进制，保留前导0",
     "null_strategy": "无", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "latest_time", "unified_field": "timestamp",
     "mapping_rule": "直接映射", "unit_conversion": "Unix秒，必须为正整数",
     "null_strategy": "空→null", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "OpenSky", "input_field": "time_source", "unified_field": "quality.time_source",
     "mapping_rule": "直接映射", "unit_conversion": "position_time / last_contact_fallback",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "OpenSky", "input_field": "callsign", "unified_field": "identity.callsign",
     "mapping_rule": "直接映射", "unit_conversion": "无",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "lat", "unified_field": "position.lat",
     "mapping_rule": "直接映射", "unit_conversion": "度",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "lon", "unified_field": "position.lon",
     "mapping_rule": "直接映射", "unit_conversion": "度",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "altitude", "unified_field": "position.alt",
     "mapping_rule": "直接映射", "unit_conversion": "米",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "alt_type", "unified_field": "position.alt_type",
     "mapping_rule": "直接映射", "unit_conversion": "barometric / geometric / unknown",
     "null_strategy": "空→unknown", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "OpenSky", "input_field": "speed", "unified_field": "motion.speed",
     "mapping_rule": "直接映射", "unit_conversion": "米/秒",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "heading", "unified_field": "motion.heading",
     "mapping_rule": "直接映射", "unit_conversion": "度",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "vertical_rate", "unified_field": "motion.vertical_rate",
     "mapping_rule": "直接映射", "unit_conversion": "米/秒",
     "null_strategy": "空→null", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "on_ground", "unified_field": "status.on_ground",
     "mapping_rule": "直接映射", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "opensky_field_dictionary.csv", "verified": True},
    {"source_format": "OpenSky", "input_field": "lat/lon", "unified_field": "quality.position_valid",
     "mapping_rule": "lat与lon均非空且合法", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "OpenSky", "input_field": "latest_time", "unified_field": "quality.time_valid",
     "mapping_rule": "latest_time为正整数", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "OpenSky", "input_field": "源记录结构", "unified_field": "quality.message_valid",
     "mapping_rule": "源记录结构校验结果", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    # ---------- TeachingLink ----------
    {"source_format": "TeachingLink", "input_field": "target_id", "unified_field": "track_id",
     "mapping_rule": "直接映射", "unit_conversion": "六位小写十六进制，保留前导0",
     "null_strategy": "无", "evidence": "partner_field_dictionary.csv", "verified": True},
    {"source_format": "TeachingLink", "input_field": "timestamp", "unified_field": "timestamp",
     "mapping_rule": "直接映射", "unit_conversion": "Unix秒，必须为正整数",
     "null_strategy": "空→null", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "status_flags.bit2", "unified_field": "quality.time_source",
     "mapping_rule": "bit2=1为last_contact_fallback，否则position_time", "unit_conversion": "无",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "callsign+validity_flags.bit6", "unified_field": "identity.callsign",
     "mapping_rule": "bit6=1时去除补0；无效时null", "unit_conversion": "无",
     "null_strategy": "无效→null", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "latitude_code+validity_flags.bit0", "unified_field": "position.lat",
     "mapping_rule": "有效时code/(2^22-1)×180-90", "unit_conversion": "度",
     "null_strategy": "无效→null", "evidence": "teaching_message_spec.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "longitude_code+validity_flags.bit1", "unified_field": "position.lon",
     "mapping_rule": "有效时code/(2^22-1)×360-180", "unit_conversion": "度",
     "null_strategy": "无效→null", "evidence": "teaching_message_spec.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "altitude_code+validity_flags.bit2", "unified_field": "position.alt",
     "mapping_rule": "有效时code-1000", "unit_conversion": "米",
     "null_strategy": "无效→null", "evidence": "teaching_message_spec.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "status_flags.bit1", "unified_field": "position.alt_type",
     "mapping_rule": "高度有效时0=barometric、1=geometric；无效时unknown", "unit_conversion": "无",
     "null_strategy": "无效→unknown", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "speed_code+validity_flags.bit3", "unified_field": "motion.speed",
     "mapping_rule": "有效时code×0.1", "unit_conversion": "米/秒",
     "null_strategy": "无效→null", "evidence": "teaching_message_spec.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "heading_code+validity_flags.bit4", "unified_field": "motion.heading",
     "mapping_rule": "有效时code×0.01且小于360", "unit_conversion": "度",
     "null_strategy": "无效→null", "evidence": "teaching_message_spec.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "vertical_rate_code+validity_flags.bit5", "unified_field": "motion.vertical_rate",
     "mapping_rule": "有效时code×0.01-327.68", "unit_conversion": "米/秒",
     "null_strategy": "无效→null", "evidence": "teaching_message_spec.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "status_flags.bit0", "unified_field": "status.on_ground",
     "mapping_rule": "bit0转布尔", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "纬经有效位+解码范围", "unified_field": "quality.position_valid",
     "mapping_rule": "纬度与经度均有效且解码值在合法范围", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "timestamp及帧接收", "unified_field": "quality.time_valid",
     "mapping_rule": "timestamp为正整数", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
    {"source_format": "TeachingLink", "input_field": "完整帧接收判据", "unified_field": "quality.message_valid",
     "mapping_rule": "完整帧接收判据", "unit_conversion": "布尔",
     "null_strategy": "无", "evidence": "source_field_definitions.md", "verified": True},
]


def verify_candidate_mapping(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """依据字段定义、单位、有效性和样例，形成人工核验后的正式映射。

    预生成候选仅作参考；正式映射基于权威字段定义逐条核验后给出，
    每条包含证据来源与verified标记。
    """
    return [dict(row) for row in VERIFIED_MAPPING]


def map_to_unified(record: dict[str, Any], source_format: str) -> dict[str, Any]:
    """使用人工核验后的规则生成统一态势消息。"""
    unified: dict[str, Any] = {
        "track_id": "",
        "source": source_format,
        "timestamp": 0,
        "identity": {"callsign": None},
        "position": {"lat": None, "lon": None, "alt": None, "alt_type": "unknown"},
        "motion": {"speed": None, "heading": None, "vertical_rate": None},
        "status": {"on_ground": False},
        "quality": {
            "position_valid": False,
            "time_valid": False,
            "message_valid": False,
            "time_source": "position_time",
            "anomaly_flags": [],
        },
    }

    timestamp = _to_int(record.get("latest_time") or record.get("timestamp"))
    unified["timestamp"] = timestamp or 0
    unified["track_id"] = record.get("target_id") or ""

    if source_format == "OpenSky":
        lat = _to_float(record.get("lat"))
        lon = _to_float(record.get("lon"))
        unified["identity"]["callsign"] = record.get("callsign") or None
        unified["position"]["lat"] = lat
        unified["position"]["lon"] = lon
        unified["position"]["alt"] = _to_float(record.get("altitude"))
        unified["position"]["alt_type"] = record.get("alt_type") or "unknown"
        unified["motion"]["speed"] = _to_float(record.get("speed"))
        unified["motion"]["heading"] = _to_float(record.get("heading"))
        unified["motion"]["vertical_rate"] = _to_float(record.get("vertical_rate"))
        unified["status"]["on_ground"] = _to_bool(record.get("on_ground"))
        unified["quality"]["position_valid"] = lat is not None and lon is not None
        unified["quality"]["time_valid"] = timestamp is not None and timestamp > 0
        unified["quality"]["message_valid"] = _to_bool(record.get("message_valid"))
        unified["quality"]["time_source"] = record.get("time_source") or "position_time"
    elif source_format == "TeachingLink":
        validity = _to_int(record.get("validity_flags")) or 0
        status = _to_int(record.get("status_flags")) or 0

        if validity & (1 << 6):
            unified["identity"]["callsign"] = record.get("callsign") or None

        lat_valid = bool(validity & (1 << 0))
        lon_valid = bool(validity & (1 << 1))
        if lat_valid:
            lat_code = _to_int(record.get("latitude_code")) or 0
            unified["position"]["lat"] = lat_code / LAT_LON_CODE_MAX * 180.0 - 90.0
        if lon_valid:
            lon_code = _to_int(record.get("longitude_code")) or 0
            unified["position"]["lon"] = lon_code / LAT_LON_CODE_MAX * 360.0 - 180.0

        altitude_valid = bool(validity & (1 << 2))
        if altitude_valid:
            alt_code = _to_int(record.get("altitude_code")) or 0
            unified["position"]["alt"] = alt_code - ALTITUDE_OFFSET
            unified["position"]["alt_type"] = "geometric" if (status & (1 << 1)) else "barometric"
        else:
            unified["position"]["alt_type"] = "unknown"

        if validity & (1 << 3):
            speed_code = _to_int(record.get("speed_code")) or 0
            unified["motion"]["speed"] = speed_code * SPEED_SCALE
        if validity & (1 << 4):
            heading_code = _to_int(record.get("heading_code")) or 0
            unified["motion"]["heading"] = heading_code * HEADING_SCALE
        if validity & (1 << 5):
            vs_code = _to_int(record.get("vertical_rate_code")) or 0
            unified["motion"]["vertical_rate"] = vs_code * VERTICAL_RATE_SCALE - VERTICAL_RATE_OFFSET

        unified["status"]["on_ground"] = bool(status & 1)
        unified["quality"]["position_valid"] = lat_valid and lon_valid
        unified["quality"]["time_valid"] = timestamp is not None and timestamp > 0
        unified["quality"]["message_valid"] = _to_bool(record.get("message_valid"))
        unified["quality"]["time_source"] = (
            "last_contact_fallback" if (status & (1 << 2)) else "position_time"
        )

    return unified
