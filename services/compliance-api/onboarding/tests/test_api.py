import os
from unittest.mock import patch
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from rest_framework.test import APIClient
import yaml

from onboarding.models import AuditEvent, CaseDocument, EventOutbox, OnboardingCase, VoiceContact, VoicePolicyAudit
from onboarding.views import DocumentUpload, tenant


class TenantContextTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_production_requires_a_configured_internal_service_token(self):
        request = self.factory.get("/", HTTP_X_INTERNAL_SERVICE_TOKEN="caller-token")

        with patch.dict(os.environ, {"APP_ENV": "production", "INTERNAL_SERVICE_TOKEN": ""}, clear=True):
            self.assertIsNone(tenant(request))

    def test_production_rejects_missing_or_incorrect_internal_service_token(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "INTERNAL_SERVICE_TOKEN": "expected"}, clear=True):
            missing = self.factory.get("/", HTTP_X_TENANT_ID="tenant-a")
            incorrect = self.factory.get(
                "/", HTTP_X_TENANT_ID="tenant-a", HTTP_X_INTERNAL_SERVICE_TOKEN="wrong"
            )

            self.assertIsNone(tenant(missing))
            self.assertIsNone(tenant(incorrect))

    def test_production_accepts_matching_internal_token_and_tenant(self):
        request = self.factory.get(
            "/", HTTP_X_TENANT_ID="tenant-a", HTTP_X_INTERNAL_SERVICE_TOKEN="expected"
        )

        with patch.dict(os.environ, {"APP_ENV": "production", "INTERNAL_SERVICE_TOKEN": "expected"}, clear=True):
            self.assertEqual(tenant(request), "tenant-a")

    def test_tenant_identifier_must_be_nonempty_and_at_most_100_characters(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(tenant(self.factory.get("/", HTTP_X_TENANT_ID="")))
            self.assertIsNone(tenant(self.factory.get("/", HTTP_X_TENANT_ID="x" * 101)))
            self.assertEqual(tenant(self.factory.get("/", HTTP_X_TENANT_ID="x" * 100)), "x" * 100)


class ComplianceApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        contract_path = Path(__file__).resolve().parents[4] / "packages" / "contracts" / "openapi.yaml"
        cls.openapi = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        validate_spec(cls.openapi)
        cls.openapi_registry = Registry().with_resource(
            "https://opsbridge.local/openapi.yaml",
            Resource.from_contents(cls.openapi, default_specification=DRAFT202012),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.defaults["HTTP_X_TENANT_ID"] = "tenant-a"
        self.client.defaults["HTTP_X_ACTOR_ID"] = "reviewer-7"

    def assert_contract_response(self, path, method, status_code, response_data):
        response_spec = self.openapi["paths"][path][method]["responses"][str(status_code)]
        while "$ref" in response_spec:
            reference = response_spec["$ref"].split("#", 1)[1].strip("/").split("/")
            response_spec = self.openapi
            for component in reference:
                response_spec = response_spec[component]
        schema = response_spec["content"]["application/json"]["schema"]
        validator = Draft202012Validator(
            schema,
            registry=self.openapi_registry,
            _resolver=self.openapi_registry.resolver("https://opsbridge.local/openapi.yaml"),
            format_checker=FormatChecker(),
        )
        validator.validate(response_data)

    def create_case(self, **overrides):
        payload = {
            "workerName": "Example Worker",
            "email": "worker@example.invalid",
            "phone": "+10000000000",
            "role": "Portfolio Tester",
            "country": "us",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/cases", payload, format="json")

    def voice_contact_payload(self, **overrides):
        payload = {
            "phoneNumber": "+15551234567",
            "consentStatus": "granted",
            "consentRecordedAt": timezone.now().isoformat(),
            "consentSource": "signed onboarding form",
            "consentReference": "evidence-ref-42",
            "suppressed": False,
            "suppressionReason": "",
        }
        payload.update(overrides)
        return payload

    def test_voice_contact_grant_is_tenant_scoped_and_audited_then_revocation_blocks(self):
        response = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(), format="json", HTTP_X_CORRELATION_ID="voice-consent-42")
        self.assertEqual(response.status_code, 200, response.data)
        self.assert_contract_response("/voice/contacts", "put", 200, response.data)
        contact = VoiceContact.objects.get(tenant_id="tenant-a", phone_number="+15551234567")
        audit = VoicePolicyAudit.objects.get(contact=contact)
        self.assertEqual(audit.actor_id, "reviewer-7")
        self.assertEqual(audit.correlation_id, "voice-consent-42")
        self.assertEqual(audit.details["after"]["consentStatus"], "granted")
        detail = self.client.get("/api/v1/voice/contacts", {"phoneNumber": "+15551234567"})
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assert_contract_response("/voice/contacts", "get", 200, detail.data)
        self.assertEqual(detail.data["consentSource"], "signed onboarding form")

        eligible = self.client.get("/api/v1/voice/contacts/eligibility", {"phoneNumber": "+15551234567"})
        self.assertEqual(eligible.status_code, 200)
        self.assertEqual(eligible.data, {"eligible": True, "reason": "eligible"})
        self.assert_contract_response("/voice/contacts/eligibility", "get", 200, eligible.data)

        revoked = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(consentStatus="revoked", consentSource="withdrawal request"), format="json")
        self.assertEqual(revoked.status_code, 200, revoked.data)
        self.assertEqual(VoicePolicyAudit.objects.filter(contact=contact).count(), 2)
        blocked = self.client.get("/api/v1/voice/contacts/eligibility", {"phoneNumber": "+15551234567"})
        self.assertEqual(blocked.data, {"eligible": False, "reason": "consent_not_granted"})

    def test_voice_suppression_blocks_call_and_contact_is_invisible_to_other_tenants(self):
        response = self.client.put(
            "/api/v1/voice/contacts",
            self.voice_contact_payload(suppressed=True, suppressionReason="customer requested no calls"),
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        blocked = self.client.get("/api/v1/voice/contacts/eligibility", {"phoneNumber": "+15551234567"})
        self.assertEqual(blocked.data, {"eligible": False, "reason": "suppressed"})

        self.client.defaults["HTTP_X_TENANT_ID"] = "tenant-b"
        detail = self.client.get("/api/v1/voice/contacts", {"phoneNumber": "+15551234567"})
        not_visible = self.client.get("/api/v1/voice/contacts/eligibility", {"phoneNumber": "+15551234567"})
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(not_visible.data, {"eligible": False, "reason": "no_record"})

    def test_voice_contact_rejects_invalid_phone_future_timestamp_and_incomplete_grant(self):
        invalid_phone = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(phoneNumber="123"), format="json")
        future_timestamp = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(consentRecordedAt=(timezone.now() + timezone.timedelta(days=1)).isoformat()), format="json")
        incomplete_grant = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(consentSource=""), format="json")
        self.assertEqual(invalid_phone.status_code, 400)
        self.assertEqual(future_timestamp.status_code, 400)
        self.assertEqual(incomplete_grant.status_code, 400)
        self.assertEqual(VoiceContact.objects.count(), 0)

    @patch.dict(os.environ, {"APP_ENV": "production", "INTERNAL_SERVICE_TOKEN": "gateway-secret"}, clear=True)
    def test_voice_contact_management_requires_trusted_service_context(self):
        missing = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(), format="json")
        wrong = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(), format="json", HTTP_X_INTERNAL_SERVICE_TOKEN="wrong")
        trusted = self.client.put("/api/v1/voice/contacts", self.voice_contact_payload(), format="json", HTTP_X_INTERNAL_SERVICE_TOKEN="gateway-secret")
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(trusted.status_code, 200, trusted.data)

    def test_create_persists_case_audit_and_outbox_with_correlation(self):
        response = self.client.post(
            "/api/v1/cases",
            {
                "workerName": "Example Worker",
                "email": "worker@example.invalid",
                "phone": "+10000000000",
                "role": "Portfolio Tester",
                "country": "us",
            },
            format="json",
            HTTP_X_CORRELATION_ID="case-create-42",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assert_contract_response("/cases", "post", 201, response.data)
        case = OnboardingCase.objects.get(pk=response.data["id"])
        self.assertEqual(case.tenant_id, "tenant-a")
        self.assertEqual(case.country, "US")
        audit = AuditEvent.objects.get(case=case)
        self.assertEqual(audit.actor_id, "reviewer-7")
        self.assertEqual(audit.event_type, "case.created")
        self.assertEqual(audit.correlation_id, "case-create-42")
        event = EventOutbox.objects.get(aggregate_id=str(case.id))
        self.assertEqual(event.event_type, "case.created")
        self.assertEqual(event.payload["correlationId"], "case-create-42")
        self.assertEqual(response["X-Correlation-Id"], "case-create-42")

        listing = self.client.get("/api/v1/cases")
        self.assert_contract_response("/cases", "get", 200, listing.data)
        detail = self.client.get(f"/api/v1/cases/{case.id}")
        self.assert_contract_response("/cases/{caseId}", "get", 200, detail.data)

    def test_list_and_detail_are_tenant_scoped(self):
        created = self.create_case()
        case_id = created.data["id"]

        self.client.defaults["HTTP_X_TENANT_ID"] = "tenant-b"
        listing = self.client.get("/api/v1/cases")
        detail = self.client.get(f"/api/v1/cases/{case_id}")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["items"], [])
        self.assertEqual(detail.status_code, 404)

    @patch.dict(os.environ, {"APP_ENV": "production", "INTERNAL_SERVICE_TOKEN": "gateway-secret"}, clear=True)
    def test_production_case_list_requires_trusted_gateway_token(self):
        missing = self.client.get("/api/v1/cases")
        incorrect = self.client.get("/api/v1/cases", HTTP_X_INTERNAL_SERVICE_TOKEN="wrong")
        trusted = self.client.get("/api/v1/cases", HTTP_X_INTERNAL_SERVICE_TOKEN="gateway-secret")

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(incorrect.status_code, 401)
        self.assertEqual(trusted.status_code, 200)

    def test_case_list_cursor_pages_have_stable_order_and_tenant_scope(self):
        case_ids = [self.create_case(workerName=f"Page Worker {index}").data["id"] for index in range(3)]
        same_created_at = timezone.now()
        OnboardingCase.objects.filter(id__in=case_ids).update(created_at=same_created_at)

        first_page = self.client.get("/api/v1/cases?limit=2")
        self.assertEqual(first_page.status_code, 200, first_page.data)
        self.assert_contract_response("/cases", "get", 200, first_page.data)
        self.assertEqual(first_page.data["total"], 3)
        self.assertEqual(len(first_page.data["items"]), 2)
        cursor = first_page.data["next_cursor"]
        self.assertTrue(cursor)

        second_page = self.client.get(f"/api/v1/cases?limit=2&cursor={cursor}")
        self.assertEqual(second_page.status_code, 200, second_page.data)
        self.assertEqual(second_page.data["total"], 3)
        self.assertEqual(len(second_page.data["items"]), 1)
        self.assertIsNone(second_page.data["next_cursor"])
        returned_ids = [item["id"] for item in first_page.data["items"] + second_page.data["items"]]
        self.assertEqual(returned_ids, sorted(case_ids, reverse=True))

        self.client.defaults["HTTP_X_TENANT_ID"] = "tenant-b"
        replayed_cursor = self.client.get(f"/api/v1/cases?limit=2&cursor={cursor}")
        self.assertEqual(replayed_cursor.status_code, 400)
        self.assert_contract_response("/cases", "get", 400, replayed_cursor.data)

    def test_case_list_rejects_invalid_limit_status_and_tampered_cursor(self):
        self.create_case(workerName="Cursor Worker One")
        self.create_case(workerName="Cursor Worker Two")
        page = self.client.get("/api/v1/cases?limit=1")
        cursor = page.data["next_cursor"]
        tampered_cursor = ("A" if cursor[0] != "A" else "B") + cursor[1:]

        for query in ("limit=0", "limit=101", "limit=abc", "status=unknown", f"cursor={tampered_cursor}"):
            with self.subTest(query=query):
                response = self.client.get(f"/api/v1/cases?{query}")
                self.assertEqual(response.status_code, 400, response.data)
                self.assert_contract_response("/cases", "get", 400, response.data)

    def test_invalid_country_does_not_create_case_or_outbox(self):
        response = self.create_case(country="USA")

        self.assertEqual(response.status_code, 400)
        self.assert_contract_response("/cases", "post", 400, response.data)
        self.assertEqual(OnboardingCase.objects.count(), 0)
        self.assertEqual(EventOutbox.objects.count(), 0)

    def test_decision_requires_reason_and_rejects_second_final_decision(self):
        created = self.create_case()
        case_id = created.data["id"]

        missing_reason = self.client.post(
            f"/api/v1/cases/{case_id}/decision",
            {"decision": "approve", "reason": "  "},
            format="json",
        )
        approved = self.client.post(
            f"/api/v1/cases/{case_id}/decision",
            {"decision": "approve", "reason": "Evidence reviewed"},
            format="json",
        )
        second_decision = self.client.post(
            f"/api/v1/cases/{case_id}/decision",
            {"decision": "reject", "reason": "Second attempt"},
            format="json",
        )

        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data["status"], "approved")
        self.assert_contract_response("/cases/{caseId}/decision", "post", 200, approved.data)
        self.assertEqual(second_decision.status_code, 409)
        self.assert_contract_response("/cases/{caseId}/decision", "post", 409, second_decision.data)
        self.assertEqual(
            list(AuditEvent.objects.filter(case_id=case_id).values_list("event_type", flat=True)),
            ["case.created", "case.approved"],
        )

    @patch("onboarding.views.process_document.delay")
    def test_upload_validates_type_and_queues_with_audit_and_outbox(self, enqueue):
        created = self.create_case()
        case_id = created.data["id"]
        invalid = self.client.post(
            f"/api/v1/cases/{case_id}/documents",
            {"file": SimpleUploadedFile("bad.bin", b"no", content_type="application/octet-stream")},
            format="multipart",
        )
        self.assertEqual(invalid.status_code, 415)
        self.assertEqual(CaseDocument.objects.count(), 0)

        request = RequestFactory().post(
            f"/api/v1/cases/{case_id}/documents",
            {"file": SimpleUploadedFile("sample.txt", b"synthetic", content_type="text/plain")},
            format="multipart",
            HTTP_X_TENANT_ID="tenant-a",
            HTTP_X_ACTOR_ID="reviewer-7",
            HTTP_X_CORRELATION_ID="upload-42",
        )
        request.correlation_id = "upload-42"
        uploaded = DocumentUpload.as_view()(request, case_id=case_id)

        self.assertEqual(uploaded.status_code, 202, uploaded.data)
        self.assert_contract_response("/cases/{caseId}/documents", "post", 202, uploaded.data)
        self.assertEqual(uploaded.data["status"], "queued")
        document = CaseDocument.objects.get(pk=uploaded.data["id"])
        self.assertGreater(len(document.file.name), 100)
        self.assertEqual(document.tenant_id, "tenant-a")
        self.assertEqual(OnboardingCase.objects.get(pk=case_id).status, "processing")
        enqueue.assert_called_once_with(str(document.id), correlation_id="upload-42")
        self.assertTrue(AuditEvent.objects.filter(case_id=case_id, event_type="document.received", correlation_id="upload-42").exists())
        self.assertTrue(EventOutbox.objects.filter(aggregate_id=case_id, event_type="document.received").exists())
