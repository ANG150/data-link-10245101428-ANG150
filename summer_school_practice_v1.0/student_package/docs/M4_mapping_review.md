# M4 AI辅助映射核验说明

- 候选来源：学校预生成候选
- 使用的提示或候选文件：student_package/reference/pre_generated_mapping_candidate.csv
- 发现的字段、单位、层次、有效性或来源问题：
  1. 经纬度对调：候选把 latitude_code 映射为 position.lon、longitude_code 映射为 position.lat，
     正确应为 position.lat 与 position.lon；
  2. 高度偏置错误：候选把 altitude_code 规则写为“乘1米”，正确应为 code-1000（物理偏置1000米）；
  3. status_flags.bit2 语义错误：候选把 bit2 映射到 quality.time_valid 并误认为 bit2=1 表示时间无效，
     正确语义是 timestamp_fallback（时间回退不等于时间无效），应映射到 quality.time_source。
- 人工修订依据：schema/source_field_definitions.md、schema/teaching_message_spec.md、两个字段字典。
- 正式映射条目数：30（每条含单位转换、空值策略、证据与verified标记）。
- 统一态势消息数：6（OpenSky与TeachingLink各来源）。
- 正常样例验证结果：target_id 保留前导0；callsign 有效去除补0；位置与运动按比例因子/偏置恢复。
- 真实零值与缺失值样例验证结果：有效位为0时统一字段为null；协议整数0不自动解释为真实0（高度code=1000表示0米）。
- 不应由大模型自行决定的内容：有效位与协议整数0的区分；message_valid 不扩为来源可信；偏置与比例因子恢复。
