import os
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
runtime_url=os.getenv('AI_RUNTIME_URL','').rstrip('/')
url=(runtime_url+'/v1/knowledge/policies' if runtime_url else os.getenv('API_GATEWAY_URL','http://localhost:8080/api/v1')+'/ai/knowledge/policies')
headers={'X-Tenant-Id':os.getenv('OPSBRIDGE_TENANT_ID','demo-tenant'),'Content-Type':'application/json'}
if token:=os.getenv('OPSBRIDGE_ACCESS_TOKEN'):headers['Authorization']=f'Bearer {token}'
if token:=os.getenv('INTERNAL_SERVICE_TOKEN'):headers['X-Internal-Service-Token']=token
for policy_path in sorted((root/'policies').glob('*.md')):
    response=httpx.post(url,headers=headers,json={'title':policy_path.stem.replace('-',' ').title(),'content':policy_path.read_text(encoding='utf-8')},timeout=120)
    response.raise_for_status()
    print(response.json())
