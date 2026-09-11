"""Verify the handoff against captured bytes, measured counts and protected baselines."""
import ast
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent.parent
PRIOR=ROOT.parent/'multihazard_source_validation_20260911'
checks=[]
def read(path):
 return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('invalid JSON constant '+x)))
def require(condition,message):
 if not condition:raise AssertionError(message)
 checks.append(message)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def jsonl(path):return [json.loads(x) for x in path.read_text().splitlines() if x]

seed=read(ROOT/'inputs/download_registry.json')
registry=read(ROOT/'SOURCE_REGISTRY.json')['sources']; byid={r['source_id']:r for r in registry}
require(len(registry)==len(byid)==74,'74 unique registry entries, 54 original plus 20 supplements')
require({r['id'] for r in seed['resources']}=={r['source_id'] for r in registry if r['seed_id_preserved']},'original D01-D54 IDs preserved')
require(all(byid[r['id']]['name']==r['name'] for r in seed['resources']),'original source names preserved')
require(all(set(r['axes'])=={'access','content','provenance','license','task_eligibility'} for r in registry),'five independent status axes on every source')
require(all(not r['new_task_admitted'] and r['new_qualified_episode_count']==0 for r in registry),'no new formal task admission inferred from decoding')
require(all(r['capabilities']['C6']=='not_established_historical_availability_null' for r in registry),'strict historical availability remains unestablished')
for r in registry:
 for e in r['evidence']:
  require((ROOT/e['file']).exists(),'evidence file exists: '+r['source_id']+' '+e['file'])

counts=read(ROOT/'DATA_COUNTS.json')
require(counts['event_family_total'] is None,'uncomputed global event count remains null')
require(counts['new_model_calls']==counts['new_gpu_jobs']==0,'no new model or GPU jobs')
require(counts['content_class_counts']==dict(Counter(r['content_evidence'] for r in registry)),'content class totals match source registry')
for m in counts['counts']:
 require(all(k in m for k in ['value','unit','basis','scope','evidence']),'count unit/basis/scope present: '+str(m['source_id'])+' '+m['metric'])
 require(m['value'] is None or isinstance(m['value'],int),'counts are integer or explicitly unknown')

files=jsonl(ROOT/'FILE_MANIFEST.jsonl')
require(len(files)==len({r['path'] for r in files})==counts['file_manifest_entries'],'file manifest paths unique and counted')
for r in files:
 path=REPO/r['path']
 require(path.is_file() and path.stat().st_size==r['bytes'] and digest(path)==r['sha256'],'file bytes and SHA256: '+r['path'])

for root in [PRIOR,ROOT]:
 rs=[read(p) for p in root.glob('attempts/*/response.json')]
 require(len(rs)==counts['network'][root.name]['http_attempts'],'HTTP attempt denominator: '+root.name)
 require(sum(r['captured_bytes'] for r in rs)==counts['network'][root.name]['captured_bytes'],'HTTP captured-byte total: '+root.name)
 scope=read(root/'SCOPE.json')
 require(len(rs)<=scope['max_http_attempts'] and sum(r['captured_bytes'] for r in rs)<=scope['max_captured_response_body_bytes'],'independent request and byte budgets respected: '+root.name)
 require(len(list(root.glob('attempts/*/intent.json')))==len(rs),'all request intents have terminal receipts: '+root.name)

old={r['id']:r for r in read(ROOT/'analysis/DOWNLOADED_AUDIT.json')['reports']}
new={r['id']:r for r in read(ROOT/'analysis/SELECTION_AUDIT.json')['reports']}
require(len(new)==10 and all(r['level']=='verified' for r in new.values()),'10 supplementary content/relationship checks verified')
require(sum(old[k]['details']['records'] for k in ['storm-events-2021-assembled','storm-events-2023-assembled'])==136982,'complete Storm Events annual rows total 136982')
require(new['exebench-coldwave']['details']['source_case_ids']==9 and new['exebench-coldwave']['details']['time_steps']==559,'ExEBench case/time-step units separated')
require(new['ewb-hourly-rowgroup']['details']['decoded_rows']==122880 and new['ewb-hourly-rowgroup']['details']['decoded_rows']<new['ewb-hourly-rowgroup']['details']['object_declared_rows'],'decoded Parquet rows distinguished from footer-declared supply')
require(all(t['flood_pixels']==0 for t in new['geoid-complete-pairs-and-cems']['details']['tiles']),'GEOID sampled bundles do not establish flood-positive coverage')
require(all(t['validity_equals_label_not255'] for t in new['geoid-complete-pairs-and-cems']['details']['tiles']),'GEOID validity dependence on label explicitly identified')
require(all('/NUL_' in x['name'] for x in old['tornet-three-prefix-members']['details']['members']),'TorNet sampled radar files are negative examples')
require(new['droughted-prefix']['details']['fractional_score_rows']==1330,'DroughtED fractional scores are not silently rounded to classes')
require(new['droughted-prefix']['details']['observed_date_max']=='2016-12-31','DroughtED actual train dates checked against metadata conflict')
require(new['weatherqa-spc-product']['details']['issue_time']!=new['weatherqa-spc-product']['details']['analysis_time_referenced'],'SPC analysis and discussion issuance times distinguished')

protected=set(read(ROOT/'REPO_DATA_BASELINE.json')['protected_ids'])
for s in new['cyport-three-storm-bundles']['details']['samples']:
 require(not protected.intersection(s['parts']['txt']['storm_ids']),'new CyPort sample outside protected explicit storm IDs: '+s['source_storm_name'])
risks=read(ROOT/'SPLIT_AND_DEPENDENCY_RISKS.json')
require(set(risks['protected_storm_ids'])==protected,'protected storm union propagated to split-risk registry')
require(new['geoid-complete-pairs-and-cems']['details']['new_disastertrace_split']=='AUDIT_ONLY_ALREADY_OBSERVED','externally heldout GEOID samples remain observed audit material')
require(risks['event_family_count'] is None,'global cross-source event deduplication not falsely declared complete')

hazards=read(ROOT/'HAZARD_COVERAGE.json')
require({r['hazard_id'] for r in hazards}=={f'H{i:02d}' for i in range(1,17)},'all 16 hazard directions recorded')
require(all(r['primary_source_ids'] and r['backup_source_ids'] and r['gaps_cn'] for r in hazards),'each hazard has primary/backup routes and an explicit gap')
require(all(set(r['primary_source_ids']+r['backup_source_ids'])<=byid.keys() for r in hazards),'hazard source references resolve')
st=Counter()
for k in ['storm-events-2021-assembled','storm-events-2023-assembled']:st.update(old[k]['details']['type_counts'])
require(all(r['catalog_report_count']==sum(st[t] for t in r['storm_events_types']) for r in hazards),'hazard report counts recompute from decoded annual files')
require(all('Volcanic Ashfall' not in r['storm_events_types'] for r in hazards),'volcanic ash excluded from weather taxonomy')

manifest=read(ROOT/'NEXT_ACQUISITION_MANIFEST.json')
require(len(manifest['items'])==12,'12 concrete next-acquisition work items')
require(manifest['sum_item_capture_caps_bytes']==sum(r['max_captured_bytes'] for r in manifest['items']),'next-acquisition byte caps recompute')
require(all(r['net_new_event_families'] is None and r['status']=='planned_not_launched' for r in manifest['items']),'future event yield unpromised; next-stage jobs not launched')
for r in manifest['items']:require(set(r['source_ids'])<=byid.keys(),'next-stage source IDs resolve: '+r['id'])
for r in jsonl(ROOT/'BENCHMARK_RAW_LINKS.jsonl'):require(r['benchmark_source_id'] in byid and r['historical_available_at'] is None,'benchmark linkage preserves uncertainty: '+r['link_id'])

baseline=read(PRIOR/'BASELINE.json')
for r in baseline['old_files']:require(digest(REPO/r['path'])==r['sha256'],'protected baseline unchanged: '+r['path'])
for r in read(ROOT/'REPO_DATA_BASELINE.json')['inputs']:
 require(digest(Path(r['path']))==r['sha256'],'user input unchanged: '+Path(r['path']).name)
 require(digest(ROOT/'inputs'/Path(r['path']).name)==r['sha256'],'input snapshot matches original: '+Path(r['path']).name)
correction=read(ROOT/'analysis/SCOPE_METADATA_CORRECTION_01.json')
require(correction['actual_sha256']==digest(ROOT/'inputs/download_registry.json'),'incorrect initial scope digest corrected by preserved amendment')

for p in ROOT.glob('*.py'):ast.parse(p.read_text())
require(True,'all new top-level Python sources parse without executing author code')
required=['DATA_READINESS_REVIEW_CN.md','SOURCE_FEASIBILITY.md','HAZARD_COVERAGE.md','DATA_COUNTS.json','BENCHMARK_RAW_LINKS.jsonl','REUSE_AND_GAPS.md','NEXT_ACQUISITION_MANIFEST.json','CAPABILITY_MATRIX.md','SOURCE_DEPENDENCIES.json','ASSET_REUSE_INDEX.json']
for name in required:require((ROOT/name).stat().st_size>0,'required deliverable present: '+name)
for p in ROOT.glob('*.json'):read(p)
for p in ROOT.glob('*.jsonl'):jsonl(p)
report={'schema':'disastertrace_v6_selection_verification_v1','status':'passed','check_count':len(checks),'checks':checks,
 'required_deliverables':[{'path':name,'sha256':digest(ROOT/name),'bytes':(ROOT/name).stat().st_size} for name in required],
 'limitations':['This verifies the bounded acquisition/selection handoff, not full V6 completion.','Probability sampling, full rights review, event-family deduplication, native image timestamp OCR and task admission remain open.','No inferred representative source success rate or global event count.'],
 'new_gpu_jobs':0,'new_model_calls':0,'new_formal_episodes':0}
(ROOT/'VERIFY_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['checks','required_deliverables']},ensure_ascii=False,indent=2))
