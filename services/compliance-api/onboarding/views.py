import hashlib,hmac,os,re,uuid
from django.core import signing
from django.db import transaction
from django.http import JsonResponse
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser,MultiPartParser,FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import OnboardingCase,CaseDocument,AuditEvent,EventOutbox,VoiceContact,VoicePolicyAudit
from .serializers import CaseCreateSerializer,CaseSerializer,VoiceContactUpdateSerializer
from .tasks import process_document

def tenant(request):
 if os.getenv('APP_ENV')=='production':
  expected=os.getenv('INTERNAL_SERVICE_TOKEN','')
  if not expected or not hmac.compare_digest(request.headers.get('X-Internal-Service-Token',''),expected):return None
 value=request.headers.get('X-Tenant-Id','demo-tenant')
 return value if value and len(value)<=100 else None
def health(request):return JsonResponse({'status':'ok','service':'compliance-api'})
CASE_LIST_CURSOR_SALT='opsbridge.case-list.cursor.v1'
def encode_case_cursor(case,tenant_id,status_filter):
 return signing.dumps({'created_at':case.created_at.isoformat(),'id':str(case.id),'tenant_id':tenant_id,'status':status_filter},salt=CASE_LIST_CURSOR_SALT,compress=True)
class CaseCollection(APIView):
 def get(self,request):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  status_filter=request.query_params.get('status') or None
  valid_statuses={value for value,_label in OnboardingCase.STATUS}
  if status_filter and status_filter not in valid_statuses:return Response({'error':'Invalid case status filter.'},status=400)
  try:limit=int(request.query_params.get('limit','50'))
  except (TypeError,ValueError):return Response({'error':'limit must be an integer between 1 and 100.'},status=400)
  if limit<1 or limit>100:return Response({'error':'limit must be an integer between 1 and 100.'},status=400)
  qs=OnboardingCase.objects.filter(tenant_id=tenant_id)
  if status_filter:qs=qs.filter(status=status_filter)
  total=qs.count()
  cursor=request.query_params.get('cursor')
  if cursor:
   try:
    payload=signing.loads(cursor,salt=CASE_LIST_CURSOR_SALT,max_age=86400)
    if not isinstance(payload,dict) or payload.get('tenant_id')!=tenant_id or payload.get('status')!=status_filter:raise signing.BadSignature('Cursor scope mismatch.')
    cursor_created_at=parse_datetime(payload.get('created_at',''))
    cursor_id=uuid.UUID(payload.get('id',''))
    if cursor_created_at is None:raise signing.BadSignature('Cursor timestamp is invalid.')
   except (signing.BadSignature,TypeError,ValueError):return Response({'error':'Invalid or expired case-list cursor.'},status=400)
   qs=qs.filter(Q(created_at__lt=cursor_created_at)|Q(created_at=cursor_created_at,id__lt=cursor_id))
  qs=qs.order_by('-created_at','-id').prefetch_related('documents','audit_events')
  rows=list(qs[:limit+1]);has_more=len(rows)>limit;page=rows[:limit]
  next_cursor=encode_case_cursor(page[-1],tenant_id,status_filter) if has_more and page else None
  items=CaseSerializer(page,many=True).data
  return Response({'items':items,'total':total,'next_cursor':next_cursor})
 def post(self,request):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  serializer=CaseCreateSerializer(data=request.data)
  if not serializer.is_valid():return Response(serializer.errors,status=400)
  with transaction.atomic():
   case=serializer.save(tenant_id=tenant_id)
   actor=request.headers.get('X-Actor-Id','local-demo-user')
   AuditEvent.objects.create(tenant_id=tenant_id,case=case,actor_id=actor,event_type='case.created',details={'role':case.role,'country':case.country},correlation_id=request.correlation_id)
   EventOutbox.objects.create(tenant_id=tenant_id,event_type='case.created',aggregate_id=str(case.id),payload={'workerName':case.worker_name,'role':case.role,'status':case.status,'correlationId':request.correlation_id})
  return Response(CaseSerializer(case).data,status=status.HTTP_201_CREATED)
class CaseDetail(APIView):
 def get(self,request,case_id):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  try:case=OnboardingCase.objects.prefetch_related('documents','audit_events').get(pk=case_id,tenant_id=tenant_id)
  except (OnboardingCase.DoesNotExist,ValueError):return Response({'error':'Case not found.'},status=404)
  return Response(CaseSerializer(case).data)
class DocumentUpload(APIView):
 parser_classes=[MultiPartParser,FormParser]
 def post(self,request,case_id):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  try:case=OnboardingCase.objects.get(pk=case_id,tenant_id=tenant_id)
  except (OnboardingCase.DoesNotExist,ValueError):return Response({'error':'Case not found.'},status=404)
  uploaded=request.FILES.get('file');doc_type=str(request.data.get('documentType','identity'))[:80]
  if not uploaded:return Response({'error':'File is required.'},status=400)
  if uploaded.size>15*1024*1024:return Response({'error':'File exceeds 15 MB.'},status=413)
  if uploaded.content_type not in {'application/pdf','image/png','image/jpeg','text/plain'}:return Response({'error':'Only PDF, PNG, JPEG, or plain text files are accepted.'},status=415)
  digest=hashlib.sha256();
  for chunk in uploaded.chunks():digest.update(chunk)
  uploaded.seek(0)
  doc=CaseDocument.objects.create(tenant_id=tenant_id,case=case,document_type=doc_type,file=uploaded,original_name=os.path.basename(uploaded.name)[:255],mime_type=uploaded.content_type,size_bytes=uploaded.size,sha256=digest.hexdigest())
  with transaction.atomic():
   case.status='processing';case.version+=1;case.save(update_fields=['status','version','updated_at'])
   AuditEvent.objects.create(tenant_id=tenant_id,case=case,actor_id=request.headers.get('X-Actor-Id','local-demo-user'),event_type='document.received',details={'document_id':str(doc.id),'document_type':doc_type,'sha256':doc.sha256},correlation_id=request.correlation_id)
   EventOutbox.objects.create(tenant_id=tenant_id,event_type='document.received',aggregate_id=str(case.id),payload={'documentId':str(doc.id),'documentType':doc_type,'correlationId':request.correlation_id})
  process_document.delay(str(doc.id),correlation_id=request.correlation_id)
  return Response({'id':str(doc.id),'caseId':str(case.id),'status':'queued'},status=202)
class CaseDecision(APIView):
 def post(self,request,case_id):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  decision=request.data.get('decision');reason=str(request.data.get('reason','')).strip()
  if decision not in {'approve','reject','request_changes'} or not reason:return Response({'error':'A valid decision and reason are required.'},status=400)
  with transaction.atomic():
   try:case=OnboardingCase.objects.select_for_update().get(pk=case_id,tenant_id=tenant_id)
   except (OnboardingCase.DoesNotExist,ValueError):return Response({'error':'Case not found.'},status=404)
   if case.status in {'approved','rejected'}:return Response({'error':'This case already has a final decision.'},status=409)
   case.status={'approve':'approved','reject':'rejected','request_changes':'changes_requested'}[decision];case.decision_reason=reason;case.version+=1;case.save()
   event_type='case.'+case.status;AuditEvent.objects.create(tenant_id=tenant_id,case=case,actor_id=request.headers.get('X-Actor-Id','local-demo-user'),event_type=event_type,details={'reason':reason,'decision':decision},correlation_id=request.correlation_id)
   EventOutbox.objects.create(tenant_id=tenant_id,event_type=event_type,aggregate_id=str(case.id),payload={'decision':decision,'reason':reason,'version':case.version,'correlationId':request.correlation_id})
  return Response(CaseSerializer(case).data)

def voice_policy_state(contact):
 return {'consentStatus':contact.consent_status,'consentRecordedAt':contact.consent_recorded_at.isoformat() if contact.consent_recorded_at else None,'consentSource':contact.consent_source,'consentReference':contact.consent_reference,'suppressed':contact.suppressed,'suppressionReason':contact.suppression_reason}

class VoiceContactUpdate(APIView):
 def get(self,request):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  phone_number=request.query_params.get('phoneNumber','')
  if not re.fullmatch(r'\+[1-9][0-9]{6,14}',phone_number):return Response({'error':'phoneNumber must use E.164 format.'},status=400)
  contact=VoiceContact.objects.filter(tenant_id=tenant_id,phone_number=phone_number).first()
  if contact is None:return Response({'error':'Voice contact policy not found.'},status=404)
  return Response({'phoneNumber':contact.phone_number,**voice_policy_state(contact)})

 def put(self,request):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  serializer=VoiceContactUpdateSerializer(data=request.data)
  if not serializer.is_valid():return Response(serializer.errors,status=400)
  values=dict(serializer.validated_data);phone_number=values.pop('phoneNumber')
  with transaction.atomic():
   contact,created=VoiceContact.objects.select_for_update().get_or_create(tenant_id=tenant_id,phone_number=phone_number)
   before=None if created else voice_policy_state(contact)
   for field,value in values.items():setattr(contact,field,value)
   contact.updated_by=request.headers.get('X-Actor-Id','unknown')
   contact.save()
   after=voice_policy_state(contact)
   if before!=after:
    VoicePolicyAudit.objects.create(tenant_id=tenant_id,contact=contact,actor_id=contact.updated_by,event_type='voice_contact.policy_updated',details={'before':before,'after':after},correlation_id=request.correlation_id)
  return Response({'phoneNumber':contact.phone_number,**after})

class VoiceContactEligibility(APIView):
 def get(self,request):
  tenant_id=tenant(request)
  if not tenant_id:return Response({'error':'Trusted tenant context required.'},status=401)
  phone_number=request.query_params.get('phoneNumber','')
  if not re.fullmatch(r'\+[1-9][0-9]{6,14}',phone_number):return Response({'error':'phoneNumber must use E.164 format.'},status=400)
  contact=VoiceContact.objects.filter(tenant_id=tenant_id,phone_number=phone_number).first()
  if contact is None:return Response({'eligible':False,'reason':'no_record'})
  if contact.suppressed:return Response({'eligible':False,'reason':'suppressed'})
  if contact.consent_status!='granted' or not contact.consent_recorded_at:return Response({'eligible':False,'reason':'consent_not_granted'})
  if contact.consent_recorded_at>timezone.now():return Response({'eligible':False,'reason':'invalid_consent_timestamp'})
  return Response({'eligible':True,'reason':'eligible'})
