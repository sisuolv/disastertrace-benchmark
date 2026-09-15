from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
work=json.loads((ROOT/'specs/work_packages.json').read_text())['work_packages']
tests=json.loads((ROOT/'specs/acceptance_tests.json').read_text())['tests']
ids={w['id'] for w in work}; testids={t['id'] for t in tests}
assert len(ids)==len(work) and len(testids)==len(tests)
assert all(set(w['depends_on'])<=ids for w in work)
visiting=set();done=set();lookup={w['id']:w for w in work}
def dfs(i):
    assert i not in visiting,'Cyclic work dependency'
    if i in done:return
    visiting.add(i)
    for d in lookup[i]['depends_on']:dfs(d)
    visiting.remove(i);done.add(i)
for i in ids:dfs(i)
for w in work:
    assert set(w['acceptance_ids'])=={t['id'] for t in tests if t['work_package']==w['id']}
assert set(t['work_package'] for t in tests)==ids
r=json.loads((ROOT/'checks/SCOPED_RESULTS.json').read_text())
e=json.loads((ROOT/'checks/E_SUMMARY_REPRODUCTION.json').read_text())
assert r['total']==r['passed']==21 and e['passed']
for p in ROOT.rglob('*.json'):json.loads(p.read_text())
for n in ['REVIEW_AND_CODEX_NEXT_PLAN_CN.md','CODEX_START_HERE.md','README.md']:
    text=(ROOT/n).read_text();assert len(text)>100
for p in ROOT.rglob('*'):
    if p.is_file() and p.suffix in ('.md','.json','.py'):
        text=p.read_text()
        assert all(term not in text for term in ('?to' + 'ken=AY', 'Authoriz' + 'ation: Bearer '))
result={'passed':True,'work_packages':len(work),'future_acceptance_specs':len(tests),
 'sources':len(json.loads((ROOT/'specs/sources.json').read_text())['sources']),
 'upstream_module_synthetic_checks':r['passed'],'E_summary_expression_checks':1,
 'repository_suite_rerun':False,'scientific_experiments_executed':False}
(ROOT/'PACKAGE_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='MANIFEST.sha256')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(ROOT))+'\n' for p in files)
(ROOT/'MANIFEST.sha256').write_text(manifest)
zip_path=ROOT.parent/'DisasterTrace_v11_889620a_Review_Codex_Plan_20260915.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in files+[ROOT/'MANIFEST.sha256']:z.write(p,str(p.relative_to(ROOT)))
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    for line in manifest.splitlines():
        sha,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==sha
print(json.dumps({**result,'zip_path':str(zip_path),'zip_bytes':zip_path.stat().st_size,
 'zip_members':len(files)+1},ensure_ascii=False,indent=2))
