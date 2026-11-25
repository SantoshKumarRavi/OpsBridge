"""Local, read-only OpsBridge MCP tools. Runs over stdio for an attached AI client."""
import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp=FastMCP('OpsBridge')
GATEWAY=os.getenv('API_GATEWAY_URL','http://localhost:8080/api/v1')
TENANT=os.getenv('OPSBRIDGE_MCP_TENANT_ID','demo-tenant')

def request_headers():
    headers={'X-Tenant-Id':TENANT}
    token=os.getenv('OPSBRIDGE_MCP_ACCESS_TOKEN')
    if token:headers['Authorization']=f'Bearer {token}'
    return headers

@mcp.tool()
def list_onboarding_cases(status:str|None=None,limit:int=20)->dict:
    """List cases visible to the configured OpsBridge tenant. This tool is read-only."""
    if not 1<=limit<=100:raise ValueError('limit must be from 1 to 100')
    params={'status':status} if status else {}
    try:
        with httpx.Client(timeout=10) as client:
            response=client.get(f'{GATEWAY}/cases',headers=request_headers(),params=params);response.raise_for_status();data=response.json()
        data['items']=data.get('items',[])[:limit]
        return data
    except httpx.HTTPError as exc:return {'error':'OpsBridge API is unavailable or denied this request.','reason':type(exc).__name__}

@mcp.tool()
def get_onboarding_case(case_id:str)->dict:
    """Read one case and its audit timeline for the configured tenant."""
    if not case_id or len(case_id)>80:raise ValueError('case_id is invalid')
    try:
        with httpx.Client(timeout=10) as client:
            response=client.get(f'{GATEWAY}/cases/{case_id}',headers=request_headers());response.raise_for_status();return response.json()
    except httpx.HTTPError as exc:return {'error':'Case is unavailable or access was denied.','reason':type(exc).__name__}

@mcp.tool()
def search_onboarding_policy(query:str)->dict:
    """Retrieve policy snippets and source titles. Does not make an eligibility decision."""
    if not query.strip() or len(query)>1000:raise ValueError('query must be between 1 and 1000 characters')
    try:
        with httpx.Client(timeout=20) as client:
            response=client.post(f'{GATEWAY}/ai/knowledge/search',headers={**request_headers(),'Content-Type':'application/json'},json={'query':query});response.raise_for_status();return response.json()
    except httpx.HTTPError as exc:return {'error':'Policy search is unavailable or access was denied.','reason':type(exc).__name__}

@mcp.tool()
def outline_onboarding_automation(description:str)->dict:
    """Turn a business request into an editable workflow outline. It does not execute actions."""
    if not description.strip() or len(description)>4000:raise ValueError('description must be between 1 and 4000 characters')
    return {'description':description,'steps':[{'type':'trigger','name':'Worker application received'},{'type':'task','name':'Collect required profile and documents'},{'type':'agent','name':'Extract document fields and attach evidence'},{'type':'policy','name':'Run deterministic policy checks'},{'type':'human_task','name':'Review exceptions and decide'},{'type':'notification','name':'Notify worker and update integrated system'}],'requires_human_approval':True,'execution_status':'not_started'}

if __name__=='__main__':mcp.run(transport='stdio')
