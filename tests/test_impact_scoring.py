import unittest
from src.scoring.impact import ImpactScorer

class TestImpactScoring(unittest.TestCase):
    def setUp(self):
        self.scorer = ImpactScorer()

    def test_p1_impact(self):
        # critical (5) * critical (5) = 25 (>= 15 -> P1)
        result = self.scorer.calculate("critical", "critical")
        self.assertEqual(result["impact_priority"], "P1")
        self.assertEqual(result["impact_score"], 25)

    def test_p2_impact(self):
        # medium (3) * warning (3) = 9 (>= 6 -> P2)
        result = self.scorer.calculate("medium", "warning")
        self.assertEqual(result["impact_priority"], "P2")
        self.assertEqual(result["impact_score"], 9)

    def test_p3_impact(self):
        # low (2) * info (1) = 2 (< 6 -> P3)
        result = self.scorer.calculate("low", "info")
        self.assertEqual(result["impact_priority"], "P3")
        self.assertEqual(result["impact_score"], 2)

    def test_unknown_values(self):
        # fallback to 1 * 1 = 1 -> P3
        result = self.scorer.calculate("unknown_crit", "unknown_sev")
        self.assertEqual(result["impact_priority"], "P3")
        self.assertEqual(result["impact_score"], 1)

if __name__ == '__main__':
    unittest.main()
