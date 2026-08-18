import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "milestones"
    / "fm6_entry_audit"
    / "run_fm6_entry_audit.py"
)
SPEC = importlib.util.spec_from_file_location("run_fm6_entry_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Fm6EntryAuditTests(unittest.TestCase):
    def test_isup_derivation_distinguishes_three_plus_four(self):
        self.assertEqual(MODULE.derive_isup("Pattern 3", "Pattern 4", 7), 2)
        self.assertEqual(MODULE.derive_isup("Pattern 4", "Pattern 3", 7), 3)
        self.assertIsNone(MODULE.derive_isup(None, None, 7))

    def test_case_isup_rejects_conflicting_records(self):
        value, source = MODULE.case_isup({
            "diagnoses": [
                {"primary_gleason_grade": "Pattern 3", "secondary_gleason_grade": "Pattern 4"},
                {"primary_gleason_grade": "Pattern 4", "secondary_gleason_grade": "Pattern 3"},
            ]
        })
        self.assertIsNone(value)
        self.assertEqual(source, "conflicting_grade_records")

    def test_treatment_requires_known_radiation_and_pharmaceutical_status(self):
        status = MODULE.case_treatment({
            "diagnoses": [{
                "treatments": [
                    {"treatment_type": "Radiation Therapy, NOS", "treatment_or_therapy": "no"},
                    {"treatment_type": "Pharmaceutical Therapy, NOS", "treatment_or_therapy": "yes"},
                ]
            }]
        })
        self.assertTrue(status["both_documented"])

    def test_direct_recurrence_does_not_use_disease_response_proxy(self):
        case = {"follow_ups": [{"disease_response": "WT-With Tumor", "days_to_follow_up": 100}]}
        self.assertFalse(MODULE.case_has_any_direct_recurrence(case))

    def test_bcr_endpoint_requires_biochemical_type_and_time(self):
        event = MODULE.case_bcr_endpoint({"follow_ups": [{
            "progression_or_recurrence": "Yes",
            "progression_or_recurrence_type": "Biochemical",
            "days_to_recurrence": 365,
        }]})
        self.assertEqual(event, {"status": "event_with_time", "event": 1, "days": 365.0})
        ambiguous = MODULE.case_bcr_endpoint({"follow_ups": [{
            "progression_or_recurrence": "Yes",
            "progression_or_recurrence_type": "Distant",
            "days_to_recurrence": 365,
        }]})
        self.assertEqual(ambiguous["status"], "competing_or_ambiguous_recurrence")


if __name__ == "__main__":
    unittest.main()
