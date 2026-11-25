import json,os
import httpx
from django.utils import timezone
from .models import EventOutbox

def _producer_class():
 from confluent_kafka import Producer
 return Producer

def dispatch_outbox(event_id):
 event=EventOutbox.objects.get(pk=event_id)
 if event.published_at:return
 producer=_producer_class()({'bootstrap.servers':os.getenv('KAFKA_BOOTSTRAP_SERVERS','localhost:9092'),'security.protocol':os.getenv('KAFKA_SECURITY_PROTOCOL','plaintext'),'enable.idempotence':True,'acks':'all'})
 delivery_errors=[]
 domain_event={'eventId':str(event.id),'eventType':event.event_type,'occurredAt':event.created_at.isoformat(),'tenantId':event.tenant_id,'caseId':event.aggregate_id,'payload':event.payload}
 if event.payload.get('correlationId') is not None:domain_event['correlationId']=event.payload['correlationId']
 producer.produce('opsbridge.domain.v1',key=event.aggregate_id,value=json.dumps(domain_event,default=str),on_delivery=lambda error,_message: delivery_errors.append(error) if error else None)
 remaining=producer.flush(10)
 if remaining or delivery_errors:raise RuntimeError('Kafka did not confirm delivery of the outbox event.')
 # Redis Pub/Sub is a best-effort live-update channel; Kafka remains durable.
 realtime_url=os.getenv('REALTIME_SERVICE_URL')
 if realtime_url:
  live_event={'eventId':str(event.id),'eventType':event.event_type,'caseId':event.aggregate_id,'tenantId':event.tenant_id,'status':event.payload.get('status'),'occurredAt':event.created_at.isoformat(),'correlationId':event.payload.get('correlationId')}
  headers={'X-Tenant-Id':event.tenant_id}
  token=os.getenv('INTERNAL_SERVICE_TOKEN','')
  if token:headers['X-Internal-Service-Token']=token
  try:httpx.post(realtime_url.rstrip('/')+'/v1/publish',json=live_event,headers=headers,timeout=2).raise_for_status()
  except httpx.HTTPError:pass
 event.attempts+=1;event.published_at=timezone.now();event.save(update_fields=['attempts','published_at'])
