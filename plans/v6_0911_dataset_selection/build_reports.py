"""Build a selection registry, coverage matrices and plans from measured audit outputs."""
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent.parent
PRIOR=ROOT.parent/'multihazard_source_validation_20260911'
def read(p): return json.loads(p.read_text())
def write(name,obj): (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def lines(name,rs): (ROOT/name).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rs))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def md(name,s): (ROOT/name).write_text(s.strip()+'\n')
def table(head,rs): return '| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+''.join('| '+' | '.join(str(v).replace('|','/') .replace('\n',' ') for v in r)+' |\n' for r in rs)

seed=read(ROOT/'inputs/download_registry.json')
old={r['id']:r for r in read(ROOT/'analysis/DOWNLOADED_AUDIT.json')['reports']}
new={r['id']:r for r in read(ROOT/'analysis/SELECTION_AUDIT.json')['reports']}
inherit=read(PRIOR/'analysis/INHERITED_SAMPLES.json')
decisions={r['source_id']:r for r in read(ROOT/'SOURCE_DECISIONS.json')}
source_map={
 'nhc_operational':'D01','sevir':'D06','ibtracs':'D02','digital_typhoon_v2':'D03','tcir':'D04','noaa_storm_events':'D05','tornet':'D07','gfd':'D11','geoid':'D12','sen1floods11':'D15','wildfirespreadts':'D19','next_day_fire':'D20','ts_satfire':'D21','firms':'D23','ghcnd':'D26','isd':'D27','gfs':'D28','chirps3':'D30','usdm':'D31','merra2_aerosol':'D35','coops':'D37','oisst':'D38','emdat':'D39','xbd':'D44','crisismmd':'D45','landslide4sense':'D46','earthextreme':'D47','ewb':'D48','worldfloods_v2':'D51','cllmate':'D54',
 'snodas':'D55','usgs_water_nims':'D56','nwps':'D57','ndbc':'D58','meteonet':'D59','caravan':'D60','hanze':'D61','dheed':'D62','dawn':'D63','senforflood':'D64','fpa_fod6':'D65','weatherbench2':'D66','era5':'D66','hrrr':'D67','hko':'D68','hko7':'D68','gesla3':'D69','gesla_current':'D69','eswd':'D70','camelsh':'D71','msetcd':'D72','cma_besttrack':'D73','billion_dollar':'D74'
}
supp_names=['SNODAS SWE','USGS Water Data','NWPS Stageflow','NDBC Buoys','MeteoNet','Caravan','HANZE v2.1','Dheed','DAWN','SenForFlood','FPA-FOD6','WeatherBench2 ERA5','HRRR','HKO-7','GESLA current / GESLA-3 candidate','ESWD','CAMELSH','MSETCD / MSCAR','CMA Best Track','NOAA Billion-Dollar Disasters']
prior_candidates=read(PRIOR/'CANDIDATES.json')['sources']
registry={r['id']:{'source_id':r['id'],'name':r['name'],'hazards_reported':r['hazards'],'registered_urls':[v['url'] for v in r['links']],
 'reported_supply':{'value':r.get('previous_scale_note'),'basis':'reported_in_user_v6_registry_not_locally_counted'},'seed_id_preserved':True} for r in seed['resources']}
for i,n in enumerate(supp_names,55):
 sid=f'D{i:02d}';prior=[r for r in prior_candidates if source_map.get(r['id'])==sid]
 registry[sid]={'source_id':sid,'name':n,'hazards_reported':prior[0]['hazards'] if prior else [],'registered_urls':prior[0]['urls'] if prior else [],'reported_supply':None,'seed_id_preserved':False}

captures=[]; attempts=[]; files=[]
for root in [PRIOR,ROOT]:
 specs={s['id']:s for p in sorted(root.glob('specs/*.json')) for s in read(p).get('probes',[])}
 for p in sorted(root.glob('batches/*/*.json')):
  r=read(p)
  if 'final' not in r: continue
  s=specs.get(r['id'],{}); rawsid=s.get('source');sid=source_map.get(rawsid,rawsid if rawsid in registry else None)
  z=r['final'];response_path=str((root/z['attempt_path']/'response.json').relative_to(REPO))
  captures.append({'capture_id':r['id'],'bundle':root.name,'source_id':sid,'source_label':rawsid,'kind':s.get('kind',r['kind']),'original_url':r['requested_url'],
    'http_status':z['http_status'],'response_complete':z['complete'],'body_bytes':z['captured_bytes'],'body_sha256':z['body_sha256'],'response_path':response_path,
    'body_path':str((root/z['attempt_path']/'body.bin').relative_to(REPO)),'attempt_paths':[str((root/v).relative_to(REPO)) for v in r['attempt_paths']]})
 for path in sorted(root.glob('attempts/*/response.json')):
  z=read(path);bp=path.parent/'body.bin'
  assert digest(bp)==z['body_sha256'] and bp.stat().st_size==z['captured_bytes']
  attempts.append({'bundle':root.name,'bytes':z['captured_bytes'],'status':z['http_status'],'complete':z['complete']})
  files.append({'path':str(bp.relative_to(REPO)),'sha256':z['body_sha256'],'bytes':z['captured_bytes'],'role':'http_capture',
    'retrieved_at':z['finished_at'],'historical_available_at':None,'http_response_complete':z['complete'],
    'whole_http_object':bool(z['complete'] and z['http_status']==200),'http_status':z['http_status'],'task_admitted':False})
 for pattern in ['archive_runs/*/member_*.bin','samples/*','assemblies/completion_01/*.bin','references/*']:
  for p in sorted(root.glob(pattern)):
   if p.is_file(): files.append({'path':str(p.relative_to(REPO)),'sha256':digest(p),'bytes':p.stat().st_size,'role':'derived_or_extracted_asset','historical_available_at':None,'task_admitted':False})
for path,info in inherit['files'].items():
 p=REPO/path;assert digest(p)==info['sha256'];files.append({'path':path,**info,'role':'inherited_rechecked_file','newly_acquired':False})
files=list({r['path']:r for r in files}.values())
lines('CAPTURE_INDEX.jsonl',captures);lines('FILE_MANIFEST.jsonl',files)

# Evidence references keep source statistics distinct from task admission.
evidence=defaultdict(list)
for ident,r in old.items():
 sid=source_map.get(r['source'])
 if sid and r['level'] not in ['not_validated','not_a_validated_sample','reference_material']:
  evidence[sid].append({'file':'analysis/DOWNLOADED_AUDIT.json','check_id':ident,'result':r['level']})
for ident,r in new.items():
 evidence[r['source']].append({'file':'analysis/SELECTION_AUDIT.json','check_id':ident,'result':r['level']})
for r in inherit['reports']:
 sid=source_map.get(r['source'])
 if sid:evidence[sid].append({'file':'../multihazard_source_validation_20260911/analysis/INHERITED_SAMPLES.json','source_key':r['source'],'result':r['level']})
evidence['D18'].append({'file':'analysis/SELECTION_AUDIT.json','check_id':'geoid-complete-pairs-and-cems','result':'activation_AOI_metadata_bridge'})
evidence['D42'].append({'file':'analysis/SELECTION_AUDIT.json','check_id':'geoid-complete-pairs-and-cems','result':'derived_S1_component_only_raw_GRD_access_not_validated'})
rights={
'D12':('provider_license_captured','CC-BY-4.0 in pinned dataset README; inherited manual labels; upstream/product conditions still checked per asset'),
'D52':('provider_license_captured','Kaggle metadata CC0; attribution/terms of NASA POWER, USDM and soil inputs retained'),
'D64':('provider_license_captured','Dataverse CC-BY-SA-4.0 metadata; current assets are LULC only'),
'D15':('unresolved','Repository/STAC dataset license ambiguity; do not equate code license with data license'),
'D39':('registration_and_terms_required','No authenticated dataset access attempted'),
'D44':('registration_and_terms_required','xBD terms and release conditions pending'),
'D47':('upstream_rights_pending','HF package downloaded; ERA5 and EM-DAT derivative conditions not yet cleared'),
'D50':('repository_license_only','GitHub LICENSE captured; individual NHC products and derived QA rights separate'),
'D19':('data_terms_pending','Author reader verified; data publication terms still to be pinned'),
}
public_noaa={'D01','D05','D08','D09','D10','D26','D27','D28','D37','D38','D55','D56','D57','D58','D67'}
for sid,r in registry.items():
 r.update(decisions[sid]); cs=[c for c in captures if c['source_id']==sid];r['capture_ids']=[c['bundle']+':'+c['capture_id'] for c in cs]
 r['observed_urls']=list(dict.fromkeys(c['original_url'] for c in cs));r['evidence']=evidence[sid]
 good=[c for c in cs if c['http_status'] in [200,206] and c['response_complete'] and c['body_bytes']]
 access='response_captured' if good else 'requests_failed_or_incomplete' if cs else 'inherited_local_sample' if evidence[sid] else 'not_runtime_probed'
 if sid=='D42':access='derived_component_only_raw_access_not_tested'
 lic,detail=rights.get(sid,('official_public_data_terms_to_document','Official public endpoint reachable or registered; per-product attribution and third-party exceptions remain to document') if sid in public_noaa else ('not_fully_verified','Planning links/README do not establish rights to redistribute every upstream asset'))
 r['axes']={'access':access,'content':r['content_evidence'],'provenance':'evidence_bound_source_mapping_partial' if evidence[sid] else 'not_locally_established',
            'license':lic,'task_eligibility':'new_tasks_not_admitted'}
 r['license_note']=detail;r['capabilities']={f'C{i}':('candidate_evidence_requires_task_checks' if f'C{i}' in r['capability_candidates'] else 'not_validated') for i in range(8)}
 if sid=='D01':
  for cap in ['C1','C2','C4','C5']:r['capabilities'][cap]='inherited_MM_seed_only_no_new_admission'
 r['capabilities']['C6']='not_established_historical_availability_null'
 r['source_case_count_not_global_event_count']=True
lines('source_access_report.jsonl',registry.values())
write('SOURCE_REGISTRY.json',{'schema':'disastertrace_v6_selection_registry_v1','original_sources':54,'supplements':20,'registered_entries':len(registry),
 'independent_physical_source_count':None,'not_all_sources_sample_verified':True,'sources':list(registry.values())})

measure=[]
def count(sid,metric,value,unit,basis,ref,scope='audited local sample',**extra):
 measure.append({'source_id':sid,'metric':metric,'value':value,'unit':unit,'basis':basis,'scope':scope,'evidence':ref,**extra})
for ident in ['storm-events-2021-assembled','storm-events-2023-assembled']:
 d=old[ident]['details'];count('D05','catalog_rows',d['records'],'report','decoded_complete_annual_file','analysis/DOWNLOADED_AUDIT.json#'+ident,ident)
for sid,ident,key,unit in [('D02','ibtracs-full-retry02-assembled','records','track fix'),('D02','ibtracs-full-retry02-assembled','storm_ids','source SID'),('D61','hanze-events','records','impact event record'),('D62','dheed-events','records','derived event record'),('D54','cllmate-data_dataset_cllmate_json-retry02','records','graph node'),('D59','meteonet-data_samples_ground_stations_SE_20160101_csv-retry02','records','station report'),('D59','meteonet-data_samples_ground_stations_SE_20160101_csv-retry02','stations','station'),('D68','hko7-hko_data_weather_statistics_csv','records','daily weather statistic'),('D23','firms-viirs','records','hotspot record')]:
 count(sid,key,old[ident]['details'][key],unit,'decoded','analysis/DOWNLOADED_AUDIT.json#'+ident)
for sid,prefix in [('D26','ghcnd-'),('D27','isd-'),('D56','usgs-')]:
 rs=[r for r in old.values() if r['id'].startswith(prefix) and r['level']=='sample_decoded']
 count(sid,'windows_or_files',len(rs),'station window/file','decoded','analysis/DOWNLOADED_AUDIT.json')
 count(sid,'records',sum(r['details']['records'] for r in rs),'station-day' if sid=='D26' else 'report' if sid=='D27' else 'discharge observation','decoded','analysis/DOWNLOADED_AUDIT.json')
for sid,ids,unit in [('D30',['chirps-2024.01.01-assembled','chirps-2024.01.02-assembled'],'daily raster'),('D55',['snodas-20240101','snodas-20240102','snodas-20240103-assembled'],'daily SWE grid'),('D38',['oisst-20240910','oisst-20240911','oisst-20240912'],'daily SST grid'),('D28',['gfs-tmp','gfs-ugrd','gfs-cape'],'variable field at one initialization'),('D67',['hrrr-tmp','hrrr-ugrd','hrrr-cape'],'variable field at one initialization'),('D21',['ts-satfire-sample-0-decoded','ts-satfire-sample-1-decoded','ts-satfire-sample-2-decoded'],'daily image from one fire')]:
 count(sid,'decoded_assets',sum(old[i]['level']=='sample_decoded' for i in ids),unit,'decoded','analysis/DOWNLOADED_AUDIT.json')
for sid,ident,field,unit in [('D47','exebench-coldwave','source_case_ids','source case'),('D47','exebench-coldwave','time_steps','case-day'),('D48','ewb-hourly-rowgroup','decoded_rows','hourly observation row'),('D48','ewb-hourly-rowgroup','object_declared_rows','metadata-declared row'),('D12','geoid-complete-pairs-and-cems','tile_pairs','four-role tile bundle'),('D12','geoid-complete-pairs-and-cems','activation_count','CEMS activation'),('D52','droughted-prefix','prefix_rows','complete CSV row in partial compressed member'),('D52','droughted-prefix','nonmissing_score_rows','nonmissing score row'),('D52','droughted-prefix','fractional_score_rows','fractional score row')]:
 count(sid,field,new[ident]['details'][field],unit,'footer_metadata_only' if field=='object_declared_rows' else 'decoded_partial_member' if sid=='D52' else 'decoded','analysis/SELECTION_AUDIT.json#'+ident)
count('D48','case_definitions',old['ewb-src_extremeweatherbench_data_events_yaml']['details']['records'],'case definition','decoded_yaml_not_observation_cases','analysis/DOWNLOADED_AUDIT.json#ewb-src_extremeweatherbench_data_events_yaml')
for sid,ident,skey,unit in [('D60','caravan-three-basins','samples','basin time series'),('D46','landslide-three-pairs','samples','image/mask pair')]:
 count(sid,'decoded_units',len(old[ident]['details'][skey]),unit,'decoded','analysis/DOWNLOADED_AUDIT.json#'+ident)
count('D60','basin_days',sum(x['rows'] for x in old['caravan-three-basins']['details']['samples']),'basin-day','decoded','analysis/DOWNLOADED_AUDIT.json#caravan-three-basins')
count('D07','decoded_radar_samples',len(old['tornet-three-prefix-members']['details']['members']),'negative radar sample','complete_members_from_partial_archive','analysis/DOWNLOADED_AUDIT.json#tornet-three-prefix-members')
count('D07','verified_tornado_positive_samples',0,'tornado-positive radar sample','decoded','analysis/DOWNLOADED_AUDIT.json#tornet-three-prefix-members')
count('D12','verified_flood_positive_tiles',sum(t['flood_pixels']>0 for t in new['geoid-complete-pairs-and-cems']['details']['tiles']),'tile','decoded','analysis/SELECTION_AUDIT.json#geoid-complete-pairs-and-cems')
count('D37','matched_observation_prediction_times',sum(s['matched_times'] for s in new['coops-time-pairing']['details']['samples']),'station-time pair','joined_by_station_time_datum','analysis/SELECTION_AUDIT.json#coops-time-pairing')
count('D10','files',3,'20-second GLM product','decoded_parent_IDs_checked','analysis/SELECTION_AUDIT.json#glm-three-products')
for key in ['flash','group','event']:
 count('D10',key+'_records',sum(s['counts'][key] for s in new['glm-three-products']['details']['samples']),key+' record within product','decoded_not_boundary_deduplicated','analysis/SELECTION_AUDIT.json#glm-three-products')
for item in inherit['reports']:
 sid=source_map.get(item['source'])
 if sid:count(sid,'inherited_sample_units',len(item.get('samples',[])),item.get('sample_unit','sample'),'inherited_rechecked','../multihazard_source_validation_20260911/analysis/INHERITED_SAMPLES.json')
count(None,'new_deduplicated_event_families',None,'event family','not_computed','SPLIT_AND_DEPENDENCY_RISKS.json')
count(None,'new_formal_task_episodes',0,'episode','none_admitted','SCOPE.json')
count(None,'historical_asof_qualified_episodes',0,'episode','none_admitted','SCOPE.json')
counts={'schema':'disastertrace_v6_data_counts_v1','registry_entries':len(registry),'original_entries':54,'supplement_entries':20,
 'content_class_counts':dict(Counter(r['content_evidence'] for r in registry.values())),
 'network':{root.name:{'http_attempts':sum(r['bundle']==root.name for r in attempts),'captured_bytes':sum(r['bytes'] for r in attempts if r['bundle']==root.name)} for root in [PRIOR,ROOT]},
 'unique_file_payload_bytes':sum(r['bytes'] for r in {r['sha256']:r for r in files}.values()),
 'file_manifest_entries':len(files),'counts':measure,
 'legacy_target':{'value':3050,'unit':'episode','status':'not_supply_not_achieved_not_current_acceptance'},
 'event_family_total':None,'new_model_calls':0,'new_gpu_jobs':0,
 'limits':['Registry entries include benchmarks and derivative products; do not sum them as independent sensors.','No probability sampling or whole-source availability rate is estimated.','HTTP attempts include redirects/failures; captured bytes include partials and metadata, not only usable science data.','Inherited sample rechecks do not equal new acquisition.']}
write('DATA_COUNTS.json',counts)

hazard_input=[
('H01','热带气旋','D01,D02,D47,D50','D03,D04,D73',['Hurricane','Hurricane (Typhoon)','Tropical Storm','Tropical Depression'],'NHC 已有种子/公告；全球 IBTrACS SID；CyPortQA 3 风暴图文','新增亚洲/南半球独立风暴；best-track/outcome 隔离；不复用受保护风暴'),
('H02','温带风暴/非对流大风','D05,D27','D28,D48,D67',['High Wind','Strong Wind'],'强风报告及 ISD 风记录可读','需非对流分类证据；不能将全部雷达 storm 叫温带气旋；风速/阵风分开'),
('H03','雷暴大风/下击暴流','D05,D06,D49','D08,D09,D48',['Thunderstorm Wind'],'灾害报告、VIL 序列；SPC MD 原文','缺地面风与雷达联合窗口；下击暴流需特定证据'),
('H04','龙卷风','D05,D07','D06,D08,D49',['Tornado'],'龙卷报告；TorNet 3 个负例可读','TorNet 正例 0；核对 v1.1 修订和同一风暴负例'),
('H05','冰雹','D05,D06','D09,D48,D70',['Hail'],'真实冰雹目录标签；SEVIR 2 条 Hail VIL','补地面直径/报告与雷达 MESH 时空匹配'),
('H06','强雷电','D10','D06,D05',['Lightning'],'3 个 GLM 产品，flash/group/event 可读并检父子关系','尚未验证极端密度；需当地时间/面积基线及跨文件去重'),
('H07','极端降水','D26,D30,D59','D09,D29,D47',['Heavy Rain'],'站点雨量、CHIRPS 2 日、MeteoNet 实测资料','日累计/分钟率不可混用；本轮栅格窗口未被认定极端'),
('H08','河洪/山洪/城市内涝','D05,D15,D56,D60,D61','D12,D13,D14,D16,D17,D51',['Flood','Flash Flood'],'站点流量、Caravan 时序、Sen1 标签及 HANZE','GEOID 新样本洪水正像素 0；城市内涝、道路状态、永久水体需独立验证'),
('H09','风暴潮/沿岸淹没','D37,D05','D01,D18,D58,D69',['Coastal Flood','Storm Surge/Tide'],'3 站 720 对潮位/预测匹配','潮汐残差不是纯风暴潮；尚未取得独立沿海淹没掩膜及阈值'),
('H10','热浪','D26,D48','D47,D25,D34',['Heat','Excessive Heat'],'Heathrow 窗口、EWB 热浪定义和小时观测','ExEBench heatwave 包未下载；本地气候态和持续时间待补，LST 单列'),
('H11','寒潮/极端低温/霜冻','D47,D26,D27','D48,D28',['Cold/Wind Chill','Extreme Cold/Wind Chill','Frost/Freeze'],'ExEBench 9 案例/559 时间步，Houston 站温','寒潮骤降、绝对低温、霜冻分开定义；空间均值定义与跨国事件去重'),
('H12','暴雪/积雪/冰冻/冻雨','D05,D26,D55','D27,D33,D49',['Blizzard','Heavy Snow','Ice Storm','Winter Storm','Winter Weather','Lake-Effect Snow','Sleet'],'暴雪等灾害报告；Buffalo 站点雪量、SNODAS SWE','冻雨和吹雪现象码样例为 0；雪盖/积雪不可填补全部冬季细类'),
('H13','干旱/闪旱','D31,D52','D30,D32,D60,D62',['Drought'],'3 周 USDM；DroughtED 26,666 行前缀','周标签含连续小数；实际 split 与文档不一致；闪旱快速恶化定义待核'),
('H14','沙尘暴','D05,D27','D35,D36,D63',['Dust Storm'],'有沙尘暴灾害报告；ISD 276 条浮尘/扬沙现象码','ISD 本批沙尘暴码正例 0；必须补 dust-specific 栅格和地面暴尘窗口'),
('H15','浓雾/极端低能见度','D27,D05','D53,D63',['Dense Fog','Freezing Fog'],'ISD 34 条带合格能见度的雾码报告','海雾 cube 未验证；极端低能见度阈值、持续时间及烟/沙尘排除待补'),
('H16','野火/天气相关火险','D19,D23','D20,D21,D22,D24,D65',['Wildfire'],'WildfireSpreadTS 3 日、FIRMS 热点、TS-SatFire 3 日','每组仅 1 火场；火点/烧痕/火险分开；天气相关不等于自然或极端天气致火')]
storm_counts=Counter()
for ident in ['storm-events-2021-assembled','storm-events-2023-assembled']:storm_counts.update(old[ident]['details']['type_counts'])
hazards=[]
for ident,name,main,backup,types,actual,gap in hazard_input:
 hazards.append({'hazard_id':ident,'name':name,'primary_source_ids':main.split(','),'backup_source_ids':backup.split(','),
 'storm_events_types':types,'catalog_report_count':sum(storm_counts[t] for t in types),'catalog_count_scope':'NOAA Storm Events 2021+2023, selected report types',
 'catalog_report_count_is_event_family_count':False,'verified_evidence_cn':actual,'gaps_cn':gap,'new_qualified_episodes':0,
 'independent_event_family_count':None,'readiness':'evidence_probe_only_subtypes_incomplete'})
write('HAZARD_COVERAGE.json',hazards)
with (ROOT/'HAZARD_COVERAGE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['hazard_id','name','primary_source_ids','backup_source_ids','catalog_report_count','verified_evidence_cn','gaps_cn','new_qualified_episodes','independent_event_family_count'])
 w.writeheader()
 for r in hazards:w.writerow({k:','.join(r[k]) if isinstance(r[k],list) else r[k] for k in w.fieldnames})
md('HAZARD_COVERAGE.md','# 16 类灾种的实测覆盖与缺口\n\n“有目录/有观测/有正例/有任务”分别判断。下表报告数是 2021、2023 两年美国 NOAA 报告类型的实测计数，不是去重天气事件，也不代表全球覆盖。三条相邻记录属于便利抽样，不能估计可用率。全部新资料尚未成为正式评测题。\n\n'+table(['ID / 灾种','主路线；备选','目录报告条数','已经验证','仍需解决'],[(r['hazard_id']+' '+r['name'],','.join(r['primary_source_ids'])+'；'+','.join(r['backup_source_ids']),r['catalog_report_count'],r['verified_evidence_cn'],r['gaps_cn']) for r in hazards])+'\n扩展：海洋热浪使用 D38；降雨滑坡使用 D46，但降雨因果尚未建立。火山、地震、海啸不纳入主表。2023 Storm Events 中 7 条 Volcanic Ashfall 不计入这 16 类。\n\n目前非美国证据包括 ExEBench 寒潮的 8 国/地区、北京与沙特站点、英国和澳大利亚站点、法国 MeteoNet、欧洲 HANZE、德国 GEOID/CEMS、印度与柬埔寨 Sen1Floods11。它们未形成全球均衡的事件分布；全球栅格覆盖也不能当作已验证全球极端事件。')

joins=[]
def join(ident,src,event,upstream,status,evidence,limits):
 joins.append({'link_id':ident,'benchmark_source_id':src,'source_event_or_product':event,'upstream':upstream,'status':status,'evidence':evidence,
 'historical_available_at':None,'new_task_admitted':False,'limitations':limits})
join('geoid-cems-EMSR712-AOI10','D12','EMSR712 / AOI10','D18 CEMS activation EMSR712 / Berga','activation_and_AOI_matched','analysis/SELECTION_AUDIT.json#geoid-complete-pairs-and-cems','Exact scene UUID and annotation revision still pending; original test material already observed; three tiles are not three events.')
for s in new['exebench-coldwave']['details']['samples']:
 join('exebench-'+s['case_id'],'D47',s['case_id'],'ERA5 t2m; EM-DAT-style case ID','time_coordinates_and_source_ID_decoded','analysis/SELECTION_AUDIT.json#exebench-coldwave','Original ERA5 extraction recipe and source-event ID authority not independently verified; not an independent observational source.')
for s in new['cyport-three-storm-bundles']['details']['samples']:
 join('cyport-'+s['source_storm_name'],'D50',s['source_storm_name'],{'source':'D01 NHC','storm_ids':s['parts']['txt']['storm_ids']},'storm_identifier_and_filename_bundle','analysis/SELECTION_AUDIT.json#cyport-three-storm-bundles','Image-printed issuance and text product timestamps need exact join; port QA labels not inherited.')
join('weatherqa-2018-md0398','D49','README example 2018_md0398, 2018-05-13 17Z','https://www.spc.noaa.gov/products/md/2018/md0398.html','upstream_text_retrieved_benchmark_data_missing','batches/priority_02/D49-spc-md0398.json','20 map parameters are not 20 time steps; no full image group or benchmark raw-text file obtained.')
join('ewb-ghcnh-rg0','D48','GHCN-hourly row group 0','https://storage.googleapis.com/extremeweatherbench/datasets/ghcnh_all_2020_2024.parq','upstream_product_slice_decoded_no_case_join','analysis/SELECTION_AUDIT.json#ewb-hourly-rowgroup','329 case definitions and this observation slice have not been matched into 329 episodes; unit conversion needs audit.')
join('droughted-usdm-power','D52','train prefix, FIPS 01001/01003/01005/01007/01009','D31 USDM + NASA POWER + soil database','provider_lineage_and_fields_captured','analysis/SELECTION_AUDIT.json#droughted-prefix','Score transformation including fractional values pending; county-week join to exact USDM map not reconstructed.')
join('wildfire-reader','D19','fire_21458798 / 2018-01-01..03','Author FireSpreadDataset.py blob a7422287ea43725a6deaa27e2af548626ea15629','label_transform_replayed','analysis/SELECTION_AUDIT.json#wildfire-label-semantics','Mask provenance to exact satellite source and coverage QA remains unresolved.')
lines('BENCHMARK_RAW_LINKS.jsonl',joins)

dependencies=[
 {'from':'D47','to':'ERA5','relation':'derived_weather_fields','status':'author_reader_and_package_evidence'},
 {'from':'D48','to':'ERA5','relation':'one_possible_reference_product','status':'reader_documentation_not_current_slice'},
 {'from':'D66','to':'ERA5','relation':'processed_chunk','status':'inherited_chunk_verified'},
 {'from':'D60','to':'ERA5-Land','relation':'meteorological_forcing','status':'provider_documentation'},
 {'from':'D52','to':'D31','relation':'target_derived_from_USDM','status':'provider_metadata'},
 {'from':'D52','to':'NASA_POWER','relation':'weather_covariates','status':'provider_metadata'},
 {'from':'D12','to':'D18','relation':'CEMS_derived_flood_annotation','status':'activation_bridge_verified'},
 {'from':'D12','to':'D42','relation':'Sentinel1_images','status':'paired_assets_verified'},
 {'from':'D50','to':'D01','relation':'repackaged_NHC_graphics_text','status':'storm_ID_verified_timestamp_join_pending'},
 {'from':'D30','to':'IMERG','relation':'DAILY_SAT_submonthly_timing_dependency','status':'provider_documentation'},
 {'from':'D06','to':'D05','relation':'event_catalog_association','status':'source_ID_specific_join_required'}]
write('SOURCE_DEPENDENCIES.json',{'edges':dependencies,'limits':'Edges describe derivation, not physical event identity; do not union event splits merely because a source uses ERA5.'})
reuse=defaultdict(list)
for f in files:
 if f['bytes'] and (f['role']!='http_capture' or f.get('http_status') in [200,206]):reuse[f['sha256']].append(f['path'])
write('ASSET_REUSE_INDEX.json',{'exact_duplicate_payload_groups':[{'sha256':k,'paths':v} for k,v in reuse.items() if len(v)>1],
 'role':'Exact payload duplication only; complete event identity and near-duplicate image matching remain pending.',
 'same_hash_is_not_new_independent_event':True})
risks={'protected_storm_ids':read(ROOT/'REPO_DATA_BASELINE.json')['protected_ids'],'event_family_count':None,
 'guard':'All new material is AUDIT_ONLY or PENDING_SPLIT_CHECK. No new train/dev/test task partition has been minted.',
 'known_groups':[{'key':'EMSR712','members':['D12 3 tiles','D18 activation/AOI metadata'],'external_split':'test','allowed_use':'observed availability audit only; select different train events for development'},
 {'key':'fire_21458798','members':['D19 Jan1','D19 Jan2','D19 Jan3'],'independent_events':1},
 {'key':'fire_20562846','members':['D21 Apr23','D21 Apr24','D21 Apr25'],'independent_events':1},
 {'key':'AL052019','members':['D50 Dorian','D01 related products'],'status':'join before split'},
 {'key':'AL092017','members':['D50 Harvey','D01 related products'],'status':'join before split'},
 {'key':'AL062018','members':['D50 Florence','D01 related products'],'status':'join before split'}],
 'open_risks':['Storm Events episodes may share synoptic parent; county lines do not partition events.','Full annual reports, IBTrACS and hourly station files may contain protected events; quarantine until identity filtering.','ExEBench country cases can share one transboundary coldwave; event-family count remains null.','DroughtED temporal splits disagree with documentation; preserve original path and compute actual per-file dates.','Public benchmark cases and questions may be in LLM pretraining; add future/nonoverlapping withheld events and report contamination limits.','Shared source families affect independence analyses but do not define physical event grouping.','Existing pixel crops, maps, branches and question paraphrases never increase independent-event counts.']}
write('SPLIT_AND_DEPENDENCY_RISKS.json',risks)

recnames={'core':'优先数据开发池','bridge':'定向桥接','conditional':'条件候选','defer':'暂缓','extension':'扩展灾种','auxiliary':'辅助背景'}
md('SOURCE_FEASIBILITY.md','# 数据源选择与实测可行性\n\n本表保留用户 V6 的 D01–D54，并把此前实际调查中的互补来源登记为 D55–D74。共 74 个登记项，包含 benchmark、产品和派生资料；不是 74 个独立传感器，也不是全部已下载。判定来自 SOURCE_REGISTRY.json、CAPTURE_INDEX.jsonl、两份离线审计和继承复核文件。\n\n五个独立轴为 access、content、provenance、license、task_eligibility。推荐进入开发池表示优先完成适配和准入，所有新正式任务数仍为 0。C0–C7 中 candidate 表示已有相关证据但尚未通过对应任务规则。\n\n'+table(['来源','建议','实测内容层','访问层','选择依据与缺口'],[(sid+' '+r['name'],recnames[r['recommendation']],r['content_evidence'],r['axes']['access'],r['decision_cn']) for sid,r in registry.items()])+ '\n## 权利与来源的独立检查\n\n'+table(['来源','当前状态','范围'],[(sid,r['axes']['license'],r['license_note']) for sid,r in registry.items()])+'\n## 可重放证据\n\n- 原始入口和失败/重试记录：CAPTURE_INDEX.jsonl；逐次 HTTP 回执在两个 bundle 的 attempts/。\n- 数组、字段、日期和计数：analysis/DOWNLOADED_AUDIT.json、analysis/SELECTION_AUDIT.json。\n- 每个本地资产及哈希：FILE_MANIFEST.jsonl。返回 206 完整 Range 不表示完整归档。\n- 不能自动外推成功率：本轮是目录开头或已知事件的便利抽样，未做随机抽样。\n- 许可不明确的来源保持候选；公开可下载不等于可以直接重新分发。\n')
caprows=[[sid+' '+r['name']]+[r['capabilities'][f'C{i}'] for i in range(8)] for sid,r in registry.items()]
md('CAPABILITY_MATRIX.md','# C0–C7 能力证据\n\nC0 目录/背景；C1 感知/空间；C2 多模态；C3 真实演化；C4 同目标修订；C5 受控回放；C6 严格历史 as-of；C7 未来结果配对。所有新增数据均未正式准入；继承 NHC 能力只适用于已验证种子，不能扩展到整源。C6 没有被获取时间或文件 Last-Modified 代替。\n\n'+table(['来源']+[f'C{i}' for i in range(8)],caprows))

manifest=[]
def acquire(key,sources,priority,action,selectors,budget,gain,gate,**kw):
 manifest.append({'id':key,'source_ids':sources,'priority':priority,'action':action,'selectors':selectors,
 'max_captured_bytes':budget,'expected_download_bytes':None,'expected_expanded_bytes':None,'net_new_event_families':None,'expected_gain':gain,
 'prerequisites':gate,'external_train_only':True,'model_calls':0,'gpu_jobs':0,'status':'planned_not_launched',**kw})
acquire('N01-longtail-event-windows',['D05','D27','D55'],1,'从已冻结报告目录挑选正例/邻近负例，先去重和保护过滤，再取同站逐时记录。',
 {'local_catalogs':['storm-events-2021-assembled','storm-events-2023-assembled'],'report_types':['Dust Storm','Ice Storm','Blizzard','Dense Fog','Lightning'],'selection_rule':'per type first 3 distinct provisional source episodes after identity review by deterministic metadata rules; ambiguous families quarantined','station_query_template':'https://www.ncei.noaa.gov/data/global-hourly/access/{year}/{station_id}.csv'},128*2**20,'补目前不足的沙尘暴、冻雨、暴雪、极端雾窗口；目标是证据链，不承诺 15 个独立事件。',['recompute local identity map','resolve stations by coordinates and distance cutoff','predeclare weather codes and QC'])
acquire('N02-exebench-next-package',['D47','D26'],2,'锁同一 commit 列出 heatwave 包；取包后检查病例、时间轴及与地面站桥接。',
 {'hf_repo':'zhaoshan/ee-bench_v1.0','revision':new['exebench-coldwave']['details']['hf_commit'],'relative_path':'data/weather/heatwave.zip','source_url':'https://huggingface.co/datasets/zhaoshan/ee-bench_v1.0/resolve/'+new['exebench-coldwave']['details']['hf_commit']+'/data/weather/heatwave.zip','package_size_reported_decimal_bytes':65300000},96*2**20,'扩大热浪和非美国地区；寒潮 9 个病例先合并跨国事件。',['verify pinned size and SHA256','ERA5 and EM-DAT lineage/terms','protect historic heldout'])
acquire('N03-tornet-positive',['D07','D08'],1,'读取已取得 catalog 的完整成员/版本元数据，找到 v1.1 正例及匹配负例，再定点取 NetCDF。',
 {'zenodo_record':'12636522','selection':'3 TOR and 3 NUL from train, distinct parent storm IDs; confirm release v1.1 label mapping','minimum_member_count':6},128*2**20,'解决已取得 3 例全为负例的问题。',['match release ID to corrected labels','bounded seekable route or select smaller archive; do not download 3GB archive by default'])
acquire('N04-flood-positive-bridge',['D12','D18','D15'],1,'只用 train 列表挑新 activation，先验 mask 三类和正负覆盖，再配 CEMS 原产品。',
 {'hf_repo':'links-ads/geoid-flood','revision':'868407460bf3db492f50730a57585916baa71dc6','exclude_activation':'EMSR712','selection':'3 train activations; >=1 flood-positive tile and 1 hard-negative tile each; use label only for private audit strata','api':'https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code={activation_code}'},256*2**20,'提高独立洪水与真实正例数量；补不同大陆，优先河洪/城市内涝差异。',['resolve original split and scene IDs','freeze label-derived validity as private QA','exclude protected storm families'])
acquire('N05-droughted-integrity',['D52','D31'],1,'先取静态小表和发布 metadata；计算各文件真实日期范围/score 定义，再制定有界时序获取方案。',
 {'metadata':'https://www.kaggle.com/api/v1/datasets/view/cdminix/us-drought-meteorological-data','file_list':'https://www.kaggle.com/api/v1/datasets/list/cdminix/us-drought-meteorological-data','static_file':'soil_data.csv','static_reported_bytes':731402,'timeseries_raw_bytes_reported':2196408881,'full_train_download_this_stage':False},4*2**20,'处理训练年限冲突、1,330 条小数标签与周频缺失，避免错误生成六分类 Gold。',['derive county aggregation formula','preserve exact original splits','USDM-to-score authority'])
acquire('N06-extreme-lightning',['D10','D06','D05'],2,'由强对流事件时空窗取 GLM 小文件集合，按 flash 而非 event 数构建密度检验。',
 {'s3_list_template':'https://noaa-goes16.s3.amazonaws.com/?list-type=2&prefix=GLM-L2-LCFA/{year}/{day_of_year}/{hour}/&max-keys=100','window_count_target':3,'max_files_per_window':30},64*2**20,'由 1 分钟一般雷电样例升级到已报告事件窗口。',['predeclare footprint/time normalization','deduplicate boundary flashes','baseline window independent of target labels'])
acquire('N07-fire-event-diversity',['D19','D21','D23'],2,'在现有 ZIP 索引中选择另外两个 train 火场的连续窗口；优先有正例且具有效覆盖信息的场景。',
 {'local_zip_index':'../multihazard_source_validation_20260911/archive_runs/wildfirespreadts_01/INDEX.json','exclude':'2018/fire_21458798','days_per_fire':3,'new_fire_ids_target':2,'author_reader_blob':'a7422287ea43725a6deaa27e2af548626ea15629'},96*2**20,'新增火场而不是增加同一火场裁剪。',['bind original split','active-fire HHMM interpretation','future weather features as-of review'])
acquire('N08-water-and-coastal',['D56','D57','D37','D58','D69'],2,'把洪水或沿海风险时间窗与站点/基准面元数据成对获取。',
 {'coops_stations':['8761724','8518750','9414290'],'coops_products':['water_level','predictions'],'datum':'MLLW','timezone':'gmt','units':'metric','usgs_sites':['07374000','01646500','02323500'],'nwps_sites':['BTRL1','STFL1','DONL1'],'do_not_assume_BTRL1_equals_USGS07374000':True},16*2**20,'验证事件窗、阈值与观测/预报对齐；增加海岸灾害的独立参考。',['datum and site-ID proof','retrospective reference remains private','positive event window selection'])
acquire('N09-weatherqa-upstream',['D49','D50','D01'],2,'先复现一个精确产品组，再扩大 3 个开发事件的图文时间配对。',
 {'example':'2018_md0398','upstream_text':'https://www.spc.noaa.gov/products/md/2018/md0398.html','spc_map_archive':'https://www.spc.noaa.gov/exper/ma_archive/','cyport_storms':['DORIAN_2019','HARVEY_2017','FLORENCE_2018'],'max_assets':12},32*2**20,'验证图像与正文确属同一时刻；不继承开放题或港口动作真值。',['match timestamps printed in graphics','document product codes and issue time','exclude protected aliases'])
acquire('N10-fog-dust-backup',['D53','D63','D35'],3,'核验作者来源和网盘实际文件；如仍受阻，保留 ISD 现象码主线并定向获取原始尘埃/卫星产品。',
 {'M4Fog_repo':'https://github.com/Clynie/M4Fog','DAWN_listing':'https://data.mendeley.com/public-api/datasets/766ygrbt8y/files?folder_id=root&version=1','DAWN_packages':['Fog.zip','Sand.zip'],'images_per_package':3},16*2**20,'验证视觉条件备用数据；无时间/地点时仅进入辅助感知，不计真实极端事件。',['M4Fog provenance/terms','no login bypass','DAWN source names verified from actual listing'])
acquire('N11-nonUS-event-selection',['D61','D60','D59','D02','D47'],1,'只处理现有本地索引，生成国家/季节/灾种候选分布和重复事件簇，先不批量下载。',
 {'HANZE_records':2521,'IBTrACS_source_SIDs':378,'ExEBench_cold_cases':9,'existing_Caravan_basins':['camels_01022500','camels_01031500','camels_01047000'],'selection_target':'at least two regions/climate regimes per main hazard when empirical supply supports it'},0,'把地区增益作为下载优先级；不把全球栅格像元数当全球事件数。',['source IDs and event times normalized','protected IDs union','uncertain matches quarantined'])
acquire('N12-event-contract-and-dryrun',[],1,'离线建立 asset/event/product/label 记录、拆分三种图、执行确定性查询准入，无模型。',
 {'interfaces':['multimodal_v1.ArtifactMeta','multimodal_v1.FactKey','multimodal_v1.DeliveryEvent','active_forecast exact kernel'],'max_query_diagnostics_per_hazard':3},0,'让数据转成可评分结构，量化哪些灾种尚无可计算 Gold。',['license and split eligibility','no label leakage','independent numeric/geospatial reference'])
write('NEXT_ACQUISITION_MANIFEST.json',{'schema':'disastertrace_v6_next_acquisition_v1','status':'reviewable_plan_not_launched','items':manifest,
 'sum_item_capture_caps_bytes':sum(m['max_captured_bytes'] for m in manifest),'quota_free_bytes':None,'full_registry_bulk_download':False,
 'stop_rule':'Stop a source after bounded metadata/member attempts; record failures and proceed with independent sources. Caps are planning upper bounds, not expected traffic or reserved resources.',
 'sampling_plan':'Per accessible source aim for >=3 identifiable units, and positive/negative, time and region strata where available; initial convenience probes do not count as representative sampling.',
 'all_new_splits_pending':True})

md('REUSE_AND_GAPS.md','''# 复用现有实现与需要增加的接口

现有仓库已经有真实多模态实现，不能再沿用“尚无 MM 框架”的旧结论。已读取 `disastertrace-starter/README_MULTIMODAL_V1.md`、`CURRENT_PHASE.md`、`multimodal_v1/types.py` 和实际 admission；本轮未修改这些冻结模块。

| 现有部分 | 可以复用 | 还要补什么 |
| --- | --- | --- |
| multimodal_v1: ArtifactMeta、FactKey、DeliveryEvent、QuerySpec | 源资产、语义键、交付、确定性查询的已有协议 | 通用变量/单位/时间支撑区间；FactKey.threshold_kt 不能直接用于温度/雨量/土壤湿度 |
| NHC/MM 原始获取、存储、空间参考 | 哈希、官方产品、矢量参考及受控投递分支 | 扩展 source adapter；原生图像解读单列，不将数据重绘误标为原始卫星 |
| active_forecast exact kernel | 确定性计数、面积、修订运算及已有评分约束 | 各灾种 source admission；状态、输入、私有标签的运行时隔离；新增预算规则另行验收 |
| 现有受保护配置和源 manifest | 冻结样例/保护 ID 的继承 | 同一物理事件、重叠瓦片/时窗、跨 benchmark 资产重复的完整图 |
| 当前匿名有界下载、Range、解码脚本 | 捕获回执、失败、断点拼接、局部读、哈希及已有标签检查 | 重复运行的增量注册、provider schema 漂移检查、正负样例策略及测试覆盖 |

建议只增加数据准入/桥接层，不重写 benchmark 框架。最小数据记录应包含 source/version、artifact SHA256、变量和单位、valid time/issue time/retrieved time、空间范围/CRS、缺测/QC、原始 split、event ID、label authority、rights、parent products。historical_available_at 没有证据就保留 null。

三种图分开：physical-event graph 用于跨源事件切分；asset-reuse graph 用于重复影像、裁剪和派生资产防泄漏；source-dependency graph 用于独立证据声明。共享 ERA5 不会把所有天气事件连接成一个簇。

Gold 采用确定性记录读取、阈值/持续时间算法、空间运算及已有官方/公开数据集标签。允许已有专家标签并标注来源，例如 USDM、洪水人工掩膜；不新增逐题人工复核，也不使用 LLM judge 决定事实。数据发生冲突、时空或许可不能确定时，自动拒绝该题或显式输出 unknown，不能用模型补造真值。

未完成：多灾种通用 adapter、概率/分层抽样、全量事件去重、正式 train/dev/test、严格 as-of、原生影像必要性检查、跨灾种 Gold 一致性测试，以及新增模型实验。本轮的资产可解码不代表上述能力已实现。
''')

# High-level review is a durable handoff; claims link to the structured outputs.
summary=f'''# DisasterTrace V6 数据集选择：研究、实测与执行路线

核查日期：2026-09-11。输入为用户提供的两份 V6 计划及 download_registry.json；原始字节副本和哈希已保存。结论建立在此前抽样与本轮新增验证上，不是仅阅读网页后的推荐。

## 1. 推荐决定

采用两层结构：先建设尽可能广的 Broad Data Bank，再从中按任务建立合格子集。以 16 类天气灾害为覆盖目标，保留所有 54 个原候选，并登记 20 个互补来源。74 是登记项数，含 benchmark、原始产品及派生集合；既不是独立数据源数，也不是全部已验证数。没有必要等待所有来源满足同目标修订才能扩容。

优先开发池围绕几条互补链组织：事件目录 Storm Events/HANZE/IBTrACS；地面与水文观测 GHCN/ISD/USGS/CO-OPS/Caravan；天气演化与空间证据 NHC/SEVIR/GLM/MeteoNet/SNODAS/CHIRPS；整理后的寒潮/热浪路线 ExEBench/EWB；干旱 USDM；野火 WildfireSpreadTS/FIRMS。这些是优先适配和完成准入的选择，并非已经批准重分发或形成新题集。

GEOID、TorNet、CyPortQA、DroughtED、TS-SatFire、WorldFloods、M4Fog 等保留为条件候选。已有证据很有价值，但缺正例、版本/切分冲突、时间对齐或数据权利时，需要补齐指定条件。EM-DAT/xBD 等访问门槛较高且不是当前覆盖瓶颈的资料暂缓。海洋热浪和降雨滑坡单列扩展，避免挤占主要 16 类的长尾补样。

## 2. 已经实际验证的关键证据

| 来源 | 本地实测 | 结论范围 |
| --- | --- | --- |
| NOAA Storm Events | 2021 年 61,389 + 2023 年 75,593 = 136,982 条报告 | 可作多灾种索引；非独立天气系统数，含应排除的非天气类型 |
| ExEBench coldwave | 4,385,936 字节完整包；固定 commit；9 源案例、559 时间步、8 国/地区 | NetCDF t2m(K)、坐标和序列表日期已对齐；其他子包未下载 |
| ExtremeWeatherBench | 329 条案例定义；GHCN-hourly 解码 122,880 行、24 站 | 仅读取一个 row group；整个 Parquet 的 298,948,393 行来自 footer，不是已下载量 |
| GHCN / ISD | 5 个日观测窗口共 40 站日；2 个逐时站年共 28,733 报告 | QC/缺测字段已解析；仍须独立定义极端阈值和事件窗口 |
| GLM | 3 个相邻 20 秒产品；489 flash / 6,904 group / 18,973 event 记录 | 父子 ID 一致；计数单位不同，未认定为强雷电过程 |
| GEOID + CEMS | 3 组前后 SAR/label/validity，12 资产；EMSR712/AOI10 可桥接 | 三瓦片洪水正像素均为 0；原数据 split 为 test，只作已观察审计材料 |
| TorNet | 从部分归档提取 3 个完整 train NetCDF | 全部 NUL 负例；龙卷风正例验证仍为 0 |
| WildfireSpreadTS | 同一火场 3 日 TIFF，按作者规则复算活动火像素 4/0/0 | 854 等值是 HHMM 探测时刻，NaN 依作者规则转无探测；不构成火场消失的充分证明 |
| DroughtED | 1 MiB 压缩前缀解析 26,666 个完整 CSV 行、5 县、3,809 非空分数 | 不是完整归档；无完整成员 CRC；其中 1,330 个分数为小数，不能直接当整数六分类 |
| CO-OPS | 3 站共 720 对观测/预测潮，同 MLLW/GMT/米 | 可重算残差；残差不等于单一风暴潮成因 |
| Caravan / MeteoNet | 3 流域各 14,609 日；111,623 站报/484 站及 IR 数组 | 可补水文和欧洲资料；三个 Caravan 样例仍全部在美国 |
| 补充资料 | SNODAS 3 日、CHIRPS 2 日、OISST 3 日；Landslide4Sense 3 对；HANZE 2,521 记录；Dheed 82,839 记录 | 栅格、事件目录和标签对分别计数；不求一个混合总样本量 |

本轮新增 V6 捕获 {counts['network'][ROOT.name]['http_attempts']} 次 HTTP 尝试、{counts['network'][ROOT.name]['captured_bytes']:,} 字节；此前抽样 bundle 为 228 次、321,358,162 字节。尝试数包含重定向/失败，字节包含元数据和不完整响应。六类继承样例共绑定 26 个已有文件，没有重复当作新下载。

## 3. 对 V6 计划的重要修正

1. ExEBench 与 ExtremeWeatherBench 是两个不同项目；一个寒潮包的成功不能外推到所有天气/遥感子包。ExEBench 的国家案例可能属于同一跨境寒潮，9 个 case ID 尚不等于 9 个独立过程。
2. 数据集页面和真实数据会矛盾。DroughtED 页面说 train 2000–2009，本地 train 前缀实际含 2000–2016；下一阶段以冻结文件和实际日期计数为依据，并调查发布版本。周频缺失不等于无干旱，小数 score 的聚合公式需核验。
3. 简单取前三个文件会产生假覆盖。TorNet 三个负例、GEOID 三个无洪水瓦片、同一火场三天都证明了这一点。后续必须按正负/事件/地区/季节分层，失败和空样本保留在分母。
4. GEOID validity 与 label != 255 在本批完全一致，因此把它当公开独立传感器质量会泄漏 Gold。保留为私有评分有效区，另找真实云、轨道和传感器 QC。
5. ISD 本批实际有 34 条雾码以及 276 条浮尘/扬沙码；沙尘暴码 30–35、冻雨码 66–67、吹雪码 36–39 正例为 0。H14、H12 的特定细类仍是重点缺口，不能以“低能见度”或“SWE 有数据”替代。
6. CEMS 产品目录含“不生产/无变化”的版本。产品目录、发布版本、真实演化与同目标修订分别记录，不能仅按版本字段构造修订任务。
7. 公开访问、内容解码、来源链、数据权利、任务准入五轴分开。数据版权尚不明确的集合仍可登记其事实状态，不会因为网页打开就进入发布版。

## 4. 怎样兼顾覆盖与 novelty

多灾种数量是数据优势，单纯拼接公开 benchmark 本身不足以证明论文创新。建议将贡献收敛为“跨灾种、可追溯证据下的 LLM/VLM 状态判断与更新”，并保留三个相互可比、分别计分的层次。

- 覆盖层：16 类数据驱动阅读、阈值/持续时间判断、范围/受影响对象判定；与 ExEBench 的数值任务、EWB 的预报案例、WeatherQA/CyPortQA 的图文问答分别比较，不声称它们缺少全部相关能力。
- 演化层：同一真实过程多时刻证据，检查状态变化、未知区域与证据冲突；不同物理时刻和同一目标的预报修订分开。连续栅格可做 C3，不能因此叫 C4。
- 证据更新层：同一目标、不同发布/可见证据、时效冲突、可靠性和 abstention；Gold 来自明确的源记录及确定性规则。将受控交付 C5 与严格历史 as-of C6 分开，后者目前可以为空。

未来模型实验须加 text-only、image-only、完整证据、oracle structured evidence、时间打乱/过期证据、缺失证据和同源重复的诊断对照，分别报告感知错误与推理/更新错误。多模态必要性要有同文异图或同图异文等受控验证；不能用内容完全冗余的重绘图声称必须看图。

目前的 novelty 是有证据支撑的研究定位，不是已完成的首创性证明。还需要固定检索日期，对 ExEBench、EWB、WeatherQA、CyPortQA、CLLMate 及动态/工具型地学 benchmark 做方法维度对照；禁止未经系统检索写“首次”。本阶段不新增模型结果来代替该核查。

## 5. 后续执行顺序与完成条件

| 阶段 | 建议节奏 | 工作 | 完成条件 |
| --- | --- | --- | --- |
| A：库存和元数据收口 | 1–2 天 | 现有 74 项登记；优先来源许可、版本、source/event/product/asset 身份；保护过滤 | 每项有五轴状态，文件计数可重算，未知数保留 null；不要求全部来源成功 |
| B：长尾与正负抽样 | 3–5 天 | 优先沙尘暴/冻雨/极端雾/强雷电；TorNet、GEOID 正例；ExEBench 热浪；火场和非美国增益 | 每条保留主路线和备选；至少 3 可识别单元目标并按正负/地区分层；不足则显式列缺口 |
| C：事件合并和数据合同 | 第 2 周 | 三种图分开；跨 benchmark/跨国事件归并；变量、单位、时间支撑区间、QC、权利和 Gold authority | 不跨 split 的事件/资产簇，原始 split 保留，至少一个可审计极端/正常对照窗；混合/不确定事件隔离 |
| D：小规模可评分试点 | 后续约 2 周 | 复用已有 MM/active_forecast 接口，确定性查询与独立数值参考，先不调用模型 | 每个进入主榜的灾种都有合格数据/Gold/负例；未合格灾种留 Broad，不伪造全面覆盖 |
| E：模型评测与论文线 | 之后按实测供给推进 | 冻结开发/测试，执行感知/推理/更新对照、污染和泛化分析 | 只有准入、隔离与评分检查通过后启动 LLM/VLM；按事件族统计，不按问法膨胀 |

下一批下载和元数据操作已写入 NEXT_ACQUISITION_MANIFEST.json，12 项依赖与捕获上限合计约 {sum(m['max_captured_bytes'] for m in manifest)/(2**20):.0f} MiB。此数是各项上限之和，不是已启动预算、预测流量或预计净增事件数；实际事件增量和用户存储配额尚未知。优先执行 N11/N12 的离线工作，再执行 N01/N03/N04/N05 补关键证据，之后扩大其他数据。

## 6. 当前完成边界

DA00 工作区/冻结核查和 DA01 登记/16 类路线已完成本阶段要求。DA02/DA03 已对可达重点来源实际探测与解码，仍有未探测/阻塞项。DA04 有源案例和产品桥接记录，尚非所有样本的精确版本链。DA05 有能力候选矩阵，未完成正式任务准入。DA06 已重算本地数量、列出已知重复簇，但全量事件族/国家季节分布未完成。DA07 已交付下一轮具体获取清单。DA08 将以 VERIFY_REPORT.json 记录本次交接文件与哈希核查；它不宣告整个 V6 路线全部完成。

所有新增正式 episode = 0，新增 GPU 作业 = 0，新增 API/模型调用 = 0。历史 104 个开发 episode、现有 Francine MM 种子和历史模型成绩保持原冻结范围，不能与这次数据验证相加。所有历史 available_at 没有确证时仍为 null。

## 7. 阅读与复查入口

先看本文件，再看 SOURCE_FEASIBILITY.md 和 HAZARD_COVERAGE.md。详细数量在 DATA_COUNTS.json；逐样本核验在 analysis/SELECTION_AUDIT.json 和 analysis/DOWNLOADED_AUDIT.json；桥接事实在 BENCHMARK_RAW_LINKS.jsonl；现有接口复用在 REUSE_AND_GAPS.md；事件与依赖限制在 SPLIT_AND_DEPENDENCY_RISKS.json、SOURCE_DEPENDENCIES.json；后续执行依据为 NEXT_ACQUISITION_MANIFEST.json。

可离线运行：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911 python3 plans/v6_0911_dataset_selection/audit_selection.py`，随后 `python3 plans/v6_0911_dataset_selection/build_reports.py`。验证脚本和说明见 verify_selection.py/VERIFY_REPORT.json。源码读取器仅检查文本，没有执行作者模型、训练代码或不可信 pickle。
'''
md('DATA_READINESS_REVIEW_CN.md',summary)
print(json.dumps({'sources':len(registry),'hazards':len(hazards),'metrics':len(measure),'bridge_records':len(joins),'capture_records':len(captures),'asset_files':len(files),'next_acquisitions':len(manifest),'network':counts['network']},ensure_ascii=False,indent=2))
