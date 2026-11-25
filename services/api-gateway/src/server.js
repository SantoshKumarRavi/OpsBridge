import crypto from 'node:crypto';
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import { RedisStore } from 'rate-limit-redis';
import { createClient } from 'redis';
import multer from 'multer';
import pino from 'pino';
import pinoHttp from 'pino-http';
import { createRemoteJWKSet, jwtVerify, SignJWT } from 'jose';
import { collectDefaultMetrics, Registry, Counter, Histogram } from 'prom-client';

const app=express(), log=pino({level:process.env.LOG_LEVEL??'info'}), registry=new Registry();
collectDefaultMetrics({register:registry});
const requests=new Counter({name:'opsbridge_gateway_requests_total',help:'API requests by route, method, and response',labelNames:['method','route','status'],registers:[registry]});
const requestDuration=new Histogram({name:'opsbridge_gateway_request_duration_seconds',help:'Gateway request duration in seconds by route and method',labelNames:['method','route'],buckets:[0.05,0.1,0.25,0.5,1,2,5,10],registers:[registry]});
const targets={compliance:process.env.COMPLIANCE_SERVICE_URL??'http://localhost:8001',ai:process.env.AI_SERVICE_URL??'http://localhost:8002',integrations:process.env.INTEGRATION_SERVICE_URL??'http://localhost:8083',telemetry:process.env.TELEMETRY_SERVICE_URL??'http://localhost:8090'};
const rateLimitRedisUrl=process.env.RATE_LIMIT_REDIS_URL??process.env.REDIS_URL;
const rateLimitRedis=rateLimitRedisUrl?createClient({url:rateLimitRedisUrl}):undefined;
rateLimitRedis?.on('error',error=>log.error({err:error},'Redis rate-limit store error'));
if(process.env.APP_ENV==='production'&&!rateLimitRedis)throw new Error('RATE_LIMIT_REDIS_URL is required in production.');
if(rateLimitRedis)await rateLimitRedis.connect();
const rateLimitStore=rateLimitRedis?new RedisStore({
  prefix:'opsbridge:gateway:rate-limit:',
  sendCommand:(...args)=>rateLimitRedis.sendCommand(args),
}):undefined;
const issuer=process.env.OIDC_ISSUER, jwksUrl=process.env.OIDC_JWKS_URL, jwks=jwksUrl?createRemoteJWKSet(new URL(jwksUrl)):null;
const realtimeTicketSecret=process.env.REALTIME_TICKET_SECRET??(process.env.APP_ENV==='production'?'':'local-realtime-ticket-secret-change-me');
app.disable('x-powered-by');
app.use(helmet());
app.use(cors({origin:(process.env.ALLOWED_ORIGINS??'http://localhost:3000,http://localhost:3002,http://localhost:4173,http://localhost:4200,http://localhost:4301,http://localhost:5173').split(',').map(s=>s.trim()),credentials:true}));
app.use(pinoHttp({
  logger:log,
  genReqId(req,res){
    const supplied=req.headers['x-correlation-id'];
    const correlationId=typeof supplied==='string'&&/^[A-Za-z0-9._:-]{1,100}$/.test(supplied)?supplied:crypto.randomUUID();
    res.setHeader('X-Correlation-Id',correlationId);
    return correlationId;
  },
  customProps(req){return {correlationId:req.id};}
}));
app.use((req,res,next)=>{
  const started=process.hrtime.bigint();
  res.once('finish',()=>{
    const route=req.route?.path||req.baseUrl||'unmatched';
    requests.inc({method:req.method,route,status:String(res.statusCode)});
    requestDuration.observe({method:req.method,route},Number(process.hrtime.bigint()-started)/1e9);
  });
  next();
});
// API payloads include tenant-scoped personal data and must never enter shared or browser caches.
app.use('/api/',(_req,res,next)=>{
  res.setHeader('Cache-Control','private, no-store');
  next();
});
app.use('/api/',rateLimit({windowMs:60_000,limit:120,standardHeaders:'draft-7',legacyHeaders:false,...(rateLimitStore?{store:rateLimitStore}:{})}));
app.use(express.json({limit:'1mb'}));

async function identity(req,res,next){
  try{
    const token=req.headers.authorization?.replace(/^Bearer\s+/i,'');
    if(token&&jwks){
      const{payload}=await jwtVerify(token,jwks,{issuer,audience:process.env.OIDC_AUDIENCE});
      const tenantId=payload.tenant_id;
      if(typeof tenantId!=='string'||!tenantId||tenantId.length>100)return res.status(403).json({error:'Token is missing a valid tenant claim.'});
      req.identity={sub:payload.sub,tenantId,roles:payload.roles??payload.realm_access?.roles??[]};return next();
    }
    if(token||process.env.APP_ENV==='production'||process.env.DEV_IDENTITY_ENABLED!=='true')return res.status(401).json({error:'A valid access token is required.'});
    const tenantId=String(req.headers['x-tenant-id']??'demo-tenant');
    if(!/^[a-zA-Z0-9_-]{1,100}$/.test(tenantId))return res.status(400).json({error:'Invalid tenant identifier.'});
    req.identity={sub:'local-demo-user',tenantId,roles:['opsbridge-admin','operations-user']};return next();
  }catch{return res.status(401).json({error:'Access token is invalid or expired.'});}
}
function requireAnyRole(...allowed){return(req,res,next)=>{if(req.identity?.roles?.some(role=>allowed.includes(role)))return next();return res.status(403).json({error:'Your account does not have permission for this action.'});};}

async function relay(req,res,target,path,bodyOverride){
  try{
    const url=new URL(path,targets[target]);
    for(const[k,v]of Object.entries(req.query))if(typeof v==='string')url.searchParams.set(k,v);
    const headers={'X-Tenant-Id':req.identity.tenantId,'X-Actor-Id':req.identity.sub,'X-Correlation-Id':req.id};
    if(process.env.INTERNAL_SERVICE_TOKEN)headers['X-Internal-Service-Token']=process.env.INTERNAL_SERVICE_TOKEN;
    if(req.headers['content-type']&&!(bodyOverride instanceof FormData))headers['Content-Type']=req.headers['content-type'];
    let body=bodyOverride;
    if(body===undefined&&req.body!==undefined&&req.method!=='GET'&&req.method!=='HEAD'){body=JSON.stringify(req.body);headers['Content-Type']='application/json';}
    const upstream=await fetch(url,{method:req.method,headers,body:['GET','HEAD'].includes(req.method)?undefined:body,signal:AbortSignal.timeout(30_000)});
    res.status(upstream.status);for(const name of['content-type','retry-after'])if(upstream.headers.has(name))res.set(name,upstream.headers.get(name));
    res.send(Buffer.from(await upstream.arrayBuffer()));
  }catch(error){req.log?.error({err:error,target},'Upstream request failed');res.status(503).json({error:'The requested service is temporarily unavailable.'});}
}

app.get('/health',(_req,res)=>res.json({status:'ok',service:'api-gateway',identity:issuer?'oidc':'development-mock'}));
app.get('/metrics',async(_req,res)=>{res.set('Content-Type',registry.contentType);res.end(await registry.metrics());});
app.post('/api/v1/realtime/ticket',identity,async(req,res)=>{
  if(!realtimeTicketSecret||realtimeTicketSecret.length<32)return res.status(503).json({error:'Realtime ticket signing is not configured.'});
  try{
    const ticket=await new SignJWT({tenant_id:req.identity.tenantId,roles:req.identity.roles})
      .setProtectedHeader({alg:'HS256'}).setIssuer('opsbridge-api-gateway').setAudience('opsbridge-realtime')
      .setSubject(req.identity.sub).setJti(crypto.randomUUID()).setIssuedAt().setExpirationTime('30s')
      .sign(new TextEncoder().encode(realtimeTicketSecret));
    return res.json({ticket,expiresIn:30,websocketUrl:process.env.REALTIME_WS_URL??'ws://localhost:8091/ws/cases'});
  }catch{return res.status(500).json({error:'Could not issue a realtime session.'});}
});
app.get('/api/v1/cases',identity,(req,res)=>relay(req,res,'compliance','/api/v1/cases'));
app.post('/api/v1/cases',identity,(req,res)=>relay(req,res,'compliance','/api/v1/cases'));
app.get('/api/v1/cases/:caseId',identity,(req,res)=>relay(req,res,'compliance',`/api/v1/cases/${encodeURIComponent(req.params.caseId)}`));
const upload=multer({storage:multer.memoryStorage(),limits:{fileSize:15*1024*1024,files:1},fileFilter:(_req,file,callback)=>callback(null,['application/pdf','image/png','image/jpeg','text/plain'].includes(file.mimetype))}).single('file');
app.post('/api/v1/cases/:caseId/documents',identity,upload,async(req,res)=>{
  if(!req.file)return res.status(400).json({error:'A PDF, PNG, JPEG, or text file is required.'});
  const form=new FormData();form.append('file',new Blob([req.file.buffer],{type:req.file.mimetype}),req.file.originalname.replace(/[\r\n/\\]/g,'_'));form.append('documentType',String(req.body.documentType??'identity'));
  return relay(req,res,'compliance',`/api/v1/cases/${encodeURIComponent(req.params.caseId)}/documents`,form);
});
app.use('/api/v1/ai',identity,(req,res)=>relay(req,res,'ai',`/v1${req.path}`));
app.post('/api/v1/cases/:caseId/decision',identity,requireAnyRole('opsbridge-admin','compliance-reviewer'),(req,res)=>relay(req,res,'compliance',`/api/v1/cases/${encodeURIComponent(req.params.caseId)}/decision`));
app.get('/api/v1/voice/contacts',identity,requireAnyRole('opsbridge-admin','compliance-reviewer'),(req,res)=>relay(req,res,'compliance','/api/v1/voice/contacts'));
app.put('/api/v1/voice/contacts',identity,requireAnyRole('opsbridge-admin','compliance-reviewer'),(req,res)=>relay(req,res,'compliance','/api/v1/voice/contacts'));
app.get('/api/v1/voice/contacts/eligibility',identity,requireAnyRole('opsbridge-admin','compliance-reviewer'),(req,res)=>relay(req,res,'compliance','/api/v1/voice/contacts/eligibility'));
app.use('/api/v1/billing',identity,requireAnyRole('opsbridge-admin','operations-user'),(req,res)=>relay(req,res,'integrations',`/api/v1/billing${req.path==='/'?'':req.path}`));
app.use('/api/v1/integrations',identity,requireAnyRole('opsbridge-admin','operations-user'),(req,res)=>relay(req,res,'integrations',`/api/v1/integrations${req.path==='/'?'':req.path}`));
app.use('/api/v1/telemetry',identity,(req,res)=>relay(req,res,'telemetry',`/v1/telemetry`));
app.use('/api/v1',identity,(req,res)=>relay(req,res,'compliance',`/api/v1${req.path}`));
app.use((err,_req,res,_next)=>{if(err?.code==='LIMIT_FILE_SIZE')return res.status(413).json({error:'File exceeds the 15 MB limit.'});if(err instanceof multer.MulterError)return res.status(400).json({error:'Invalid file upload.'});return res.status(500).json({error:'Unexpected gateway error.'});});
const port=Number(process.env.PORT??8080);
const server=app.listen(port,'0.0.0.0',()=>log.info({port,identity:issuer?'oidc':'development-mock',rateLimitStore:rateLimitRedis?'redis':'memory'},'OpsBridge API gateway listening'));
async function shutdown(signal){
  log.info({signal},'OpsBridge API gateway shutting down');
  server.close(async error=>{
    if(error)log.error({err:error},'Gateway HTTP server shutdown failed');
    if(rateLimitRedis?.isOpen)await rateLimitRedis.quit().catch(redisError=>log.error({err:redisError},'Redis client shutdown failed'));
    process.exitCode=error?1:0;
  });
}
process.once('SIGTERM',()=>void shutdown('SIGTERM'));
process.once('SIGINT',()=>void shutdown('SIGINT'));
