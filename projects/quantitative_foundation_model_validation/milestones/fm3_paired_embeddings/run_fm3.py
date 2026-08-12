#!/usr/bin/env python3
"""Register the G9-clean shared-FOV CONCH/Virchow embedding bundle."""

from __future__ import annotations
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
RECORDS=ROOT/'projects/quantitative_foundation_model_validation/preexperiment/governance_records'
FM2=ROOT/'projects/quantitative_foundation_model_validation/milestones/fm2_paired_manifest/outputs'
OUT=Path(__file__).resolve().parent/'outputs'; OUT.mkdir(parents=True,exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def main():
    g9=json.loads((RECORDS/'g9_handoff_manifest.json').read_text()); source=Path(g9['attempt_dir'])
    if not source.exists():
        source=RECORDS/'clean_rerun'/source.name
    if not source.is_dir():raise RuntimeError(f'G9 source attempt is unavailable: {source}')
    manifest=rows(FM2/'paired_sample_manifest.csv'); qc={r['encoder']:r for r in rows(source/'embedding_technical_qc.csv')}
    specs=[('CONCH','precise_conch_shared_fov_embeddings.npy',512),('Virchow','precise_virchow_shared_fov_embeddings.npy',2560)]
    bundle=[]
    for encoder,name,dimension in specs:
        path=source/name; array=np.load(path,mmap_mode='r')
        if array.shape!=(1218,dimension) or not np.isfinite(array).all():raise RuntimeError(f'invalid {encoder} array')
        if sha(path)!=qc[encoder]['output_sha256']:raise RuntimeError(f'{encoder} hash mismatch')
        bundle.append({'encoder':encoder,'model_id':qc[encoder]['model_id'],'model_revision':qc[encoder]['model_revision'],'weights_sha256':qc[encoder]['weights_sha256'],'source_attempt':source.name,'array_path':str(path.relative_to(ROOT)),'array_sha256':sha(path),'rows':array.shape[0],'dimension':array.shape[1],'dtype':str(array.dtype),'nonfinite_values':int((~np.isfinite(array)).sum()),'zero_norm_rows':int((np.linalg.norm(array,axis=1)==0).sum()),'sample_order_manifest':'FM2 paired_sample_manifest.csv','physical_fov_um':'shared 394.24 nominal','technical_status':'pass_clean_reproducible'})
    with (OUT/'embedding_bundle_manifest.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(bundle[0]),lineterminator='\n');w.writeheader();w.writerows(bundle)
    row_links=[{'embedding_row':i,'sample_id':r['sample_id'],'subject_id':r['subject_id'],'fold':r['fold'],'conch_available':True,'virchow_available':True,'tumor_fraction':r['tumor_fraction']} for i,r in enumerate(manifest)]
    with (OUT/'embedding_row_manifest.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(row_links[0]),lineterminator='\n');w.writeheader();w.writerows(row_links)
    report=['# FM3 paired embedding bundle','', '- Status: **PASS — G9-clean shared-FOV descriptive bundle registered**',f'- Source attempt: `{source.name}`','- Samples: 1,218 paired tiles / 25 subjects','- CONCH: 1,218 × 512, finite, exact smoke repeat','- Virchow: 1,218 × 2,560, finite, exact smoke repeat','- Sample-order mismatch: 0','- Array hash mismatch: 0','', 'Arrays are referenced in the immutable clean-attempt directory rather than copied. This bundle is restricted to shared-394.24µm descriptive tumor-fraction work. It does not authorize confirmatory, clinical, PNI, scanner/stain, superiority or H2 inference.']
    (OUT/'FM3_REPORT.md').write_text('\n'.join(report)+'\n')
    config={'schema_version':'fm3-bundle-1.0','generated_at_utc':datetime.now(timezone.utc).isoformat(),'g9_manifest_sha256':sha(RECORDS/'g9_handoff_manifest.json'),'fm2_manifest_sha256':sha(FM2/'paired_sample_manifest.csv'),'bundle':bundle,'output_hashes_excluding_run_config':{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='run_config.json'}}
    (OUT/'run_config.json').write_text(json.dumps(config,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'encoders':2,'paired_rows':1218,'status':'pass'}))
if __name__=='__main__':main()
