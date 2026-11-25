import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from celery.exceptions import Retry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from onboarding.models import AuditEvent, CaseDocument, EventOutbox, OnboardingCase
from onboarding.tasks import process_document, publish_pending_events, refresh_case_recommendation


class ComplianceTaskTests(TestCase):
    def setUp(self):
        self.case = OnboardingCase.objects.create(
            tenant_id="tenant-a",
            worker_name="Example Worker",
            email="worker@example.invalid",
            role="Portfolio Tester",
            country="US",
        )

    def create_document(self, filename="identity.txt", content=b"Example identity evidence"):
        return CaseDocument.objects.create(
            tenant_id=self.case.tenant_id,
            case=self.case,
            document_type="identity",
            file=SimpleUploadedFile(filename, content, content_type="text/plain"),
            original_name=filename,
            mime_type="text/plain",
            size_bytes=len(content),
            sha256="synthetic-digest",
        )

    def extraction_response(self, fields=None):
        response = MagicMock()
        response.json.return_value = {
            "fields": fields or {"full_name": "Example Worker"},
            "confidence": 0.91,
            "warnings": [],
            "human_review_required": False,
        }
        return response

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_processes_text_document_and_persists_extraction_audit_and_outbox(
        self, post, refresh_recommendation
    ):
        document = self.create_document()
        response = MagicMock()
        response.json.return_value = {
            "fields": {"full_name": "Example Worker"},
            "confidence": 0.97,
            "warnings": [],
            "human_review_required": False,
        }
        post.return_value = response

        result = process_document.run(str(document.id), correlation_id="trace-doc-1")

        self.assertEqual(result, {"document_id": str(document.id), "status": "processed"})
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://localhost:8002/v1/extract")
        self.assertEqual(kwargs["json"], {"document_text": "Example identity evidence", "document_type": "identity"})
        self.assertEqual(kwargs["headers"]["X-Tenant-Id"], "tenant-a")
        self.assertEqual(kwargs["headers"]["X-Correlation-Id"], "trace-doc-1")

        document.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual(document.status, "processed")
        self.assertEqual(document.confidence, 0.97)
        self.assertEqual(self.case.status, "processing")
        self.assertEqual(self.case.extraction[str(document.id)]["full_name"], "Example Worker")
        self.assertTrue(
            AuditEvent.objects.filter(
                case=self.case,
                event_type="document.processed",
                correlation_id="trace-doc-1",
            ).exists()
        )
        self.assertTrue(
            EventOutbox.objects.filter(
                aggregate_id=str(self.case.id),
                event_type="document.processed",
                payload__correlationId="trace-doc-1",
            ).exists()
        )
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-doc-1")

    @patch("onboarding.tasks.httpx.post", side_effect=httpx.ConnectError("AI service unavailable"))
    def test_document_task_retries_ai_transport_failure_without_committing_extraction(self, post):
        document = self.create_document()

        with patch.object(process_document, "retry", side_effect=Retry("scheduled")) as retry:
            with self.assertRaises(Retry):
                process_document.run(str(document.id), correlation_id="trace-retry")

        retry.assert_called_once()
        self.assertIsInstance(retry.call_args.kwargs["exc"], httpx.ConnectError)
        post.assert_called_once()
        document.refresh_from_db()
        self.assertEqual(document.status, "processing")
        self.assertEqual(document.extracted_fields, {})
        self.assertFalse(EventOutbox.objects.filter(event_type="document.processed").exists())

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_empty_document_is_routed_to_human_review_without_calling_ai(self, post, refresh_recommendation):
        document = self.create_document(content=b"  \n")

        result = process_document.run(str(document.id), correlation_id="trace-empty")

        self.assertEqual(result, {"document_id": str(document.id), "status": "review_required"})
        post.assert_not_called()
        document.refresh_from_db()
        self.assertEqual(document.status, "review_required")
        self.assertIn("human reviewer", document.warnings[0])
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-empty")

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_extracts_embedded_text_from_pdf(self, post, refresh_recommendation):
        document = self.create_document("identity.pdf", b"synthetic-pdf")
        page = MagicMock()
        page.get_text.return_value = "PDF identity text"
        fake_fitz = SimpleNamespace(open=MagicMock(return_value=[page]))
        post.return_value = self.extraction_response()

        with patch.dict(sys.modules, {"fitz": fake_fitz}):
            result = process_document.run(str(document.id), correlation_id="trace-pdf")

        self.assertEqual(result["status"], "processed")
        self.assertEqual(post.call_args.kwargs["json"]["document_text"], "PDF identity text")
        page.get_pixmap.assert_not_called()
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-pdf")

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_uses_ocr_when_pdf_has_no_embedded_text(self, post, refresh_recommendation):
        document = self.create_document("scanned.pdf", b"synthetic-pdf")
        page = MagicMock()
        page.get_text.return_value = ""
        page.get_pixmap.return_value.tobytes.return_value = b"synthetic-png"
        fake_fitz = SimpleNamespace(open=MagicMock(return_value=[page]), Matrix=MagicMock())
        fake_pil = ModuleType("PIL")
        fake_pil.Image = SimpleNamespace(open=MagicMock(return_value=object()))
        fake_ocr = SimpleNamespace(image_to_string=MagicMock(return_value="OCR identity text"))
        post.return_value = self.extraction_response()

        with patch.dict(sys.modules, {"fitz": fake_fitz, "PIL": fake_pil, "pytesseract": fake_ocr}):
            result = process_document.run(str(document.id), correlation_id="trace-ocr")

        self.assertEqual(result["status"], "processed")
        self.assertEqual(post.call_args.kwargs["json"]["document_text"], "OCR identity text")
        fake_ocr.image_to_string.assert_called_once()
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-ocr")

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_routes_pdf_to_human_review_when_ocr_finds_no_text(self, post, refresh_recommendation):
        document = self.create_document("unreadable-scan.pdf", b"synthetic-pdf")
        page = MagicMock()
        page.get_text.return_value = ""
        page.get_pixmap.return_value.tobytes.return_value = b"synthetic-png"
        fake_fitz = SimpleNamespace(open=MagicMock(return_value=[page]), Matrix=MagicMock())
        fake_pil = ModuleType("PIL")
        fake_pil.Image = SimpleNamespace(open=MagicMock(return_value=object()))
        fake_ocr = SimpleNamespace(image_to_string=MagicMock(return_value="  "))

        with patch.dict(sys.modules, {"fitz": fake_fitz, "PIL": fake_pil, "pytesseract": fake_ocr}):
            result = process_document.run(str(document.id), correlation_id="trace-empty-ocr")

        self.assertEqual(result["status"], "review_required")
        post.assert_not_called()
        document.refresh_from_db()
        self.assertEqual(document.status, "review_required")
        self.assertIn("No readable text", document.warnings[0])
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-empty-ocr")

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_uses_ocr_for_image_document(self, post, refresh_recommendation):
        document = self.create_document("identity.png", b"synthetic-image")
        fake_pil = ModuleType("PIL")
        fake_pil.Image = SimpleNamespace(open=MagicMock(return_value=object()))
        fake_ocr = SimpleNamespace(image_to_string=MagicMock(return_value="Image identity text"))
        post.return_value = self.extraction_response()

        with patch.dict(sys.modules, {"PIL": fake_pil, "pytesseract": fake_ocr}):
            result = process_document.run(str(document.id), correlation_id="trace-image")

        self.assertEqual(result["status"], "processed")
        self.assertEqual(post.call_args.kwargs["json"]["document_text"], "Image identity text")
        fake_ocr.image_to_string.assert_called_once()
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-image")

    @patch("onboarding.tasks.refresh_case_recommendation.delay")
    @patch("onboarding.tasks.httpx.post")
    def test_unreadable_pdf_is_marked_for_human_review(self, post, refresh_recommendation):
        document = self.create_document("broken.pdf", b"not-a-pdf")
        fake_fitz = SimpleNamespace(open=MagicMock(side_effect=ValueError("invalid PDF")))

        with patch.dict(sys.modules, {"fitz": fake_fitz}):
            result = process_document.run(str(document.id), correlation_id="trace-broken")

        self.assertEqual(result["status"], "review_required")
        post.assert_not_called()
        document.refresh_from_db()
        self.assertEqual(document.status, "review_required")
        self.assertIn("could not read", document.warnings[0])
        refresh_recommendation.assert_called_once_with(str(self.case.id), correlation_id="trace-broken")

    @patch("onboarding.tasks.httpx.post")
    def test_recommendation_uses_tenant_context_and_preserves_final_case_decision(self, post):
        self.case.status = "approved"
        self.case.save(update_fields=["status"])
        response = MagicMock()
        response.json.return_value = {
            "suggested_next_step": "review_documents",
            "human_decision_required": True,
            "policy_sources": ["synthetic-policy-1"],
        }
        post.return_value = response

        result = refresh_case_recommendation.run(str(self.case.id), correlation_id="trace-recommend")

        self.assertEqual(result, {"case_id": str(self.case.id), "suggested_next_step": "review_documents"})
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"]["X-Tenant-Id"], "tenant-a")
        self.assertEqual(kwargs["headers"]["X-Correlation-Id"], "trace-recommend")
        self.assertEqual(kwargs["json"]["worker_profile"]["name"], "Example Worker")
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "approved")
        self.assertEqual(self.case.ai_recommendation["policy_sources"], ["synthetic-policy-1"])
        self.assertTrue(
            AuditEvent.objects.filter(
                case=self.case,
                event_type="case.ai_recommendation_updated",
                correlation_id="trace-recommend",
            ).exists()
        )
        self.assertTrue(EventOutbox.objects.filter(event_type="case.ai_recommendation_updated").exists())

    @patch("onboarding.tasks.httpx.post", side_effect=httpx.ConnectError("AI service unavailable"))
    def test_recommendation_task_retries_ai_transport_failure(self, post):
        with patch.object(refresh_case_recommendation, "retry", side_effect=Retry("scheduled")) as retry:
            with self.assertRaises(Retry):
                refresh_case_recommendation.run(str(self.case.id), correlation_id="trace-recommend-retry")

        retry.assert_called_once()
        self.assertIsInstance(retry.call_args.kwargs["exc"], httpx.ConnectError)
        post.assert_called_once()
        self.case.refresh_from_db()
        self.assertEqual(self.case.ai_recommendation, {})
        self.assertFalse(AuditEvent.objects.filter(event_type="case.ai_recommendation_updated").exists())

    def test_publishes_only_pending_outbox_events_in_created_order(self):
        first = EventOutbox.objects.create(
            tenant_id="tenant-a", event_type="case.created", aggregate_id="case-1", payload={}
        )
        EventOutbox.objects.create(
            tenant_id="tenant-a",
            event_type="case.updated",
            aggregate_id="case-2",
            payload={},
            published_at=self.case.created_at,
        )
        second = EventOutbox.objects.create(
            tenant_id="tenant-a", event_type="case.updated", aggregate_id="case-3", payload={}
        )

        with patch("onboarding.events.dispatch_outbox") as dispatch:
            result = publish_pending_events.run()

        self.assertEqual(result, {"published": 2})
        self.assertEqual([call.args[0] for call in dispatch.call_args_list], [first.id, second.id])

    def test_outbox_task_retries_when_event_dispatch_fails(self):
        EventOutbox.objects.create(
            tenant_id="tenant-a", event_type="case.created", aggregate_id="case-retry", payload={}
        )

        with patch("onboarding.events.dispatch_outbox", side_effect=RuntimeError("Kafka unavailable")):
            with patch.object(publish_pending_events, "retry", side_effect=Retry("scheduled")) as retry:
                with self.assertRaises(Retry):
                    publish_pending_events.run()

        retry.assert_called_once()
        self.assertIsInstance(retry.call_args.kwargs["exc"], RuntimeError)
        self.assertIsNone(EventOutbox.objects.get(aggregate_id="case-retry").published_at)
