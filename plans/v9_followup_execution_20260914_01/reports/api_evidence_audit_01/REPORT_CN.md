# DeepSeek E 诊断复核

多个视图共享底层问题；以下不是独立天气过程的样本量。

| 模型 | 输入 | 输出方式 | 最终E正确 | 全字段正确 | 格式有效 | 保守费用USD |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| deepseek-flash | full_bundle | direct | 99/126 | 99/126 | 108/126 | 0.07715 |
| deepseek-v4-pro | full_bundle | direct | 78/126 | 78/126 | 111/126 | 0.34496 |
| deepseek-flash | full_bundle | slotwise | 114/126 | 114/126 | 114/126 | 0.09008 |
| deepseek-v4-pro | full_bundle | slotwise | 90/126 | 90/126 | 111/126 | 0.38363 |
| deepseek-flash | focused_slots | direct | 99/126 | 99/126 | 108/126 | 0.02321 |
| deepseek-v4-pro | focused_slots | direct | 74/126 | 74/126 | 110/126 | 0.10512 |
| deepseek-flash | focused_slots | slotwise | 106/126 | 106/126 | 106/126 | 0.02994 |
| deepseek-v4-pro | focused_slots | slotwise | 89/126 | 89/126 | 107/126 | 0.13041 |
