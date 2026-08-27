# M6综合运行说明

## 基本信息

- 姓名：（待填写）
- 学号：10245101428
- GitHub用户名：ANG150
- Python版本：3.10+
- 是否使用SQLite：是
- M4候选来源：学校预生成候选

## 安装与运行

先按课程包 `environment/README_environment.md` 建立独立 `.venv`。在课程包根目录清空 `student_package/output/` 后执行：

```powershell
.\.venv\Scripts\python.exe student_package\src_skeleton\run_all.py
```

## 程序入口

统一入口为 `student_package/src_skeleton/run_all.py` 的 `run_pipeline()`，按顺序调用：

1. `parse()`：M2 OpenSky 解析
2. `encode()`：M2 TeachingLink 消息封装
3. `decode_validate()`：M2 解码与帧验证
4. `build_tracks()`：M3 航迹与当前态势（含 OpenSky 真实数据验证）
5. `map_unified()`：M4 语义映射与统一消息
6. `check_quality()`：M5 一致性检查
7. `export_results()`：M6 关键成果汇总

各模块核心函数位于 `m2_protocol.py`、`m3_tracks.py`、`m4_mapping.py`、`m5_quality.py`。

## 输入文件

- M2：`student_package/data/raw_states.json`
- M3：`student_package/data/partner_messages_multitime.bin`、`student_package/data/opensky_real/normalized_state_vectors.csv`
- M4：`student_package/output/current_situation.csv`（M3 产物）、`student_package/data/m4/partner_current_situation.csv`、`student_package/reference/pre_generated_mapping_candidate.csv`
- M5：`student_package/data/m5/anomaly_cases.csv`、`student_package/data/m5/anomaly_rules.csv`

## 输出文件

- 消息编解码：`output/encoded_messages.bin`、`output/decoded_partner_states.csv`、`output/validation_log.csv`、`output/roundtrip_report.csv`
- 航迹与当前态势：`output/decoded_multitime.csv`、`output/track_table.csv`、`output/current_situation.csv`、`output/states.db`（选做）、`output/opensky_real/`（真实数据验证 9 文件）
- 语义映射：`output/llm_mapping_candidate.csv`、`output/verified_mapping_table.csv`、`output/unified_situation.ndjson`
- 一致性检查：`output/alert_log.csv`、`output/quality_situation.csv`
- 说明材料：`docs/M4_mapping_review.md`、`docs/M5_result_note.md`

## 实验结果

- M2：5 条 OpenSky 状态向量，其中 3 条通过量程检查编码为 3 帧（时间缺失、航向越界各 1 条被拒绝），解码 3 帧全部成功（`message_valid=True`），往返误差均在一个量化单位内。
- M3：9 帧多时刻消息全部解码，3 个目标各 3 条航迹记录（`track_sequence_no` 从 1 连续），当前态势 3 个目标；真实 OpenSky 数据 71 条全部编码解码成功、形成 24 个目标。
- M4：30 条人工核验正式映射，生成 6 条统一态势消息（OpenSky 与 TeachingLink 各 3 条），同一目标两种来源关键字段一致。
- M5：4 条告警（位置缺失 HIGH 1 条，延迟、重复、航向越界 MEDIUM 各 1 条），质量态势 6 行（1 ERROR、3 WARNING、2 NORMAL）。

## 已知限制

- TeachingLink 为学校自定义教学协议，不对应 ASTERIX、ADS-B/Mode-S、Link 16 等真实装备协议；`message_valid` 仅表示帧通过格式与校验检查，不代表来源真实性与安全完整性。
- 数据均为离线快照；M3 假定帧起始边界已对齐，不处理失步重同步。
- M4 使用学校预生成候选并人工核验，未调用在线大模型。
- SQLite 与航迹图为选做内容，不构成必做前置条件。

## 最终提交信息

- 仓库链接：https://github.com/ANG150/data-link-10245101428-ANG150.git
- 最终commit ID：（提交后登记）
- 最后检查日期：2026-08-27
