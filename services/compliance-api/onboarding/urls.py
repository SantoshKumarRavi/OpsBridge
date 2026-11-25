from django.urls import path
from .views import CaseCollection,CaseDetail,DocumentUpload,CaseDecision,VoiceContactUpdate,VoiceContactEligibility
urlpatterns=[path('cases',CaseCollection.as_view()),path('cases/<uuid:case_id>',CaseDetail.as_view()),path('cases/<uuid:case_id>/documents',DocumentUpload.as_view()),path('cases/<uuid:case_id>/decision',CaseDecision.as_view()),path('voice/contacts',VoiceContactUpdate.as_view()),path('voice/contacts/eligibility',VoiceContactEligibility.as_view())]
