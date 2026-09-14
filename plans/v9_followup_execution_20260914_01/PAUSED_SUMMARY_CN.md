# 本轮暂停与结果汇总

生成时间（UTC）：2026-09-14T13:55:16.023656+00:00

状态：已完成本轮运行并暂停，等待用户检查。

本报告覆盖普通日历 DeepSeek F 评测、单独登记的 Denver 正例诊断，以及完整 2017–2018 温度程序对照。后台不会从这里启动下一轮下载、模型试验、GPU 任务或打开确认周。

## 已完成的基础工作

616 项监测工程测试通过。四区域 3,303 次原生 TAF/METAR 获取完成；清除跨期窗口重叠后，区域基线拟合 9,678 条、校准 2,780 条。原 8 窗口温度程序链完成 64 条轨迹、876 个机会与 280 个唯一目标。

CCI 仅有 2 核/8GiB，F 程序重放迁移至 64 核/256GiB 的 ACP CPU 任务。18 条原轨迹保留，其余 102 条在新节点完成；模型请求并发仍为 4。温度扩展使用单独的 16 核/64GiB CPU 任务，本轮新增 GPU 占用为 0。

## E 证据理解结果

修复后的 E02 完成 1,008 次调用并通过原始响应、参考与费用审计；42 个底层问题生成相依视图。

| 模型 | 完整/直接 | 完整/逐槽 | 聚焦/直接 | 聚焦/逐槽 |
| --- | ---: | ---: | ---: | ---: |
| DeepSeek Flash | 114/126 | 125/126 | 109/126 | 126/126 |
| DeepSeek v4 Pro | 85/126 | 106/126 | 84/126 | 101/126 |

Pro 聚焦逐槽的 25 个错误均为槽位判断全部正确后的最终汇总错误；Flash 完整逐槽的一份格式无效输出仍计入分母。这是固定 thinking disabled 设置下的开发结果，不是模型一般能力排名，也不是未来预测准确率。

## 普通日历的未来报告预测

first and final weekday of registered Jan6-12 calendar; all sites and hourly cutoffs

| 阈值 | 方法 | 已结算/缺失 | 正例机会 | Brier | 相对 FOLLOW 差值 | 新概率提议数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1000m | batch_program | 431/1 | 0 | 0.004460 | 0.000933 | 287 |
| 1000m | copy_baseline | 431/1 | 0 | 0.003527 | 0.000000 | 0 |
| 1000m | copy_current | 431/1 | 0 | 0.003527 | 0.000000 | 0 |
| 1000m | deepseek-flash__batch_predictor | 431/1 | 0 | 0.003527 | 0.000000 | 0 |
| 1000m | deepseek-flash__llm_selector_program | 431/1 | 0 | 0.004242 | 0.000714 | 191 |
| 1000m | deepseek-v4-pro__batch_predictor | 431/1 | 0 | 0.003527 | -0.000000 | 0 |
| 1000m | deepseek-v4-pro__llm_selector_program | 431/1 | 0 | 0.004322 | 0.000795 | 395 |
| 1000m | follow | 431/1 | 0 | 0.003527 | 0.000000 | 0 |
| 5000m | batch_program | 431/1 | 47 | 0.069353 | 0.005048 | 208 |
| 5000m | copy_baseline | 431/1 | 47 | 0.064305 | 0.000000 | 0 |
| 5000m | copy_current | 431/1 | 47 | 0.064305 | 0.000000 | 0 |
| 5000m | deepseek-flash__batch_predictor | 431/1 | 47 | 0.064305 | 0.000000 | 0 |
| 5000m | deepseek-flash__llm_selector_program | 431/1 | 47 | 0.068081 | 0.003776 | 167 |
| 5000m | deepseek-v4-pro__batch_predictor | 431/1 | 47 | 0.064305 | 0.000000 | 0 |
| 5000m | deepseek-v4-pro__llm_selector_program | 431/1 | 47 | 0.066889 | 0.002584 | 301 |
| 5000m | follow | 431/1 | 47 | 0.064305 | 0.000000 | 0 |

Brier 越低越好，负差值表示损失下降。“新概率提议”仅指与可见当前值和基线值都相差超过 0.005 的提议，不能单独证明新信息或最终生效。两个阈值、多个站点与相邻时段存在依赖。

## Denver 正例机制诊断

outcome-selected exploratory mechanism diagnostic: entire Denver Jan9 day containing all three previously exposed 1km positives; no future label in policy requests; not natural prevalence

| 阈值 | 方法 | 已结算/缺失 | 正例机会 | Brier | 相对 FOLLOW 差值 | 新概率提议数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1000m | batch_program | 72/0 | 3 | 0.038161 | -0.001493 | 48 |
| 1000m | copy_baseline | 72/0 | 3 | 0.039654 | 0.000000 | 0 |
| 1000m | copy_current | 72/0 | 3 | 0.039654 | 0.000000 | 0 |
| 1000m | deepseek-flash__batch_predictor | 72/0 | 3 | 0.039654 | 0.000000 | 0 |
| 1000m | deepseek-flash__llm_selector_program | 72/0 | 3 | 0.038075 | -0.001579 | 66 |
| 1000m | deepseek-v4-pro__batch_predictor | 72/0 | 3 | 0.039654 | 0.000000 | 0 |
| 1000m | deepseek-v4-pro__llm_selector_program | 72/0 | 3 | 0.037827 | -0.001827 | 72 |
| 1000m | follow | 72/0 | 3 | 0.039654 | 0.000000 | 0 |
| 5000m | batch_program | 72/0 | 11 | 0.136583 | -0.001439 | 48 |
| 5000m | copy_baseline | 72/0 | 11 | 0.138021 | 0.000000 | 0 |
| 5000m | copy_current | 72/0 | 11 | 0.138021 | 0.000000 | 0 |
| 5000m | deepseek-flash__batch_predictor | 72/0 | 11 | 0.138021 | 0.000000 | 0 |
| 5000m | deepseek-flash__llm_selector_program | 72/0 | 11 | 0.135560 | -0.002462 | 60 |
| 5000m | deepseek-v4-pro__batch_predictor | 72/0 | 11 | 0.138021 | 0.000000 | 0 |
| 5000m | deepseek-v4-pro__llm_selector_program | 72/0 | 11 | 0.135428 | -0.002594 | 72 |
| 5000m | follow | 72/0 | 11 | 0.138021 | 0.000000 | 0 |

Brier 越低越好，负差值表示损失下降。“新概率提议”仅指与可见当前值和基线值都相差超过 0.005 的提议，不能单独证明新信息或最终生效。两个阈值、多个站点与相邻时段存在依赖。

## 温度完整历史

按 24 个自然月完成 192 条程序轨迹、11644 个目标机会、3645 个唯一目标，独立评分复核通过。来源为 EUPP 51 成员日极值和 DWD 原生参考；没有温度模型调用。

| 事件 | 唯一目标 | 可结算 | 正例目标 |
| --- | ---: | ---: | ---: |
| fixed_threshold_hot_spell_3d | 729 | 727 | 8 |
| fixed_threshold_ice_spell_3d | 729 | 727 | 10 |
| frost_day | 729 | 729 | 113 |
| hot_day | 729 | 729 | 22 |
| ice_day | 729 | 729 | 27 |

## 费用与保留问题

| 批次 | 账本尝试 | 已结算 | 未知/待定 | 峰时费用上界USD | 未决预留USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| api_compatibility_01 | 2 | 2 | 0 | 0.000085 | 0.000000 |
| api_evidence_01 | 938 | 876 | 62 | 1.184498 | 1.692672 |
| api_evidence_02 | 1008 | 1008 | 0 | 1.350812 | 0.000000 |
| api_pilot_01 | 2304 | 2304 | 0 | 9.022021 | 0.000000 |
| api_rare_pilot_01 | 384 | 384 | 0 | 1.510706 | 0.000000 |

费用按保存的峰时价和未命中缓存输入计算，属于保守估计，不是服务商账单。首次 E01 因 AFS 文件锁竞争出现采集失败；其原始响应、失败和未知费用预留全部保留，模型排名使用完整 E02。

当前限制：历史首次公开时间仍未被证明；自然日历的严格低能见度正例少；按结果选择的 Denver 诊断单独报告；过程相关块不等于独立天气系统；API 服务端计算未知；尚无 16 类灾害的完整模型评价。

## 等待你决定的后续工作

优先审阅本轮 F 是否超过 FOLLOW/COPY/证据映射强基线，以及改好、改坏和回退各占多少。之后再决定是否扩充独立正例过程、比较逐槽汇总的 E/F 管线、启用持久修订协议，以及接入温度模型。以上均尚未自动启动。

详细记录：`RUN_REPORT_CN.md`、`reports/api_forecast_audit_01/VALIDATION.json`、`reports/api_rare_forecast_audit_01/VALIDATION.json`、`reports/e_error_mechanisms_01/REPORT_CN.md`、`reports/temperature_fullcalendar_audit_01/REPORT_CN.md`。
