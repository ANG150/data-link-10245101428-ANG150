# M5 异常结果说明

- 批次时间：1710000120
- 四类必做规则是否均运行：是（R1位置缺失、R2延迟、R3重复、R4航向越界）
- 告警总数及按类型统计：共4条，DATA_DELAYED=1、DUPLICATE_RECORD=1、HEADING_OUT_OF_RANGE=1、POSITION_MISSING=1
- HIGH/MEDIUM 数量：HIGH=1，MEDIUM=3
- 正常记录是否被误报：否（ERROR=1，WARNING=3，NORMAL=2）
- heading=360 与 heading为空的处理：heading=360按越界处理（HEADING_OUT_OF_RANGE）；heading为空不触发该规则。
- 字段缺失、帧验证失败、来源真实性三者的区别：字段缺失由有效位为0表示；帧验证失败指帧未通过接收判据；两者都不代表来源真实性。
