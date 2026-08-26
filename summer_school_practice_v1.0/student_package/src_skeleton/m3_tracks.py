from __future__ import annotations

import sqlite3
from typing import Any

import m2_protocol


def _is_acceptable(record: dict[str, Any]) -> bool:
    """可接受记录：message_valid=true 且 target_id、timestamp 可用。"""
    return bool(
        record.get("message_valid")
        and record.get("target_id")
        and record.get("timestamp") is not None
    )


def decode_message_stream(data: bytes, frame_size: int = 41) -> list[dict[str, Any]]:
    """按固定帧长批量解码；记录并忽略不完整尾帧。

    完整帧逐帧调用M2解码函数并保留每帧验证结果；尾部残余字节不足一帧时，
    以同一解码函数记录LENGTH_ERROR并忽略，不使程序崩溃。
    """
    records: list[dict[str, Any]] = []
    full_length = len(data) - (len(data) % frame_size)
    for offset in range(0, full_length, frame_size):
        frame = data[offset:offset + frame_size]
        records.append(m2_protocol.decode_position_message(frame))
    tail = data[full_length:]
    if tail:
        records.append(m2_protocol.decode_position_message(tail))
    return records


def save_records_to_sqlite(records: list[dict[str, Any]], db_path: str) -> None:
    """选做：保存接收记录，None必须写为NULL。"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state_record (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id TEXT,
            callsign TEXT NULL,
            timestamp INTEGER,
            timestamp_source TEXT,
            message_seq INTEGER,
            lat REAL NULL,
            lon REAL NULL,
            altitude REAL NULL,
            alt_type TEXT NULL,
            speed REAL NULL,
            heading REAL NULL,
            vertical_rate REAL NULL,
            on_ground INTEGER,
            status_flags INTEGER,
            validity_flags INTEGER,
            message_valid INTEGER,
            source TEXT
        )
        """
    )
    for record in records:
        on_ground = record.get("on_ground")
        message_valid = record.get("message_valid")
        conn.execute(
            """
            INSERT INTO state_record
                (target_id, callsign, timestamp, timestamp_source, message_seq,
                 lat, lon, altitude, alt_type, speed, heading, vertical_rate,
                 on_ground, status_flags, validity_flags, message_valid, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("target_id"),
                record.get("callsign"),
                record.get("timestamp"),
                record.get("timestamp_source"),
                record.get("message_seq"),
                record.get("lat"),
                record.get("lon"),
                record.get("altitude"),
                record.get("alt_type"),
                record.get("speed"),
                record.get("heading"),
                record.get("vertical_rate"),
                int(on_ground) if on_ground is not None else None,
                record.get("status_flags"),
                record.get("validity_flags"),
                int(message_valid) if message_valid is not None else None,
                record.get("source"),
            ),
        )
    conn.commit()
    conn.close()


def build_tracks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仅使用可接受记录，按target_id分组并按timestamp排序。

    每组内按timestamp升序生成从1开始的track_sequence_no；message_seq只用于
    追踪发送顺序，不作为航迹排序依据。
    """
    acceptable = [record for record in records if _is_acceptable(record)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in acceptable:
        grouped.setdefault(record["target_id"], []).append(record)

    tracks: list[dict[str, Any]] = []
    for target_id in sorted(grouped):
        rows = sorted(
            grouped[target_id],
            key=lambda record: (record["timestamp"], record.get("message_seq") or 0),
        )
        for seq_no, record in enumerate(rows, start=1):
            tracks.append({
                "target_id": target_id,
                "timestamp": record["timestamp"],
                "message_seq": record.get("message_seq"),
                "track_sequence_no": seq_no,
                "lat": record.get("lat"),
                "lon": record.get("lon"),
                "altitude": record.get("altitude"),
                "speed": record.get("speed"),
                "heading": record.get("heading"),
            })
    return tracks


def build_current_situation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每个目标保留时间最新的可接受记录；可选字段缺失仍可入选。"""
    acceptable = [record for record in records if _is_acceptable(record)]
    track_length: dict[str, int] = {}
    latest: dict[str, dict[str, Any]] = {}
    for record in acceptable:
        target_id = record["target_id"]
        track_length[target_id] = track_length.get(target_id, 0) + 1
        if target_id not in latest or record["timestamp"] > latest[target_id]["timestamp"]:
            latest[target_id] = record

    situation: list[dict[str, Any]] = []
    for target_id in sorted(latest):
        record = latest[target_id]
        situation.append({
            "target_id": target_id,
            "callsign": record.get("callsign"),
            "latest_time": record["timestamp"],
            "lat": record.get("lat"),
            "lon": record.get("lon"),
            "altitude": record.get("altitude"),
            "speed": record.get("speed"),
            "heading": record.get("heading"),
            "vertical_rate": record.get("vertical_rate"),
            "on_ground": record.get("on_ground"),
            "track_length": track_length[target_id],
            "alt_type": record.get("alt_type"),
            "time_source": record.get("time_source"),
            "message_valid": record.get("message_valid"),
        })
    return situation
