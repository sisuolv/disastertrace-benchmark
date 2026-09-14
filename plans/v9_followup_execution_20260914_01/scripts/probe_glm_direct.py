import requests,json,hashlib
from pathlib import Path
p=Path('plans/v9_followup_execution_20260914_01/model_catalog/probe_03');p.mkdir(exist_ok=False)
s=requests.Session();s.trust_env=False
rows=[]
for name,url in [('glm53_modelscope','https://modelscope.cn/api/v1/models/ZhipuAI/GLM-5.3'),('glm53_github','https://api.github.com/repos/zai-org/GLM-5.3')]:
 row={'name':name,'url':url}
 try:
  r=s.get(url,timeout=(15,30));(p/(name+'.body')).write_bytes(r.content);row.update(status=r.status_code,bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest())
 except Exception as e:row['error_type']=type(e).__name__
 rows.append(row)
(p/'RESULTS.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))
