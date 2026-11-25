import hashlib,os
import httpx
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import CaseDocument,OnboardingCase,AuditEvent,EventOutbox
from .tracing import tag_current_span

def ai_headers(tenant_id,correlation_id=None):
 headers={'X-Tenant-Id':tenant_id}
 if correlation_id:headers['X-Correlation-Id']=correlation_id
 token=os.getenv('INTERNAL_SERVICE_TOKEN','')
 if token:headers['X-Internal-Service-Token']=token
 return headers

@shared_task(bind=True,max_retries=6,default_retry_delay=20,autoretry_for=(httpx.HTTPError,),retry_backoff=True,retry_jitter=True)
def process_document(self,document_id,correlation_id=None):
 tag_current_span(correlation_id)
 doc=CaseDocument.objects.select_related('case').get(pk=document_id);doc.status='processing';doc.save(update_fields=['status','updated_at'])
 text=''
 suffix=doc.original_name.lower().rsplit('.',1)[-1] if '.' in doc.original_name else ''
 try:
  if suffix=='txt':
   with doc.file.open('rb') as f:text=f.read(100000).decode('utf-8','replace')
  elif suffix=='pdf':
   import fitz
   with doc.file.open('rb') as f: raw=f.read()
   pdf=fitz.open(stream=raw,filetype='pdf')
   text='\n'.join(page.get_text() for page in list(pdf)[:12])[:100000]
   if not text.strip():
    import io,pytesseract
    from PIL import Image
    text='\n'.join(pytesseract.image_to_string(Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).tobytes('png')))) for page in list(pdf)[:5])[:100000]
  elif suffix in {'png','jpg','jpeg'}:
   import pytesseract
   from PIL import Image
   with doc.file.open('rb') as f:text=pytesseract.image_to_string(Image.open(f))[:100000]
 except Exception:
  doc.status='review_required';doc.warnings=['Document extraction could not read this file. A human reviewer must inspect it.'];doc.save(update_fields=['status','warnings','updated_at'])
  refresh_case_recommendation.delay(str(doc.case_id),correlation_id=correlation_id)
  return {'document_id':str(doc.id),'status':doc.status}
 if not text.strip():
  doc.status='review_required';doc.warnings=['No readable text was found. A human reviewer must inspect this document.'];doc.save(update_fields=['status','warnings','updated_at']);refresh_case_recommendation.delay(str(doc.case_id),correlation_id=correlation_id);return {'document_id':str(doc.id),'status':doc.status}
 response=httpx.post(os.getenv('AI_SERVICE_URL','http://localhost:8002')+'/v1/extract',json={'document_text':text,'document_type':doc.document_type},headers=ai_headers(doc.tenant_id,correlation_id),timeout=60);response.raise_for_status();result=response.json()
 with transaction.atomic():
  doc.extracted_fields=result.get('fields',{});doc.confidence=float(result.get('confidence',0));doc.warnings=result.get('warnings',[]);doc.status='review_required' if result.get('human_review_required') or not result.get('fields') else 'processed';doc.save(update_fields=['extracted_fields','confidence','warnings','status','updated_at'])
  case=OnboardingCase.objects.select_for_update().get(pk=doc.case_id,tenant_id=doc.tenant_id);case.extraction={**case.extraction,str(doc.id):doc.extracted_fields};case.status='review_required' if doc.status=='review_required' else 'processing';case.save(update_fields=['extraction','status','version','updated_at']);case.version+=1;case.save(update_fields=['version'])
  AuditEvent.objects.create(tenant_id=case.tenant_id,case=case,actor_id='system:celery',event_type='document.processed',details={'document_id':str(doc.id),'status':doc.status,'warnings':doc.warnings},correlation_id=correlation_id or '')
  EventOutbox.objects.create(tenant_id=case.tenant_id,event_type='document.processed',aggregate_id=str(case.id),payload={'documentId':str(doc.id),'status':doc.status,'correlationId':correlation_id})
 refresh_case_recommendation.delay(str(case.id),correlation_id=correlation_id)
 return {'document_id':str(doc.id),'status':doc.status}

@shared_task(bind=True,max_retries=6,default_retry_delay=10,autoretry_for=(httpx.HTTPError,),retry_backoff=True,retry_jitter=True)
def refresh_case_recommendation(self,case_id,correlation_id=None):
 tag_current_span(correlation_id)
 case=OnboardingCase.objects.prefetch_related('documents').get(pk=case_id)
 documents=[{'document_type':d.document_type,'fields':d.extracted_fields,'confidence':d.confidence,'human_review_required':d.status=='review_required','warnings':d.warnings} for d in case.documents.all()]
 policy=os.getenv('DEFAULT_ONBOARDING_POLICY','Workers must submit valid, unexpired identity and work eligibility records. Escalate name conflicts, missing data, or uncertain extraction to a human reviewer.')
 response=httpx.post(os.getenv('AI_SERVICE_URL','http://localhost:8002')+'/v1/recommend',json={'case_id':str(case.id),'worker_profile':{'name':case.worker_name,'role':case.role,'country':case.country},'extracted_documents':documents,'policy_text':policy},headers=ai_headers(case.tenant_id,correlation_id),timeout=60);response.raise_for_status();recommendation=response.json()
 with transaction.atomic():
  case=OnboardingCase.objects.select_for_update().get(pk=case_id)
  case.ai_recommendation=recommendation
  next_status='review_required' if recommendation.get('human_decision_required',True) else 'ready'
  if case.status not in {'approved','rejected','changes_requested'}:case.status=next_status
  case.version+=1;case.save(update_fields=['ai_recommendation','status','version','updated_at'])
  AuditEvent.objects.create(tenant_id=case.tenant_id,case=case,actor_id='system:ai-runtime',event_type='case.ai_recommendation_updated',details={'suggested_next_step':recommendation.get('suggested_next_step'),'human_decision_required':recommendation.get('human_decision_required'),'policy_sources':recommendation.get('policy_sources',[])},correlation_id=correlation_id or '')
  EventOutbox.objects.create(tenant_id=case.tenant_id,event_type='case.ai_recommendation_updated',aggregate_id=str(case.id),payload={'status':case.status,'suggestedNextStep':recommendation.get('suggested_next_step'),'humanDecisionRequired':recommendation.get('human_decision_required'),'correlationId':correlation_id})
 return {'case_id':str(case.id),'suggested_next_step':recommendation.get('suggested_next_step')}

@shared_task(bind=True,max_retries=8,default_retry_delay=5,autoretry_for=(Exception,),retry_backoff=True,retry_jitter=True)
def publish_pending_events(self):
 from .events import dispatch_outbox
 pending=list(EventOutbox.objects.filter(published_at__isnull=True).order_by('created_at').values_list('id',flat=True)[:100])
 for event_id in pending:dispatch_outbox(event_id)
 return {'published':len(pending)}
