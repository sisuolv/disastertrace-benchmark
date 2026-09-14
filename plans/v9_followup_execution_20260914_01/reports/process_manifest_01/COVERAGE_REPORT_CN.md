# 真实数据覆盖与切分

本表只统计 1h 提前量；阈值共享观测，不能相加作为独立天气过程。
分组是保守时间/版本相关块，尚不是经天气系统识别确认的独立过程。

| 区域 | 用途 | 阈值 m | 目标 | 正例 | 负例 | 缺失 | 相关块 | 正例块 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bay | development_evaluation | 1000 | 576 | 0 | 576 | 0 | 1 | 0 |
| bay | development_evaluation | 5000 | 576 | 19 | 557 | 0 | 1 | 1 |
| chicago | development_evaluation | 1000 | 504 | 0 | 504 | 0 | 1 | 0 |
| chicago | development_evaluation | 5000 | 504 | 49 | 455 | 0 | 1 | 1 |
| denver | development_evaluation | 1000 | 504 | 3 | 497 | 4 | 1 | 1 |
| denver | development_evaluation | 5000 | 504 | 45 | 455 | 4 | 1 | 1 |
| new_york | development_evaluation | 1000 | 504 | 0 | 504 | 0 | 1 | 0 |
| new_york | development_evaluation | 5000 | 504 | 16 | 488 | 0 | 1 | 1 |

全部历史首次可见时间仍采用声明情景。保留确认周未读取。
当前块数不能支持把数千目标作为独立样本。扩展日期须预注册，按完整过程报告。
