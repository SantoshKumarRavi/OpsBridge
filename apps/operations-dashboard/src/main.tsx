import React from 'react';
import { createRoot } from 'react-dom/client';
import { createOpsBridgeAuth } from '../../../packages/auth-client/src/index';
import { createOpsBridgeClient } from '@opsbridge/api-client';
import { Activity, ArrowUpRight, CheckCircle2, Clock3, FileCheck2, Search, ShieldCheck, Users } from 'lucide-react';
import './style.css';

const initial = [
  { id: 'OB-2048', name: 'Ananya Rao', role: 'Field Operations Associate', status: 'Needs review', docs: '2 of 3 verified', time: '12 min ago' },
  { id: 'OB-2047', name: 'Rahul Menon', role: 'Delivery Partner', status: 'Processing', docs: 'Document extraction', time: '28 min ago' },
  { id: 'OB-2046', name: 'Meera Iyer', role: 'Warehouse Associate', status: 'Ready to approve', docs: '3 of 3 verified', time: '1 hr ago' },
  { id: 'OB-2045', name: 'Arjun Das', role: 'Customer Support', status: 'Approved', docs: '3 of 3 verified', time: '2 hr ago' },
];

function App({auth}:{auth:ReturnType<typeof createOpsBridgeAuth>}) {
  const api = React.useMemo(() => createOpsBridgeClient({baseUrl:import.meta.env.VITE_API_URL ?? 'http://localhost:8080/api/v1',getHeaders:()=>auth.headers()}),[auth]);
  const [cases, setCases] = React.useState(initial);
  const [query, setQuery] = React.useState('');
  const refreshCases = React.useCallback(async()=>{try{const data=await api.listCases();setCases(data.items.map(row=>({id:String(row.id).slice(0,8),name:row.worker_name,role:row.role||'Unspecified role',status:row.status.replaceAll('_',' ').replace(/\b\w/g,(v:string)=>v.toUpperCase()),docs:`${row.documents?.length??0} document(s)`,time:new Date(row.created_at).toLocaleString()})))}catch{}},[api]);
  React.useEffect(() => {
    void refreshCases();
    let active=true, socket:WebSocket|undefined;
    const reconnect=async()=>{try{const headers=await auth.headers();const result=await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8080/api/v1'}/realtime/ticket`,{method:'POST',headers});if(!result.ok)throw new Error(`Realtime ticket request failed (${result.status})`);const{ticket,websocketUrl}=await result.json();if(!active)return;socket=new WebSocket(websocketUrl);socket.onopen=()=>socket?.send(JSON.stringify({type:'authenticate',ticket}));socket.onmessage=(message)=>{if(!active)return;try{const event=JSON.parse(message.data);if(event.type==='heartbeat'||event.type==='connected')return;void refreshCases()}catch{void refreshCases()}};socket.onerror=()=>socket?.close();socket.onclose=()=>{if(active)window.setTimeout(reconnect,3000)}}catch{if(active)window.setTimeout(reconnect,5000)}};
    void reconnect();return()=>{active=false;socket?.close()};
  }, [auth,refreshCases]);
  const visible = cases.filter(c => `${c.name} ${c.id} ${c.role}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="shell"><aside className="sidebar"><div className="brand"><span className="brand-icon">O</span><b>opsbridge</b></div><div className="workspace">DEMO WORKSPACE <span>⌄</span></div><nav><a className="active"><Activity size={18}/> Overview</a><a><Users size={18}/> Workforce</a><a><FileCheck2 size={18}/> Documents</a><a><ShieldCheck size={18}/> Policies</a></nav><div className="side-bottom"><div className="avatar">SK</div><div><b>{auth.displayName}</b><small>Workspace admin</small></div></div></aside><main><header><div><small>WORKSPACE / OPERATIONS</small><h1>Onboarding overview</h1></div><div className="header-actions">{auth.enabled&&<button className="secondary" onClick={()=>void auth.logout()}>Sign out</button>}<button className="primary" onClick={() => window.location.href = 'http://localhost:3000'}>+ New worker</button></div></header><section className="metrics"><Metric title="Active cases" value="128" note="↑ 12% this month" icon={<Users/>}/><Metric title="Needs review" value="14" note="4 due today" icon={<Clock3/>}/><Metric title="Avg. verification" value="6.4h" note="↓ 18% vs last month" icon={<FileCheck2/>}/><Metric title="Policy pass rate" value="96.8%" note="Across 4 regions" icon={<ShieldCheck/>}/></section><section className="panel"><div className="panel-head"><div><h2>Recent onboarding cases</h2><p>Track document checks, decisions, and outstanding actions.</p></div><label className="search"><Search size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search worker or case"/></label></div><div className="table-wrap"><table><thead><tr><th>WORKER</th><th>ROLE</th><th>STATUS</th><th>DOCUMENTS</th><th>UPDATED</th><th></th></tr></thead><tbody>{visible.map((c: any) => <tr key={c.id}><td><b>{c.name}</b><small>{c.id}</small></td><td>{c.role}</td><td><span className={`badge ${c.status.toLowerCase().replaceAll(' ', '-')}`}>{c.status}</span></td><td>{c.docs}</td><td>{c.time}</td><td><button className="icon"><ArrowUpRight size={17}/></button></td></tr>)}</tbody></table></div><footer><span>Showing {visible.length} of {cases.length} cases</span><button>View all cases →</button></footer></section><div className="notice"><CheckCircle2 size={18}/><span><b>Automations are running normally</b><small>Document processing and event delivery are operational.</small></span><button>View activity</button></div></main></div>;
}
function Metric({title,value,note,icon}:any){return <article className="metric"><div className="metric-top"><span>{title}</span><i>{icon}</i></div><strong>{value}</strong><small>{note}</small></article>}
const auth=createOpsBridgeAuth({url:import.meta.env.VITE_KEYCLOAK_URL,realm:'opsbridge',clientId:'opsbridge-operations',tenantFallback:'demo-tenant'});
void auth.initialize().then(()=>createRoot(document.getElementById('root')!).render(<App auth={auth}/>)).catch(error=>{console.error('Identity provider could not be initialized.',error);document.getElementById('root')!.textContent='Sign-in service is unavailable.';});
