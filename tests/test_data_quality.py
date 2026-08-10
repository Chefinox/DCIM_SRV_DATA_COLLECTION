import unittest
from src.scoring.data_quality import DataQualityScorecard
from src.validation.engine import ValidationResult

class TestDataQualityScorecard(unittest.TestCase):
    def setUp(self):
        self.scorecard = DataQualityScorecard()

    def test_perfect_score(self):
        result = ValidationResult(status="accepted")
        self.scorecard.record_validation_result(result)
        
        scores = self.scorecard.calculate_scores()
        for k, v in scores.items():
            self.assertEqual(v, 1.0)

    def test_duplicate_affects_uniqueness(self):
        result = ValidationResult(status="duplicate")
        self.scorecard.record_validation_result(result)
        
        scores = self.scorecard.calculate_scores()
        self.assertEqual(scores["uniqueness"], 0.0)
        self.assertEqual(scores["completeness"], 1.0)  # Others should be 1.0
        
    def test_stale_event_affects_timeliness(self):
        result = ValidationResult(status="quarantined", reason="stale_event: too old")
        self.scorecard.record_validation_result(result)
        
        scores = self.scorecard.calculate_scores()
        self.assertEqual(scores["timeliness"], 0.0)
        self.assertEqual(scores["accuracy"], 1.0)

if __name__ == '__main__':
    unittest.main()
