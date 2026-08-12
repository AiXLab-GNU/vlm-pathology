import csv,json,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]; OUT=ROOT/'projects/quantitative_foundation_model_validation/milestones/fm3_paired_embeddings/outputs'
class FM3Tests(unittest.TestCase):
 def test_bundle(self):
  with (OUT/'embedding_bundle_manifest.csv').open() as f:r=list(csv.DictReader(f))
  self.assertEqual([(x['encoder'],x['rows'],x['dimension']) for x in r],[('CONCH','1218','512'),('Virchow','1218','2560')])
  self.assertTrue(all(x['technical_status']=='pass_clean_reproducible' for x in r))
 def test_row_links(self):
  with (OUT/'embedding_row_manifest.csv').open() as f:r=list(csv.DictReader(f))
  self.assertEqual(len(r),1218);self.assertEqual([int(x['embedding_row']) for x in r],list(range(1218)))
 def test_arrays_exist_and_match_shape(self):
  c=json.loads((OUT/'run_config.json').read_text())
  for b in c['bundle']:
   a=np.load(ROOT/b['array_path'],mmap_mode='r');self.assertEqual(list(a.shape),[b['rows'],b['dimension']])
if __name__=='__main__':unittest.main()
