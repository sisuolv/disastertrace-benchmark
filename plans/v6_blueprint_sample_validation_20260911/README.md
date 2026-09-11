# 两份整体蓝图的整合方案与真实数据样例核验

2026-09-11。建议先阅读 [整体方案](OVERALL_PLAN_REFINED_CN.md)，再按灾种或数据源查看细表。

| 文件 | 用途 |
| --- | --- |
| [OVERALL_PLAN_REFINED_CN.md](OVERALL_PLAN_REFINED_CN.md) | 完整研究定位、16 类灾害、来源决策、处理、自动结算、抽样、novelty、基线和全周期交付 |
| [HAZARD_SOURCE_MATRIX.md](HAZARD_SOURCE_MATRIX.md) | 每类的固定未来目标、结果类型、来源、时间尺度、处理与缺口 |
| [SOURCE_SAMPLE_INVENTORY.md](SOURCE_SAMPLE_INVENTORY.md) | 逐项实际样例和选择；97 个登记/产品条目不是独立数据集数量 |
| [HAZARD_SOURCE_MATRIX.json](HAZARD_SOURCE_MATRIX.json) / [CSV](HAZARD_SOURCE_MATRIX.csv) | 16 类合同的机器可读表 |
| [SOURCE_SAMPLE_INVENTORY.json](SOURCE_SAMPLE_INVENTORY.json) / [CSV](SOURCE_SAMPLE_INVENTORY.csv) | 实际 URL、回执、继承证据指针、取样状态与限制 |
| [CAPTURE_SUMMARY.json](CAPTURE_SUMMARY.json) | 本轮 125 请求、94,916,311 响应字节，31 条科学内容解析与 2 条渲染图记录的计数口径 |
| [NEW_SAMPLE_AUDIT_05.json](NEW_SAMPLE_AUDIT_05.json) | 本轮最终科学解析；33 条记录中没有解码异常，不等于科学语义/任务准入全通过 |
| [ASSEMBLY_MANIFEST.json](ASSEMBLY_MANIFEST.json) | OFS 与 CPC 完整文件的分段绑定、偏移、原始回执与 SHA256 |
| [INHERITED_SAMPLE_AUDIT.json](INHERITED_SAMPLE_AUDIT.json) | 既有 375 文件完整性检查；复用旧科学解码结论 |
| [INHERITED_JOIN_BINDINGS.json](INHERITED_JOIN_BINDINGS.json) | NHC/水文连接审计的 78 文件绑定；与前表可有重叠 |
| [INPUT_BINDINGS.json](INPUT_BINDINGS.json) | 两份输入蓝图、旧方案及原有修改文件/index 的检查依据 |
| [VERIFY_REPORT.json](VERIFY_REPORT.json) | 本目录最终完整性、引用和原状态保护检查 |
| [ARTIFACT_MANIFEST.json](ARTIFACT_MANIFEST.json) | 交付文件哈希目录，排除局部依赖包、缓存及自引用的清单/验证报告 |

## 本轮边界

实际样例包括站点记录、未来 GRIB 字段、雷达体扫、卫星数组、航空预报/观测、冻雨/沙尘历史正例、干旱指数/展望、OFS 数组、P-ETSS 数值表。全部原始响应和逐请求回执在 `captures_01/` 至 `captures_10/`，失败或不完整响应同样保留。分段成功组装的文件在 `assembled/`。

HTTP 200 不等于科学数据成功；例如 EFFIS 和一次 GWIS 点值请求为空。CAMS/GloFAS/EFAS/SMAP/IMERG 本次匿名访问需要认证；M4Fog 无原生 cube；TorNet 新归档前缀无完整成员。旧资料若已经有可靠样例则复核哈希，避免为了重复下载而夸大新增验证。

本轮新正式任务数、模型调用数和 GPU 作业数均为 0。没有自动提交 Git 或推送 GitHub。原有工作区修改与暂存内容通过绑定检查保护。

## 复现与审计历史

`capture_samples.py` 是有界下载器，`probe_spec_01.json` 至 `probe_spec_10.json` 保存全部请求；重试时使用新的空目录名，旧目录不可覆盖。`PROBE_INTENT.json` 固定累计响应上限、单请求上限和 4 路下载并发。这是 CPU/网络取样并发，不是 GPU 作业。

`audit_new_samples.py` 使用 ecCodes、netCDF4、NumPy、rasterio、pyshp、Pillow 和 MetPy。GHCNh 文档另使用 pypdf 读取。主解析依赖复用本机的 `/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911`，局部 `parser_libs/` 补充 MetPy 1.7.1、pint 0.24.4、flexcache 0.3、flexparser 0.4、pyproj 3.7.1、pypdf 6.18.1。局部依赖安装目录不进入交付资产清单。解析脚本只关闭 CPU 解码不需要的 CuPy 导入，避免主机可选包与 NumPy 2 的冲突，没有修改主机全局环境。

在当前工作区可复核，无需模型 API：

```bash
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next
python plans/v6_blueprint_sample_validation_20260911/verify_delivery.py
```

如需重跑科学解码，指定一个尚不存在的新输出路径，保留原审计结果：

```bash
PYTHONPATH=plans/v6_blueprint_sample_validation_20260911/parser_libs:/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911 \
python plans/v6_blueprint_sample_validation_20260911/audit_new_samples.py \
  --output plans/v6_blueprint_sample_validation_20260911/NEW_SAMPLE_AUDIT_RECHECK.json
```

以上命令依赖本机解析环境；跨机器先安装列出的包并记录版本。`build_plan_tables.py` 是显式来源/灾种决策的可再生表构建器，固定读取最终 `NEW_SAMPLE_AUDIT_05.json`，不会自动采纳任何后来的审计文件。

审计演进保留如下，最终引用统一采用 05：

- `AUDIT_ATTEMPT_01_FAILURE.json`：首次严格 JSON 导出遇到非有限元数据；未产生 01 报告，随后改为显式标记非有限值。
- `NEW_SAMPLE_AUDIT_02.json`、`NEW_SAMPLE_AUDIT_03.json`：中间结果，P-ETSS 未完整识别带负尾码或小写 est 的位置头，位置块数/长度不能引用。
- `NEW_SAMPLE_AUDIT_04.json`：修复 P-ETSS，逐位置严格校验 102 个数值，290 个唯一位置；还不含之后取得的 MRMS QPE。
- `NEW_SAMPLE_AUDIT_05.json`：加入 MRMS QPE 后的完整最终结果。NEXRAD unknown message 32、MRMS unknown 单位等限制仍明确保留。

本目录的样例、发现和计划可供研究复查；数据再分发仍需按来源条款逐项落实，尤其既有第三方 benchmark。可访问、可解码、可作为当时输入、可自动结算及可再分发分别登记。
