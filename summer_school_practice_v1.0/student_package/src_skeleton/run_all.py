from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import m2_protocol
import m3_tracks


STUDENT_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = STUDENT_PACKAGE_ROOT / "output"
DATA_ROOT = STUDENT_PACKAGE_ROOT / "data"

DECODED_HEADER = [
    "target_id", "callsign", "timestamp", "timestamp_source", "time_source",
    "message_seq", "lat", "lon", "altitude", "alt_type", "speed", "heading",
    "vertical_rate", "on_ground", "status_flags", "validity_flags",
    "latitude_code", "longitude_code", "altitude_code", "speed_code",
    "heading_code", "vertical_rate_code", "lat_valid", "lon_valid",
    "altitude_valid", "speed_valid", "heading_valid", "vertical_rate_valid",
    "callsign_valid", "checksum", "expected_checksum", "message_valid",
    "validation_errors", "source",
]

VALIDATION_HEADER = ["record_no", "target_id", "stage", "field", "problem_type", "value", "description"]

ROUNDTRIP_HEADER = [
    "field", "source_value", "source_valid", "protocol_code", "flag_bit",
    "decoded_value", "decoded_valid", "absolute_error/tolerance", "passed",
]

ROUNDTRIP_FIELDS = [
    ("lat", "latitude_code", 0, 180.0 / ((1 << 22) - 1)),
    ("lon", "longitude_code", 1, 360.0 / ((1 << 22) - 1)),
    ("altitude", "altitude_code", 2, 1.0),
    ("speed", "speed_code", 3, 0.1),
    ("heading", "heading_code", 4, 0.01),
    ("vertical_rate", "vertical_rate_code", 5, 0.01),
    ("callsign", None, 6, None),
]

TRACK_HEADER = [
    "target_id", "timestamp", "message_seq", "track_sequence_no",
    "lat", "lon", "altitude", "speed", "heading",
]

SITUATION_HEADER = [
    "target_id", "callsign", "latest_time", "lat", "lon", "altitude", "speed",
    "heading", "vertical_rate", "on_ground", "track_length", "alt_type",
    "time_source", "message_valid",
]

# normalized_state_vectors.csv 列名 -> OpenSky 状态向量固定索引
OSK_COLUMNS: dict[str, tuple[int, str]] = {
    "icao24": (0, "str"),
    "callsign": (1, "str"),
    "origin_country": (2, "str"),
    "time_position": (3, "int"),
    "last_contact": (4, "int"),
    "longitude": (5, "float"),
    "latitude": (6, "float"),
    "baro_altitude_m": (7, "float"),
    "on_ground": (8, "bool"),
    "velocity_m_s": (9, "float"),
    "true_track_deg": (10, "float"),
    "vertical_rate_m_s": (11, "float"),
    "geo_altitude_m": (13, "float"),
    "position_source": (16, "int"),
}


def prepare_output_directory() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def _write_csv(name: str, header: list[str], rows: list[dict[str, Any]]) -> None:
    _write_csv_to(OUTPUT_ROOT, name, header, rows)


def _write_csv_to(
    output_dir: Path, name: str, header: list[str], rows: list[dict[str, Any]]
) -> None:
    path = output_dir / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def parse() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """M2：读取OpenSky状态向量并转换为发送方内部结构化记录。"""
    raw = json.loads((DATA_ROOT / "raw_states.json").read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for index, vector in enumerate(raw.get("states", []), start=1):
        record = m2_protocol.parse_state_vector(vector)
        record["record_no"] = index
        records.append(record)
        for err in record.get("errors", []):
            validation_rows.append({
                "record_no": index,
                "target_id": record.get("target_id") or "",
                "stage": "parse",
                "field": err["field"],
                "problem_type": err["problem_type"],
                "value": "" if err["value"] is None else err["value"],
                "description": err["description"],
            })
    return records, validation_rows


def encode(
    records: list[dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], int]], list[dict[str, Any]]]:
    """M2：发送方将可接受的内部记录封装为41字节TeachingLink帧，
    并写入encoded_messages.bin作为传输通道的发送产物。"""
    frames: list[bytes] = []
    paired: list[tuple[dict[str, Any], int]] = []
    validation_rows: list[dict[str, Any]] = []
    message_seq = 1
    for record in records:
        if record.get("errors"):
            continue
        try:
            frame = m2_protocol.encode_position_message(record, message_seq)
        except ValueError as exc:
            validation_rows.append({
                "record_no": record.get("record_no", ""),
                "target_id": record.get("target_id") or "",
                "stage": "encode",
                "field": "record",
                "problem_type": "ENCODING_ERROR",
                "value": "",
                "description": str(exc),
            })
            continue
        frames.append(frame)
        paired.append((record, message_seq))
        message_seq = (message_seq + 1) % 65536
    (OUTPUT_ROOT / "encoded_messages.bin").write_bytes(b"".join(frames))
    return paired, validation_rows


def decode_validate(
    paired: list[tuple[dict[str, Any], int]],
    validation_rows: list[dict[str, Any]],
) -> None:
    """M2：接收方从传输通道（encoded_messages.bin）读取字节，按41字节
    逐帧解码、验证并输出解码结果与往返报告。"""
    raw = (OUTPUT_ROOT / "encoded_messages.bin").read_bytes()
    frames = [raw[i:i + 41] for i in range(0, len(raw), 41)]
    decoded_rows: list[dict[str, Any]] = []
    roundtrip_rows: list[dict[str, Any]] = []
    for frame, (record, _seq) in zip(frames, paired):
        decoded = m2_protocol.decode_position_message(frame)
        decoded["source"] = "opensky"

        row: dict[str, Any] = {}
        for name in DECODED_HEADER:
            if name == "validation_errors":
                row[name] = "；".join(
                    err.get("description", "") for err in decoded.get("validation_errors", [])
                )
            else:
                row[name] = decoded.get(name, "")
        decoded_rows.append(row)

        for err in decoded.get("validation_errors", []):
            validation_rows.append({
                "record_no": record.get("record_no", ""),
                "target_id": decoded.get("target_id") or record.get("target_id") or "",
                "stage": "decode",
                "field": err.get("field", ""),
                "problem_type": err.get("problem_type", ""),
                "value": "" if err.get("value") is None else err.get("value"),
                "description": err.get("description", ""),
            })

        for field, code_field, flag_bit, tolerance in ROUNDTRIP_FIELDS:
            source_value = record.get(field)
            source_valid = source_value is not None
            decoded_value = decoded.get(field)
            decoded_valid = bool(decoded.get(f"{field}_valid", False))
            protocol_code = decoded.get(code_field, "") if code_field else ""
            if not source_valid:
                passed = not decoded_valid
                error_tol = "N/A"
            elif field == "callsign":
                passed = bool(decoded_valid and decoded_value == source_value)
                error_tol = "N/A"
            elif decoded_valid:
                abs_err = abs(float(decoded_value) - float(source_value))
                error_tol = f"{abs_err:.6g}/{tolerance:.6g}"
                passed = abs_err <= tolerance + 1e-9
            else:
                passed = False
                error_tol = "N/A"
            roundtrip_rows.append({
                "field": field,
                "source_value": "" if source_value is None else source_value,
                "source_valid": source_valid,
                "protocol_code": protocol_code,
                "flag_bit": flag_bit,
                "decoded_value": "" if decoded_value is None else decoded_value,
                "decoded_valid": decoded_valid,
                "absolute_error/tolerance": error_tol,
                "passed": passed,
            })

    if frames:
        _verify_error_frames(frames[0], validation_rows)

    _write_csv("decoded_partner_states.csv", DECODED_HEADER, decoded_rows)
    _write_csv("validation_log.csv", VALIDATION_HEADER, validation_rows)
    _write_csv("roundtrip_report.csv", ROUNDTRIP_HEADER, roundtrip_rows)


def _verify_error_frames(base_frame: bytes, validation_rows: list[dict[str, Any]]) -> None:
    """按手册5.3构造长度、头字段、校验和、保留位、标志占位不一致的错误帧，
    验证非法帧被记录且不会导致程序整体崩溃。"""
    cases: list[tuple[str, bytes]] = []

    # 长度错误
    cases.append(("err-length", base_frame[:-1]))

    # magic 头字段错误
    bad_magic = bytearray(base_frame)
    bad_magic[0:2] = b"\x00\x00"
    cases.append(("err-magic", bytes(bad_magic)))

    # 校验和错误（改动数据字节但不更新校验和）
    bad_checksum = bytearray(base_frame)
    bad_checksum[8] ^= 0xFF
    cases.append(("err-checksum", bytes(bad_checksum)))

    # 保留位错误（经纬度容器最高2位置1）
    bad_reserved = bytearray(base_frame)
    bad_reserved[23] |= 0xC0
    cases.append(("err-reserved", bytes(bad_reserved)))

    # 标志/占位不一致（清除纬度有效位，但占位整数非0）
    bad_flag = bytearray(base_frame)
    bad_flag[38] &= ~(1 << 0)
    cases.append(("err-flag", bytes(bad_flag)))

    for record_no, frame in cases:
        decoded = m2_protocol.decode_position_message(frame)
        for err in decoded.get("validation_errors", []):
            validation_rows.append({
                "record_no": record_no,
                "target_id": decoded.get("target_id") or "",
                "stage": "decode",
                "field": err.get("field", ""),
                "problem_type": err.get("problem_type", ""),
                "value": "" if err.get("value") is None else err.get("value"),
                "description": err.get("description", ""),
            })


def build_tracks() -> None:
    """M3：批量解码多时刻消息，生成航迹与当前态势，并选做SQLite。"""
    raw = (DATA_ROOT / "partner_messages_multitime.bin").read_bytes()
    records = m3_tracks.decode_message_stream(raw)

    decoded_rows: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        for name in DECODED_HEADER:
            if name == "validation_errors":
                row[name] = "；".join(
                    err.get("description", "") for err in record.get("validation_errors", [])
                )
            else:
                row[name] = record.get(name, "")
        row["source"] = "partner_messages_multitime.bin"
        decoded_rows.append(row)
    _write_csv("decoded_multitime.csv", DECODED_HEADER, decoded_rows)

    tracks = m3_tracks.build_tracks(records)
    _write_csv("track_table.csv", TRACK_HEADER, tracks)

    situation = m3_tracks.build_current_situation(records)
    _write_csv("current_situation.csv", SITUATION_HEADER, situation)

    acceptable = [
        record for record in records
        if record.get("message_valid")
        and record.get("target_id")
        and record.get("timestamp") is not None
    ]
    m3_tracks.save_records_to_sqlite(acceptable, str(OUTPUT_ROOT / "states.db"))

    validate_opensky_real()


def _to_opensky_vector(row: dict[str, str]) -> list[Any]:
    """把normalized_state_vectors.csv的一行转换为17元素OpenSky状态向量数组。"""
    vector: list[Any] = [None] * 17
    for column, (index, kind) in OSK_COLUMNS.items():
        raw = row.get(column, "")
        if raw is None or raw == "":
            continue
        if kind == "str":
            vector[index] = raw
        elif kind == "int":
            vector[index] = int(float(raw))
        elif kind == "float":
            vector[index] = float(raw)
        elif kind == "bool":
            vector[index] = raw.strip().lower() in ("true", "1")
    return vector


def validate_opensky_real() -> None:
    """6.6 使用本人M2-M3代码对OpenSky真实快照做完整收发与精度验证。"""
    data_dir = DATA_ROOT / "opensky_real"
    output_dir = OUTPUT_ROOT / "opensky_real"
    output_dir.mkdir(parents=True, exist_ok=True)

    with (data_dir / "normalized_state_vectors.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    parsed: list[dict[str, Any]] = []
    for row in rows:
        record = m2_protocol.parse_state_vector(_to_opensky_vector(row))
        record["_row"] = row
        parsed.append(record)

    # 选中：有位置（lat、lon均非空）且通过教学协议量程检查
    selected = [
        record for record in parsed
        if not record.get("errors")
        and record.get("lat") is not None
        and record.get("lon") is not None
    ]

    # 1. 接收前空态势
    _write_csv_to(output_dir, "receiver_situation_initial.csv", SITUATION_HEADER, [])

    # 2. 本次选中的OpenSky源状态（发送方内部记录）
    source_header = [
        "target_id", "callsign", "timestamp", "time_source", "lat", "lon",
        "altitude", "alt_type", "speed", "heading", "vertical_rate", "on_ground",
    ]
    source_rows = [
        {key: ("" if record.get(key) is None else record.get(key)) for key in source_header}
        for record in selected
    ]
    _write_csv_to(output_dir, "selected_source_states.csv", source_header, source_rows)

    # 3. 模拟发送的41字节帧
    frames: list[bytes] = []
    message_seq = 1
    for record in selected:
        frames.append(m2_protocol.encode_position_message(record, message_seq))
        message_seq = (message_seq + 1) % 65536
    (output_dir / "transmitted_frames.bin").write_bytes(b"".join(frames))

    # 4. 逐帧接收过程 + 5. 解码结果
    decoded: list[dict[str, Any]] = []
    trans_log: list[dict[str, Any]] = []
    for index, frame in enumerate(frames, start=1):
        record = m2_protocol.decode_position_message(frame)
        record["source"] = "opensky_real"
        decoded.append(record)
        trans_log.append({
            "frame_index": index,
            "message_seq": record.get("message_seq"),
            "target_id": record.get("target_id"),
            "timestamp": record.get("timestamp"),
            "checksum": record.get("checksum"),
            "expected_checksum": record.get("expected_checksum"),
            "message_valid": record.get("message_valid"),
            "validation_errors": "；".join(
                err.get("description", "") for err in record.get("validation_errors", [])
            ),
        })
    _write_csv_to(output_dir, "transmission_log.csv", [
        "frame_index", "message_seq", "target_id", "timestamp", "checksum",
        "expected_checksum", "message_valid", "validation_errors",
    ], trans_log)

    decoded_rows: list[dict[str, Any]] = []
    for record in decoded:
        row: dict[str, Any] = {}
        for name in DECODED_HEADER:
            if name == "validation_errors":
                row[name] = "；".join(
                    err.get("description", "") for err in record.get("validation_errors", [])
                )
            else:
                row[name] = record.get(name, "")
        decoded_rows.append(row)
    _write_csv_to(output_dir, "decoded_states.csv", DECODED_HEADER, decoded_rows)

    # 6. 最终当前态势
    situation = m3_tracks.build_current_situation(decoded)
    _write_csv_to(output_dir, "receiver_situation_final.csv", SITUATION_HEADER, situation)

    # 7. SQLite接收记录
    m3_tracks.save_records_to_sqlite(decoded, str(output_dir / "received_states.db"))

    # 8. 源值与解码值误差
    precision_header = [
        "target_id", "field", "source_value", "source_valid", "protocol_code",
        "decoded_value", "decoded_valid", "absolute_error/tolerance", "passed",
    ]
    precision_rows: list[dict[str, Any]] = []
    for source, record in zip(selected, decoded):
        for field, code_field, flag_bit, tolerance in ROUNDTRIP_FIELDS:
            source_value = source.get(field)
            source_valid = source_value is not None
            decoded_value = record.get(field)
            decoded_valid = bool(record.get(f"{field}_valid", False))
            if not source_valid:
                passed = not decoded_valid
                error_tol = "N/A"
            elif field == "callsign":
                passed = bool(decoded_valid and decoded_value == source_value)
                error_tol = "N/A"
            elif decoded_valid:
                abs_err = abs(float(decoded_value) - float(source_value))
                error_tol = f"{abs_err:.6g}/{tolerance:.6g}"
                passed = abs_err <= tolerance + 1e-9
            else:
                passed = False
                error_tol = "N/A"
            precision_rows.append({
                "target_id": record.get("target_id"),
                "field": field,
                "source_value": "" if source_value is None else source_value,
                "source_valid": source_valid,
                "protocol_code": record.get(code_field, "") if code_field else "",
                "decoded_value": "" if decoded_value is None else decoded_value,
                "decoded_valid": decoded_valid,
                "absolute_error/tolerance": error_tol,
                "passed": passed,
            })
    _write_csv_to(output_dir, "precision_error_report.csv", precision_header, precision_rows)

    # 9. 实验摘要
    summary = {
        "snapshot_count": len({row.get("snapshot_index") for row in rows}),
        "record_count": len(parsed),
        "selected_count": len(selected),
        "frame_count": len(frames),
        "decoded_count": len(decoded),
        "message_valid_count": sum(1 for record in decoded if record.get("message_valid")),
        "track_count": len(situation),
    }
    (output_dir / "experiment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def map_unified() -> None:
    raise NotImplementedError("TODO：接入M4人工核验后的映射实现。")


def check_quality() -> None:
    raise NotImplementedError("TODO：接入M5一致性检查实现。")


def export_results() -> None:
    raise NotImplementedError("TODO：整理M6关键成果和README；不得把助教检查点当成本模块成果。")


def run_pipeline() -> None:
    prepare_output_directory()
    records, parse_validation = parse()
    paired, encode_validation = encode(records)
    decode_validate(paired, parse_validation + encode_validation)
    build_tracks()
    map_unified()
    check_quality()
    export_results()


def main() -> int:
    try:
        run_pipeline()
    except NotImplementedError as exc:
        print(exc)
        print("当前文件是学生骨架，M2已运行，其余模块实现完成后再进行端到端运行。")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
