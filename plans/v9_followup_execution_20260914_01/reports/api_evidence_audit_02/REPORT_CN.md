# DeepSeek E 诊断复核

多个视图共享底层问题；以下不是独立天气过程的样本量。

| 模型 | 输入 | 输出方式 | 最终E正确 | 全字段正确 | 格式有效 | 保守费用USD |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| deepseek-flash | full_bundle | direct | 114/126 | 114/126 | 126/126 | 0.09019 |
| deepseek-v4-pro | full_bundle | direct | 85/126 | 85/126 | 126/126 | 0.39686 |
| deepseek-flash | full_bundle | slotwise | 125/126 | 125/126 | 125/126 | 0.09793 |
| deepseek-v4-pro | full_bundle | slotwise | 106/126 | 106/126 | 126/126 | 0.42872 |
| deepseek-flash | focused_slots | direct | 109/126 | 109/126 | 126/126 | 0.02754 |
| deepseek-v4-pro | focused_slots | direct | 84/126 | 84/126 | 126/126 | 0.12122 |
| deepseek-flash | focused_slots | slotwise | 126/126 | 126/126 | 126/126 | 0.03530 |
| deepseek-v4-pro | focused_slots | slotwise | 101/126 | 101/126 | 126/126 | 0.15306 |
