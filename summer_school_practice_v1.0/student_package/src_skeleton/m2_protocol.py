from __future__ import annotations

import math
import struct
from typing import Any


# ---------------------------------------------------------------------------
# TeachingLink 固定约定
# ---------------------------------------------------------------------------
FRAME_SIZE = 41

MAGIC = 0x4453
VERSION = 1
MESSAGE_TYPE = 1
MESSAGE_LENGTH = 41

# 22 位经纬度容器的最大编码值（2^22 - 1）
LAT_LON_CODE_MAX = (1 << 22) - 1
# 统一量化分辨率与偏置
LAT_SCALE = 180.0
LON_SCALE = 360.0
ALTITUDE_OFFSET = 1000.0
SPEED_SCALE = 0.1
HEADING_SCALE = 0.01
VERTICAL_RATE_OFFSET = 327.68
VERTICAL_RATE_SCALE = 0.01

HEX_CHARS = set("0123456789abcdef")

# validation_log.csv 的 problem_type 统一枚举（见学生实验手册 5.4）
PROBLEM_MISSING = "MISSING"
PROBLEM_REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
PROBLEM_OUT_OF_RANGE = "OUT_OF_RANGE"
PROBLEM_TYPE_ERROR = "TYPE_ERROR"
PROBLEM_ENCODING_ERROR = "ENCODING_ERROR"
PROBLEM_LENGTH_ERROR = "LENGTH_ERROR"
PROBLEM_MAGIC_ERROR = "MAGIC_ERROR"
PROBLEM_VERSION_ERROR = "VERSION_ERROR"
PROBLEM_MESSAGE_TYPE_ERROR = "MESSAGE_TYPE_ERROR"
PROBLEM_RESERVED_BITS_ERROR = "RESERVED_BITS_ERROR"
PROBLEM_FLAG_VALUE_INCONSISTENCY = "FLAG_VALUE_INCONSISTENCY"
PROBLEM_CHECKSUM_ERROR = "CHECKSUM_ERROR"


def _quantize(value: float) -> int:
    """统一量化函数 Q(y) = floor(y + 0.5)，不依赖语言默认 round。"""
    return math.floor(value + 0.5)


def _error(field: str, problem_type: str, value: Any, description: str) -> dict[str, Any]:
    return {
        "field": field,
        "problem_type": problem_type,
        "value": value,
        "description": description,
    }


def _empty_result(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """构造一个完全无效的解码结果，用于长度错误等无法解析的场景。"""
    return {
        "target_id": None,
        "callsign": None,
        "timestamp": None,
        "timestamp_source": None,
        "time_source": None,
        "message_seq": None,
        "lat": None,
        "lon": None,
        "altitude": None,
        "alt_type": "unknown",
        "speed": None,
        "heading": None,
        "vertical_rate": None,
        "on_ground": None,
        "status_flags": 0,
        "validity_flags": 0,
        "latitude_code": 0,
        "longitude_code": 0,
        "altitude_code": 0,
        "speed_code": 0,
        "heading_code": 0,
        "vertical_rate_code": 0,
        "lat_valid": False,
        "lon_valid": False,
        "altitude_valid": False,
        "speed_valid": False,
        "heading_valid": False,
        "vertical_rate_valid": False,
        "callsign_valid": False,
        "checksum": None,
        "expected_checksum": None,
        "message_valid": False,
        "validation_errors": errors,
    }


def parse_state_vector(vector: list[Any]) -> dict[str, Any]:
    """将OpenSky状态向量转换为发送方内部结构化记录。

    按 opensky_field_dictionary.csv 的固定索引取字段，处理必需/可空字段、
    时间与高度的来源回退，并执行物理量程检查。检查发现的问题记入
    record["errors"]（每项含 field/problem_type/value/description），
    由后续编码阶段决定是否可编码。
    """
    errors: list[dict[str, Any]] = []

    def get(index: int) -> Any:
        return vector[index] if index < len(vector) else None

    # 0: icao24 -> target_id（必需，六位小写十六进制，保留前导0）
    icao24 = get(0)
    target_id: str | None = None
    if icao24 is None:
        errors.append(_error("target_id", PROBLEM_REQUIRED_FIELD_MISSING, None, "target_id缺失"))
    elif not isinstance(icao24, str):
        errors.append(_error("target_id", PROBLEM_TYPE_ERROR, icao24, f"icao24不是字符串: {icao24!r}"))
    else:
        candidate = icao24.strip().lower()
        if len(candidate) == 6 and all(ch in HEX_CHARS for ch in candidate):
            target_id = candidate
        else:
            errors.append(_error("target_id", PROBLEM_TYPE_ERROR, icao24, f"icao24格式非法: {icao24!r}"))

    # 1: callsign（可空；去空格后1-8个ASCII字符，超长或非ASCII报错）
    callsign_raw = get(1)
    callsign: str | None = None
    if isinstance(callsign_raw, str):
        stripped = callsign_raw.strip()
        if stripped:
            if len(stripped) > 8 or any(ord(ch) > 127 for ch in stripped):
                errors.append(_error("callsign", PROBLEM_TYPE_ERROR, callsign_raw, f"呼号超长或非ASCII: {callsign_raw!r}"))
            else:
                callsign = stripped

    # 3/4: 时间回退（优先 time_position，否则 last_contact）
    time_position = get(3)
    last_contact = get(4)
    timestamp: int | None = None
    timestamp_source: str | None = None
    time_source: str | None = None
    if time_position is not None:
        timestamp = int(time_position)
        timestamp_source = "time_position"
        time_source = "position_time"
    elif last_contact is not None:
        timestamp = int(last_contact)
        timestamp_source = "last_contact"
        time_source = "last_contact_fallback"
    else:
        errors.append(_error("timestamp", PROBLEM_REQUIRED_FIELD_MISSING, None, "时间缺失：time_position与last_contact均为空"))

    # 6: 纬度（可空，量程 [-90, 90]）
    lat = get(6)
    if lat is not None:
        lat = float(lat)
        if not (-90.0 <= lat <= 90.0):
            errors.append(_error("lat", PROBLEM_OUT_OF_RANGE, lat, f"纬度越界: {lat}"))

    # 5: 经度（可空，量程 [-180, 180]）
    lon = get(5)
    if lon is not None:
        lon = float(lon)
        if not (-180.0 <= lon <= 180.0):
            errors.append(_error("lon", PROBLEM_OUT_OF_RANGE, lon, f"经度越界: {lon}"))

    # 7/13: 高度回退（优先 baro_altitude，否则 geo_altitude）
    baro_altitude = get(7)
    geo_altitude = get(13)
    altitude: float | None = None
    alt_type: str = "unknown"
    if baro_altitude is not None:
        altitude = float(baro_altitude)
        alt_type = "barometric"
    elif geo_altitude is not None:
        altitude = float(geo_altitude)
        alt_type = "geometric"
    if altitude is not None:
        code = _quantize(altitude + ALTITUDE_OFFSET)
        if not (0 <= code <= 0xFFFF):
            errors.append(_error("altitude", PROBLEM_OUT_OF_RANGE, altitude, f"高度编码越界: {altitude}"))

    # 8: on_ground（必需布尔）
    on_ground_raw = get(8)
    on_ground: bool
    if on_ground_raw is None:
        errors.append(_error("on_ground", PROBLEM_REQUIRED_FIELD_MISSING, None, "on_ground缺失"))
        on_ground = False
    else:
        on_ground = bool(on_ground_raw)

    # 9: 地速（可空，>=0 且编码后能放入 uint16）
    speed = get(9)
    if speed is not None:
        speed = float(speed)
        if speed < 0:
            errors.append(_error("speed", PROBLEM_OUT_OF_RANGE, speed, f"地速为负: {speed}"))
        elif _quantize(speed / SPEED_SCALE) > 0xFFFF:
            errors.append(_error("speed", PROBLEM_OUT_OF_RANGE, speed, f"地速编码越界: {speed}"))

    # 10: 航向（可空，0 <= heading < 360）
    heading = get(10)
    if heading is not None:
        heading = float(heading)
        if not (0.0 <= heading < 360.0):
            errors.append(_error("heading", PROBLEM_OUT_OF_RANGE, heading, f"航向越界: {heading}（应0≤heading<360）"))

    # 11: 垂直速度（可空，编码后能放入 uint16）
    vertical_rate = get(11)
    if vertical_rate is not None:
        vertical_rate = float(vertical_rate)
        code = _quantize((vertical_rate + VERTICAL_RATE_OFFSET) / VERTICAL_RATE_SCALE)
        if not (0 <= code <= 0xFFFF):
            errors.append(_error("vertical_rate", PROBLEM_OUT_OF_RANGE, vertical_rate, f"垂直速度编码越界: {vertical_rate}"))

    return {
        "target_id": target_id,
        "callsign": callsign,
        "timestamp": timestamp,
        "timestamp_source": timestamp_source,
        "time_source": time_source,
        "lat": lat,
        "lon": lon,
        "altitude": altitude,
        "alt_type": alt_type,
        "speed": speed,
        "heading": heading,
        "vertical_rate": vertical_rate,
        "on_ground": on_ground,
        "errors": errors,
    }


def calculate_checksum(data_without_checksum: bytes) -> int:
    """计算前39字节无符号字节值之和模65536。"""
    return sum(data_without_checksum) % 65536


def encode_position_message(record: dict[str, Any], message_seq: int) -> bytes:
    """按41字节TeachingLink格式封装一条位置状态消息。"""
    errors = record.get("errors") or []
    if errors:
        raise ValueError("；".join(err["description"] for err in errors))

    target_id = record.get("target_id")
    callsign = record.get("callsign")
    timestamp = record.get("timestamp")
    time_source = record.get("time_source")
    alt_type = record.get("alt_type", "unknown")
    on_ground = bool(record.get("on_ground", False))
    lat = record.get("lat")
    lon = record.get("lon")
    altitude = record.get("altitude")
    speed = record.get("speed")
    heading = record.get("heading")
    vertical_rate = record.get("vertical_rate")

    if not isinstance(target_id, str) or len(target_id) != 6:
        raise ValueError("target_id缺失或格式非法")
    if timestamp is None or not isinstance(timestamp, int) or timestamp <= 0:
        raise ValueError("timestamp缺失或非法")

    # 字段有效性
    lat_valid = lat is not None
    lon_valid = lon is not None
    altitude_valid = altitude is not None
    speed_valid = speed is not None
    heading_valid = heading is not None
    vertical_rate_valid = vertical_rate is not None
    callsign_valid = bool(callsign)

    # 定点量化（编码前量程检查，禁止静默截断/掩码/取模）
    if lat_valid:
        if not (-90.0 <= lat <= 90.0):
            raise ValueError("纬度越界")
        lat_code = _quantize((lat + 90.0) / LAT_SCALE * LAT_LON_CODE_MAX)
    else:
        lat_code = 0

    if lon_valid:
        if not (-180.0 <= lon <= 180.0):
            raise ValueError("经度越界")
        lon_code = _quantize((lon + 180.0) / LON_SCALE * LAT_LON_CODE_MAX)
    else:
        lon_code = 0

    if altitude_valid:
        alt_code = _quantize(altitude + ALTITUDE_OFFSET)
        if not (0 <= alt_code <= 0xFFFF):
            raise ValueError("高度越界")
    else:
        alt_code = 0

    if speed_valid:
        if speed < 0:
            raise ValueError("地速越界")
        speed_code = _quantize(speed / SPEED_SCALE)
        if speed_code > 0xFFFF:
            raise ValueError("地速越界")
    else:
        speed_code = 0

    if heading_valid:
        if not (0.0 <= heading < 360.0):
            raise ValueError("航向越界")
        heading_code = _quantize(heading / HEADING_SCALE)
    else:
        heading_code = 0

    if vertical_rate_valid:
        vs_code = _quantize((vertical_rate + VERTICAL_RATE_OFFSET) / VERTICAL_RATE_SCALE)
        if not (0 <= vs_code <= 0xFFFF):
            raise ValueError("垂直速度越界")
    else:
        vs_code = 0

    # callsign：有效时1-8字节，不足补0，不静默截断
    if callsign_valid:
        callsign_bytes = callsign.encode("ascii")
        if len(callsign_bytes) > 8:
            raise ValueError("呼号超过8字节，禁止静默截断")
        callsign_bytes = callsign_bytes + b"\x00" * (8 - len(callsign_bytes))
    else:
        callsign_bytes = b"\x00" * 8

    # status_flags
    status_flags = 0
    if on_ground:
        status_flags |= 1 << 0
    if altitude_valid and alt_type == "geometric":
        status_flags |= 1 << 1
    if time_source == "last_contact_fallback":
        status_flags |= 1 << 2

    # validity_flags
    validity_flags = 0
    if lat_valid:
        validity_flags |= 1 << 0
    if lon_valid:
        validity_flags |= 1 << 1
    if altitude_valid:
        validity_flags |= 1 << 2
    if speed_valid:
        validity_flags |= 1 << 3
    if heading_valid:
        validity_flags |= 1 << 4
    if vertical_rate_valid:
        validity_flags |= 1 << 5
    if callsign_valid:
        validity_flags |= 1 << 6

    body = (
        struct.pack(">H", MAGIC)                                  # 0-1
        + bytes([VERSION, MESSAGE_TYPE])                          # 2-3
        + struct.pack(">H", MESSAGE_LENGTH)                       # 4-5
        + struct.pack(">H", message_seq & 0xFFFF)                 # 6-7
        + struct.pack(">I", timestamp)                            # 8-11
        + int(target_id, 16).to_bytes(3, "big")                   # 12-14
        + callsign_bytes                                          # 15-22
        + lat_code.to_bytes(3, "big")                             # 23-25
        + lon_code.to_bytes(3, "big")                             # 26-28
        + struct.pack(">H", alt_code)                             # 29-30
        + struct.pack(">H", speed_code)                           # 31-32
        + struct.pack(">H", heading_code)                         # 33-34
        + struct.pack(">H", vs_code)                              # 35-36
        + bytes([status_flags, validity_flags])                   # 37-38
    )
    checksum = calculate_checksum(body)
    return body + struct.pack(">H", checksum)                     # 39-40


def decode_position_message(data: bytes) -> dict[str, Any]:
    """检查帧接收条件并恢复接收方结构化记录。"""
    errors: list[dict[str, Any]] = []
    if not isinstance(data, (bytes, bytearray)):
        errors.append(_error("frame", PROBLEM_TYPE_ERROR, None, "frame is not bytes"))
        return _empty_result(errors)
    if len(data) != FRAME_SIZE:
        errors.append(_error("frame", PROBLEM_LENGTH_ERROR, len(data), f"invalid length {len(data)} (expected {FRAME_SIZE})"))
        return _empty_result(errors)

    magic = struct.unpack(">H", data[0:2])[0]
    version = data[2]
    message_type = data[3]
    message_length = struct.unpack(">H", data[4:6])[0]
    message_seq = struct.unpack(">H", data[6:8])[0]
    timestamp = struct.unpack(">I", data[8:12])[0]
    target_id_int = int.from_bytes(data[12:15], "big")
    target_id = f"{target_id_int:06x}"
    callsign_raw = data[15:23]
    lat_code = int.from_bytes(data[23:26], "big")
    lon_code = int.from_bytes(data[26:29], "big")
    alt_code = struct.unpack(">H", data[29:31])[0]
    speed_code = struct.unpack(">H", data[31:33])[0]
    heading_code = struct.unpack(">H", data[33:35])[0]
    vs_code = struct.unpack(">H", data[35:37])[0]
    status_flags = data[37]
    validity_flags = data[38]
    checksum = struct.unpack(">H", data[39:41])[0]
    expected_checksum = calculate_checksum(data[0:39])

    # 头字段
    if magic != MAGIC:
        errors.append(_error("magic", PROBLEM_MAGIC_ERROR, magic, f"bad magic 0x{magic:04x}"))
    if version != VERSION:
        errors.append(_error("version", PROBLEM_VERSION_ERROR, version, f"bad version {version}"))
    if message_type != MESSAGE_TYPE:
        errors.append(_error("message_type", PROBLEM_MESSAGE_TYPE_ERROR, message_type, f"bad message_type {message_type}"))
    if message_length != MESSAGE_LENGTH:
        errors.append(_error("message_length", PROBLEM_LENGTH_ERROR, message_length, f"bad message_length {message_length}"))

    # 校验和
    if checksum != expected_checksum:
        errors.append(_error("checksum", PROBLEM_CHECKSUM_ERROR, checksum, f"checksum mismatch: got {checksum}, expected {expected_checksum}"))

    # 经纬度容器保留位（最高2位必须为0）
    if lat_code > LAT_LON_CODE_MAX:
        errors.append(_error("latitude_code", PROBLEM_RESERVED_BITS_ERROR, lat_code, "latitude reserved bits nonzero"))
    if lon_code > LAT_LON_CODE_MAX:
        errors.append(_error("longitude_code", PROBLEM_RESERVED_BITS_ERROR, lon_code, "longitude reserved bits nonzero"))

    # 标志字节保留位
    if status_flags & 0b11111000:
        errors.append(_error("status_flags", PROBLEM_RESERVED_BITS_ERROR, status_flags, "status_flags reserved bits nonzero"))
    if validity_flags & 0x80:
        errors.append(_error("validity_flags", PROBLEM_RESERVED_BITS_ERROR, validity_flags, "validity_flags reserved bit nonzero"))

    # 字段有效性
    lat_valid = bool(validity_flags & (1 << 0))
    lon_valid = bool(validity_flags & (1 << 1))
    altitude_valid = bool(validity_flags & (1 << 2))
    speed_valid = bool(validity_flags & (1 << 3))
    heading_valid = bool(validity_flags & (1 << 4))
    vertical_rate_valid = bool(validity_flags & (1 << 5))
    callsign_valid = bool(validity_flags & (1 << 6))

    # 标志/占位一致性：无效字段的占位整数必须为0
    if not lat_valid and lat_code != 0:
        errors.append(_error("latitude_code", PROBLEM_FLAG_VALUE_INCONSISTENCY, lat_code, "latitude placeholder nonzero"))
    if not lon_valid and lon_code != 0:
        errors.append(_error("longitude_code", PROBLEM_FLAG_VALUE_INCONSISTENCY, lon_code, "longitude placeholder nonzero"))
    if not altitude_valid and alt_code != 0:
        errors.append(_error("altitude_code", PROBLEM_FLAG_VALUE_INCONSISTENCY, alt_code, "altitude placeholder nonzero"))
    if not speed_valid and speed_code != 0:
        errors.append(_error("speed_code", PROBLEM_FLAG_VALUE_INCONSISTENCY, speed_code, "speed placeholder nonzero"))
    if not heading_valid and heading_code != 0:
        errors.append(_error("heading_code", PROBLEM_FLAG_VALUE_INCONSISTENCY, heading_code, "heading placeholder nonzero"))
    if not vertical_rate_valid and vs_code != 0:
        errors.append(_error("vertical_rate_code", PROBLEM_FLAG_VALUE_INCONSISTENCY, vs_code, "vertical_rate placeholder nonzero"))
    if not callsign_valid and callsign_raw != b"\x00" * 8:
        errors.append(_error("callsign", PROBLEM_FLAG_VALUE_INCONSISTENCY, callsign_raw, "callsign placeholder nonzero"))

    # 字段恢复
    lat = None
    lon = None
    altitude = None
    speed = None
    heading = None
    vertical_rate = None
    if lat_valid:
        lat = lat_code / LAT_LON_CODE_MAX * LAT_SCALE - 90.0
        if not (-90.0 <= lat <= 90.0):
            errors.append(_error("latitude_code", PROBLEM_OUT_OF_RANGE, lat_code, "latitude decode out of range"))
    if lon_valid:
        lon = lon_code / LAT_LON_CODE_MAX * LON_SCALE - 180.0
        if not (-180.0 <= lon <= 180.0):
            errors.append(_error("longitude_code", PROBLEM_OUT_OF_RANGE, lon_code, "longitude decode out of range"))
    if altitude_valid:
        altitude = alt_code - ALTITUDE_OFFSET
    if speed_valid:
        speed = speed_code * SPEED_SCALE
    if heading_valid:
        heading = heading_code * HEADING_SCALE
        if heading >= 360.0:
            errors.append(_error("heading_code", PROBLEM_OUT_OF_RANGE, heading_code, "heading decode out of range"))
    if vertical_rate_valid:
        vertical_rate = vs_code * VERTICAL_RATE_SCALE - VERTICAL_RATE_OFFSET

    if callsign_valid:
        stripped = callsign_raw.rstrip(b"\x00")
        if stripped and all(32 <= byte < 127 for byte in stripped):
            callsign = stripped.decode("ascii")
        else:
            callsign = None
            errors.append(_error("callsign", PROBLEM_FLAG_VALUE_INCONSISTENCY, None, "callsign valid flag set but empty payload"))
    else:
        callsign = None

    # 必需字段
    if target_id_int == 0:
        errors.append(_error("target_id", PROBLEM_REQUIRED_FIELD_MISSING, target_id_int, "target_id zero"))
    if timestamp <= 0:
        errors.append(_error("timestamp", PROBLEM_REQUIRED_FIELD_MISSING, timestamp, "timestamp missing or invalid"))

    on_ground = bool(status_flags & 1)
    altitude_is_geometric = bool(status_flags & (1 << 1))
    timestamp_fallback = bool(status_flags & (1 << 2))

    if altitude_valid:
        alt_type = "geometric" if altitude_is_geometric else "barometric"
    else:
        alt_type = "unknown"
    time_source = "last_contact_fallback" if timestamp_fallback else "position_time"
    timestamp_source = "last_contact" if timestamp_fallback else "time_position"

    return {
        "target_id": target_id,
        "callsign": callsign,
        "timestamp": timestamp,
        "timestamp_source": timestamp_source,
        "time_source": time_source,
        "message_seq": message_seq,
        "lat": lat,
        "lon": lon,
        "altitude": altitude,
        "alt_type": alt_type,
        "speed": speed,
        "heading": heading,
        "vertical_rate": vertical_rate,
        "on_ground": on_ground,
        "status_flags": status_flags,
        "validity_flags": validity_flags,
        "latitude_code": lat_code,
        "longitude_code": lon_code,
        "altitude_code": alt_code,
        "speed_code": speed_code,
        "heading_code": heading_code,
        "vertical_rate_code": vs_code,
        "lat_valid": lat_valid,
        "lon_valid": lon_valid,
        "altitude_valid": altitude_valid,
        "speed_valid": speed_valid,
        "heading_valid": heading_valid,
        "vertical_rate_valid": vertical_rate_valid,
        "callsign_valid": callsign_valid,
        "checksum": checksum,
        "expected_checksum": expected_checksum,
        "message_valid": len(errors) == 0,
        "validation_errors": errors,
    }
