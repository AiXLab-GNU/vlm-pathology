import csv
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'projects/quantitative_foundation_model_validation/milestones/fm2_paired_manifest/outputs'

def read(name):
    with (OUT/name).open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

class FM2Tests(unittest.TestCase):
    def test_manifest_is_exactly_paired(self):
        rows=read('paired_sample_manifest.csv')
        self.assertEqual(len(rows),1218); self.assertEqual(len({r['sample_id'] for r in rows}),1218)
        self.assertTrue(all(r['conch_embedding_row']==r['virchow_embedding_row'] for r in rows))
        self.assertTrue(all(r['crop_hash_match']=='True' for r in rows))
        self.assertTrue(all(r['same_boundary_for_both_models']=='True' for r in rows))
    def test_unknown_metadata_is_not_invented(self):
        rows=read('paired_sample_manifest.csv')
        self.assertTrue(all(r['scanner_metadata_status']=='not_available' for r in rows))
        self.assertTrue(all(r['h2_endpoint_linkage_status']=='not_available_in_PRECISE' for r in rows))
    def test_g9_pass_is_source(self):
        config=json.loads((OUT/'run_config.json').read_text())
        self.assertIn('attempt-20260812T135439Z',config['source_attempt'])

if __name__=='__main__': unittest.main()
