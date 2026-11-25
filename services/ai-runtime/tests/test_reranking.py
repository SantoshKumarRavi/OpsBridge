from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reranking import rerank_candidates


class FakeScorer:
    def __init__(self, scores):
        self.scores = scores
        self.pairs = None

    def predict(self, pairs):
        self.pairs = pairs
        return self.scores


class RerankingTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"title": "General policy", "content": "General onboarding guidance.", "retrievalScore": 0.03},
            {"title": "Expiry policy", "content": "Expired identity documents require review.", "retrievalScore": 0.02},
        ]

    def test_reorders_by_pairwise_model_score_and_keeps_retrieval_score(self):
        scorer = FakeScorer([0.1, 0.9])

        result = rerank_candidates("What if an ID is expired?", self.candidates, scorer)

        self.assertEqual([item["title"] for item in result], ["Expiry policy", "General policy"])
        self.assertEqual(result[0]["retrievalScore"], 0.02)
        self.assertEqual(result[0]["rerankScore"], 0.9)
        self.assertEqual(scorer.pairs[0][0], "What if an ID is expired?")
        self.assertIn("Expired identity documents", scorer.pairs[1][1])

    def test_equal_scores_preserve_original_candidate_order(self):
        result = rerank_candidates("query", self.candidates, FakeScorer([0.5, 0.5]))

        self.assertEqual([item["title"] for item in result], ["General policy", "Expiry policy"])

    def test_empty_candidate_list_does_not_call_model(self):
        scorer = FakeScorer([])

        self.assertEqual(rerank_candidates("query", [], scorer), [])
        self.assertIsNone(scorer.pairs)

    def test_invalid_score_count_is_rejected(self):
        with self.assertRaises(ValueError):
            rerank_candidates("query", self.candidates, FakeScorer([0.5]))


if __name__ == "__main__":
    unittest.main()
