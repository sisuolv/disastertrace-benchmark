"""Publish a bounded workspace update without changing the development index."""
import importlib.util, json, hashlib, subprocess, zipfile, io
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO.parents[1]
spec=importlib.util.spec_from_file_location('previous', REPO/'publication/v13_completed_20260917/publish_results.py')
p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
WORK=ROOT/'publication/workspace_sync_20260918_01'
WORK.mkdir(exist_ok=False)
p.legacy.OBJECTS=ROOT/'publication/v13_completed_20260917_01/publication.git/objects'
git=p.legacy.init_git(WORK/'publication.git',alternate=True)
base=git('rev-parse','FETCH_HEAD').decode().strip()
identity=p.development_identity()
original=p.legacy.entries(git,base)
snapshot=WORK/'snapshot'; snapshot.mkdir()
rows=[]; excluded=[]; changed=[]
private=[]
cred=Path('/mnt/afs/260010168/.config/disastertrace/credentials/siliconflow.json')
if cred.exists(): private.append(p.read(cred)['api_key'].encode())
if p.helpers.KEY_FILE.exists(): private.append(p.helpers.KEY_FILE.read_bytes().strip())
def inspect(name,data,depth=0):
    p.helpers.inspect_payload(name,data,private)
    if name.lower().endswith('.zip'):
        if depth>3: raise ValueError('nested archive depth')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(x.file_size for x in z.infolist())>100_000_000: raise ValueError('archive expansion limit')
            for x in z.infolist():
                if not x.is_dir(): inspect(x.filename,z.read(x),depth+1)
def save(name,data):
    inspect(name,data)
    blob=git('hash-object','--stdin',data=data).decode().strip()
    if original.get(name)==['100644','blob',blob]: return
    dest=snapshot/name; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
    rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    changed.append(name)
# Preserve previously published result bytes unless selected local files changed.
for path in p.selection():
    name=path.relative_to(REPO).as_posix()
    if name.startswith('publication/v13_completed_20260917/'): continue
    save(name,p.stable_bytes(path))
for folder in ['plan','reports','references']:
    for path in sorted((ROOT/folder).rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        if path.suffix.lower() not in {'.md','.txt','.json','.yaml','.yml','.csv','.zip','.pdf'}: continue
        name=path.relative_to(ROOT).as_posix()
        if path.stat().st_size>20_000_000:
            excluded.append({'path':name,'reason':'size over 20 MB'}); continue
        try: save(name,path.read_bytes())
        except ValueError as e: excluded.append({'path':name,'reason':str(e).split(' in ')[0]})
refs=[]
for folder in sorted((ROOT/'reference_code').iterdir()):
    if not folder.is_dir(): continue
    item={'name':folder.name}
    for key,args in [('commit',['rev-parse','HEAD']),('origin',['remote','get-url','origin'])]:
        result=subprocess.run(['git','-c','safe.directory='+str(folder),'-C',str(folder),*args],capture_output=True,text=True)
        if result.returncode==0:
            value=result.stdout.strip()
            if key=='origin' and ('@' in value and not value.startswith('git@')): value='omitted: authenticated URL'
            item[key]=value
    refs.append(item)
save('publication/workspace_sync_20260918/REFERENCE_CODE_INDEX.json',(json.dumps(refs,ensure_ascii=False,indent=2)+'\n').encode())
save('publication/workspace_sync_20260918/sync.py',Path(__file__).read_bytes())
code=[n for n in changed if n.startswith('disastertrace-starter/src/') or n.startswith('disastertrace-starter/tests/')]
report={'at':p.now(),'base':base,'code_or_test_changes':code,'files':list(rows),'excluded':excluded,'scope':'current selected code/results; original plans and review archives; reports and references; third-party repository provenance','new_experiments':0,'full_raw_data_backup':False}
save('publication/workspace_sync_20260918/MANIFEST.json',(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
note='''# 项目目录同步（2026-09-18）\n\n本次在已发布的 v13 完成结果上补充项目目录资料，不代表新实验执行。\n\n- 当前实验进展：[v13 完成结果](../../LATEST_PROGRESS_V13_CN.md)。\n- 原始计划与复查资料：[plan](../../plan)。历史方案不等同于已实现功能。\n- 第三方参考代码：[来源与版本索引](REFERENCE_CODE_INDEX.json)，不重复上传完整外部仓库。\n- 发布范围、文件哈希和排除记录：[MANIFEST.json](MANIFEST.json)。\n- 原始大数据、模型权重、运行缓存、凭据不在本次 Git 发布范围内。\n- 当前代码与测试相对远端变化数：%d。未重跑实验或测试。\n\n已有科学结论不变：本轮登记实验完成，但尚未证明 LLM 优于所有强程序基线，独立确认仍未完成。\n'''%len(code)
save('publication/workspace_sync_20260918/README_CN.md',note.encode())
banner='# Workspace update: 2026-09-18\n\n[Latest directory synchronization and scope](publication/workspace_sync_20260918/README_CN.md) | [Completed v13 experiment results](LATEST_PROGRESS_V13_CN.md) | [Original plans and reviews](plan)\n\n---\n\n'
save('README.md',banner.encode()+git('show',base+':README.md'))
if p.development_identity()!=identity: raise ValueError('Development identity changed')
names=[r['path'] for r in rows]
blobs=git('hash-object','-w','--no-filters','--stdin-paths',data=''.join(str(snapshot/n)+'\n' for n in names).encode()).decode().splitlines()
p.legacy.prior.BASE=base
tree=p.legacy.prior.overlay_tree(git,names,blobs)
after=p.legacy.entries(git,tree)
assert not(set(original)-set(after))
assert all(original[n]==after[n] for n in set(original)-set(names))
commit=git('commit-tree',tree,'-p',base,data=b'Update workspace plans, review materials and reference provenance\n').decode().strip()
p.write(WORK/'PREPARED.json',{'commit':commit,'base':base,'files':len(names),'code_changes':code,'excluded':excluded})
print(json.dumps({'prepared':commit,'files':len(names),'code_changes':len(code),'excluded':excluded}),flush=True)
assert git('ls-remote','origin','refs/heads/next-phase-v1').decode().split()[0]==base
p.write(WORK/'PUSH_INTENT.json',{'commit':commit,'at':p.now()})
git('push','origin',commit+':refs/heads/next-phase-v1')
readback=p.legacy.init_git(WORK/'readback.git')
assert readback('rev-parse','FETCH_HEAD').decode().strip()==commit
remote=p.legacy.entries(readback,commit)
assert all(remote[n]==['100644','blob',b] for n,b in zip(names,blobs))
for n in ['README.md','publication/workspace_sync_20260918/MANIFEST.json']:
    assert readback('show',commit+':'+n)==(snapshot/n).read_bytes()
assert p.development_identity()==identity
receipt={'passed':True,'commit':commit,'at':p.now(),'branch':'next-phase-v1','verified_files':len(names),'excluded':excluded,'code_changes':code,'development_identity_preserved':True}
p.write(WORK/'PUBLISHED.json',receipt)
p.write(HERE/'GITHUB_UPLOAD.json',receipt)
print(json.dumps(receipt),flush=True)
