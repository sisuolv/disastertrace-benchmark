# 真实数据覆盖与切分

本表只统计 1h 提前量；阈值共享观测，不能相加作为独立天气过程。
分组是保守时间/版本相关块，尚不是经天气系统识别确认的独立过程。

| 区域 | 用途 | 阈值 m | 目标 | 正例 | 负例 | 缺失 | 相关块 | 正例块 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bay | calibration | 1000 | 348 | 0 | 347 | 1 | 1 | 0 |
| bay | calibration | 5000 | 348 | 14 | 333 | 1 | 1 | 1 |
| bay | development_evaluation | 1000 | 576 | 0 | 576 | 0 | 1 | 0 |
| bay | development_evaluation | 5000 | 576 | 19 | 557 | 0 | 1 | 1 |
| bay | fit | 1000 | 1212 | 31 | 1181 | 0 | 1 | 1 |
| bay | fit | 5000 | 1212 | 82 | 1130 | 0 | 1 | 1 |
| bay | purged | 1000 | 672 | 5 | 666 | 1 | 1 | 1 |
| bay | purged | 5000 | 672 | 67 | 604 | 1 | 1 | 1 |
| chicago | calibration | 1000 | 348 | 9 | 339 | 0 | 1 | 1 |
| chicago | calibration | 5000 | 348 | 80 | 268 | 0 | 1 | 1 |
| chicago | development_evaluation | 1000 | 504 | 0 | 504 | 0 | 1 | 0 |
| chicago | development_evaluation | 5000 | 504 | 49 | 455 | 0 | 1 | 1 |
| chicago | fit | 1000 | 1212 | 19 | 1193 | 0 | 1 | 1 |
| chicago | fit | 5000 | 1212 | 94 | 1118 | 0 | 1 | 1 |
| chicago | purged | 1000 | 672 | 8 | 664 | 0 | 1 | 1 |
| chicago | purged | 5000 | 672 | 63 | 609 | 0 | 1 | 1 |
| denver | calibration | 1000 | 354 | 0 | 353 | 1 | 1 | 0 |
| denver | calibration | 5000 | 354 | 0 | 353 | 1 | 1 | 0 |
| denver | development_evaluation | 1000 | 504 | 3 | 497 | 4 | 1 | 1 |
| denver | development_evaluation | 5000 | 504 | 45 | 455 | 4 | 1 | 1 |
| denver | fit | 1000 | 1218 | 1 | 1208 | 9 | 1 | 1 |
| denver | fit | 5000 | 1218 | 8 | 1201 | 9 | 1 | 1 |
| denver | purged | 1000 | 660 | 0 | 651 | 9 | 1 | 0 |
| denver | purged | 5000 | 660 | 0 | 651 | 9 | 1 | 0 |
| new_york | calibration | 1000 | 342 | 10 | 332 | 0 | 1 | 1 |
| new_york | calibration | 5000 | 342 | 49 | 293 | 0 | 1 | 1 |
| new_york | development_evaluation | 1000 | 504 | 0 | 504 | 0 | 1 | 0 |
| new_york | development_evaluation | 5000 | 504 | 16 | 488 | 0 | 1 | 1 |
| new_york | fit | 1000 | 1206 | 38 | 1168 | 0 | 1 | 1 |
| new_york | fit | 5000 | 1206 | 123 | 1083 | 0 | 1 | 1 |
| new_york | purged | 1000 | 684 | 12 | 672 | 0 | 1 | 1 |
| new_york | purged | 5000 | 684 | 80 | 604 | 0 | 1 | 1 |

全部历史首次可见时间仍采用声明情景。保留确认周未读取。
当前块数不能支持把数千目标作为独立样本。扩展日期须预注册，按完整过程报告。
