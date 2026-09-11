# 给复查者：DisasterTrace-MM 首个离线种子

建议先读本目录 `IMPLEMENTATION_STATUS.md`，再检查正式的 `build_02`、`diagnostics_02`
和 `finalization_01`。本批没有视觉模型结果，核心问题是数据与测量工具是否成立。

## 最值得检查的地方

1. 同一绝对有效时刻的产品选择是否正确；是否混入 initial/其他阈值/5day 图层。
2. 公布的 native sphere 坐标、点位置、PNG 像素关系与来源几何是否一致。
3. 强度摘录是否确实排除了重复空间字段；必要性证书是否只支持受控文字投影的结论。
4. 私有 GIS/参考、未来 C 查询及未交付图像是否进入正常公开请求或来源定位。
5. 分支缺证、三值逻辑、值保持但依据刷新、纠正自身错误、未知与缺失分母是否正确。
6. 逐轨迹故障是否隔离；已提交无 raw 是否保持 unknown；原始返回是否能独立恢复。
7. 独立 ray-crossing、公开像素程序与主参考是否具有足够不同的故障路径。
8. 七个程序对照的成功/失败是否确实来自预定错误机制，而不是输出格式或额外信息差异。

## 可携带复查包

`MM0_2_REVIEW.zip` 仅包含最终版本需要的代码、四个测试文件、固定依赖、真实来源及任务、
完整程序捕获、验证收据与这份说明。初步开发产物在原批次保留，不混入最终结果表。
ZIP 内的 `PACKAGE_CONTENTS.json` 列出每个成员的 SHA-256。

解压后的目录约定如下：`source/` 是冻结 Python 包；`build/` 对应 `build_02`；
`diagnostics/` 对应 `diagnostics_02`；`tests/` 是本批测试；`review.py` 为原仓库/网络
读取拦截与原始资料重建程序；`requirements.txt` 是实际环境依赖锁定。

在已安装固定依赖的 Python 3.10 环境中，运行：

```bash
PYTHONPATH=source python -m pytest -c pytest-mm.ini -q tests
PYTHONPATH=source python -m disastertrace.multimodal_v1 verify-report \
  --build build --diagnostics diagnostics --receipt report-review.json
```

输出文件必须尚未存在。`review.py` 接收一个原仓库绝对路径；它会禁止读取该目录并禁止
网络，然后在 `rebuilt/` 从 `build/inputs` 重建资料，比较完整文件哈希。它使用 Python
审计钩子验证可信复算过程的依赖边界，不声称具备恶意代码沙箱隔离。

原始 GIS 元数据包含使用范围与局限。所有生成图片明确为官方数据重绘，测试矩形明确为
synthetic，不以这些材料冒充官方原始 PNG 或实测地面风速。环境/许可信息见
`THIRD_PARTY_NOTICES.md`。复查时请将潜在 bug、可复现反例与研究范围局限分别说明。
