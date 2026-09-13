# W1B 历史水文版本小样例

**已获得 2024 年真实历史的同站、同原始参数、连续两次集合预报，并与历史 USGS 瞬时流量做了时间戳连接。** 本轮不再只有当前 HEFS/NWPS 数据；但预报与观测的完整物理语义等价性仍未核准，未准入连续量正式评分，亦未完成水位／洪水阈值合同或证明 2024 年的首次公开可获取时刻。

## 实测结果

| 数据 | 本轮真实结果 | 解释边界 |
|---|---|---|
| HEFS API：SCOC1 / QINE，2024-01-01、02 12 UTC | 两个 ensemble 查询及一个 headers 查询均 HTTP 200，但内容为 `[]` | 说明这些精确查询没取到数据，不能据此断言所有历史日期或全部 HEFS 档案不存在 |
| CNRFC 官方 hourly ZIP archive，2024010112 与 2024010212 | 两个 ZIP CRC 通过；每个 43 列 SCOC1 轨迹 × 721 小时；参数 QINE | 提供 2024 历史逐小时 QINE 集合预报；采样间隔本身不证明瞬时／小时平均支持，CSV 轨迹没有显式成员 ID |
| 同一有效时刻的版本关系 | 两个周期重叠 697 个小时，697 个完整预报向量均发生变化 | 这是实际版本改变，不是人为扰动；不能直接推断新版更好 |
| USGS-11477000，00060，2024-01-02 12 UTC 至 01-04 12 UTC | 193 条 15 分钟数据；statistic_id=00011，单位 ft³/s，全部 Approved；无分页 | 每个预报版本各有 49 个精确小时级观测匹配；当前批准状态不等于当年即时公开状态 |
| 固定小样例 | 每个版本取 Jan 02、03、04 12 UTC，合计 6 对；5 对严格正时效，1 对时效 0 | 完整保留该时效 0 边界，不把它算未来预测 |
| CNRFC NorthCoast daily ZIP archive，同两日 | 各 366 日、17 个原始站点标识、每标识 43 列轨迹；ZIP CRC 通过 | daily 参数 SQME；不能替代 hourly QINE，也未与瞬时 USGS 值混合结算 |

这次新增不足 5 MB HTTP 响应数据，未运行模型、API 推理或 GPU。具体字节数以 `FETCH_SUMMARY.json` 为准。`ARCHIVE_VALIDATION.json` 与 `archive_flow_pairs.json` 可直接复查数值和合同边界。

## 来源与身份规则

历史 archive 路径来自官方 CNRFC `ensembleProduct.php` 的取数代码。原先尝试的 `prodID=1&date=20240101` 页面实际仍展示 2026 当前图；没有因 URL 含 20240101 就判定历史成功。随后在支持历史日期的 `prodID=4`、`prodID=8` 页面确认 archive 路径，并直接下载 ZIP，核对内部文件名、首个 GMT 时间、每行时刻与字段。

hourly 源路径示例：

```text
https://www.cnrfc.noaa.gov/csv/2024010112_SCOC1_hefs_csv_hourly.csv.zip
```

daily 源路径示例：

```text
https://www.cnrfc.noaa.gov/csv/2024010112_NorthCoast_hefs_csv_daily.zip
```

hourly QINE 原单位由官方页面的 CSV 单位说明及读取代码绑定为 kcfs。`kcfs × 1000 = ft³/s` 是流量单位转换；水位 ft 不能用这个乘数转换为流量，当前 minor flood stage=51 ft 也不能套到 QINE 上。

另行下载的官方 `ensembleHourlyProductCSV.php` 在 Note 1 明确单位 kcfs，阈值产品说明明确它使用逐小时 streamflow time series；但这两份说明未在本轮核准该历史 SCOC1 QINE 的瞬时／小时平均支持定义及调蓄／还原口径。USGS `00060`、`00011`、ft³/s 已核准的是观测侧语义。时间戳相同、单位可换算、站名一致不足以替代预报侧合同。因此 `forecast_vs_usgs_quantity_equivalence_verified`、`forecast_regulation_mode_verified`、`continuous_numeric_scoring_qualified` 均为 false。

当前官方 CSV 文档说 44 成员、对应 1980–2023 年，但下载的两个 2024 历史文件实际都是 43 列。不能把当前文档的成员年份映射直接回填到旧档案；本轮只保存列位置，没有杜撰缺失成员。

daily ZIP 同时包含 `SCOC1` 和 `SCOC1F`，各自都是 43 列，但数值不同。官方页面的一段展示代码会把 F 后缀剥离后选列；本次验证器保留完整原始标识，未把二者合并为 86 个同质成员。daily 页面还说明 full-natural/unregulated、mean daily 等产品语义，后续必须确认各原始标识和变量的具体含义；不能仅按地名或被规范化的站号合并。

## 仍然缺什么

1. **历史可用时刻。** 文件名前缀和第一行建立名义周期，并不证明历史首次公开时刻。archive 页面有名义发行时间字符串，当前下载有当前 receipt；二者都不能自动变成当年的精确 `available_at`。小样例明确保留 null。
2. **洪水命题合同。** 当前官方 metadata 的 flow 阈值仍缺失。完成“未来瞬时流量数值”不等于完成“未来是否超过 minor flood 水位”。需要历史适用的原生水位预报／同基准观测，或者版本适用的官方流量阈值／rating relation。
3. **成员身份和校准。** CSV 只有列位置；跨周期向量整体可比较，不应在未核对轨迹年标签前解释单个成员路径。集合频率是原始专业基线，不自动成为已校准的洪水概率。
4. **C1 自然共享。** NorthCoast ZIP 确实是一个涵盖多个目标的原始共享资产；但共同专业基线本就应免费给所有方法。该 ZIP 的存在不能证明“补充证据共享”产生模型调度价值，也不表示 17 个原始标识就是 17 个独立灾害过程。
5. **C2 与 E/F。** 已验证字段、版本与目标有效时间，可以开发版本识别 E 任务；尚未建立一个带截止、预算和可达支持集的完整过程实验，更没有得到 F 增益结果。

6. **物理目标等价性。** 下一步先核准历史 hourly QINE 的时域支持和调蓄口径，再决定能否用这批 Approved USGS 值结算连续量。相同有效时刻连接成功仍只是一项工程检查。旧报告中的 NRWI4、CRHA2、SCOC1 分别在 Iowa、Alaska、California；本次单独核验 Scotia，不把三个站宣称为同流域。

## 对下一轮的建议

保持 v7 方向，把水文步骤拆成两个明确出口：先使用这些历史 QINE 版本做数值／版本合同测试；洪水告警准入继续保留独立阈值与历史基准门槛。与已验证的 EUPP 温度点目标共同扩展类型接口，不等待水位阈值才能推进所有数值开发。

回放如采用保守发布日期假设，须另设 assumption track 并在所有策略共用，不能把假设标签升级为真实在线时间证据。新数据也不能直接覆盖之前 2026 provisional observation 的冻结副本。

## 本地复现

```bash
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
python plans/v7_execution_20260913/hydrology/verify_archives.py
```

验证器只读取本轮保存的 ZIP 与 USGS JSON，不联网。预报放在 `model_visible`，观测放在 `evaluator_only`；所有小样例 `formal_monitoring_eligible=false`。当前新增正式 H08 monitoring 准入数为 0。
