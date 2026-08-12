"""One-time fetch script documenting exactly how resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra/*.json were
obtained (Tier-1 review item 1.1: reviewer asked whether the marker-7 confounder audit adjusts
for clinical covariates beyond grade -- PSA, T-stage, margins, age). Re-run this only if the
cached JSON is lost; the analysis script (pilot_marker7_confounder_audit.py) reads the cached
files, not this script, so results don't silently change if the live APIs change.

Two sources, both public, no auth:
  - GDC REST API (`api.gdc.cancer.gov/cases`): ajcc_pathologic_t (T-stage) and
    demographic.age_at_index (age), for all TCGA-PRAD cases.
  - cBioPortal REST API, study `prad_tcga_pub`, patient-level clinical data: PREOPERATIVE_PSA
    and RESIDUAL_TUMOR (surgical margin status R0/R1/R2/RX). Verified directly (per this
    project's "verify before trusting" convention) that these two fields exist and are
    populated at the PATIENT level in this study's `/clinical-data?clinicalDataType=PATIENT`
    endpoint -- they are NOT present in the sample-level clinical JSON already cached elsewhere
    in this project (resources/projects/prostate_biomarker_validation/model_workspace/pilot_confounder_audit.py's CBIOPORTAL_SAMPLE_JSON), which only
    carries molecular/genomic attributes.

Run with any Python that has `requests` (not GPU work, no CONCH needed):
    python3 resources/projects/prostate_biomarker_validation/model_workspace/fetch_tcga_prad_clinical_extra.py
"""
import json
import os

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "resources/projects/prostate_biomarker_validation/model_workspace/tcga_prad_clinical_extra")


def fetch_gdc():
    url = "https://api.gdc.cancer.gov/cases"
    payload = {
        "filters": {"op": "in", "content": {"field": "project.project_id", "value": ["TCGA-PRAD"]}},
        "fields": "submitter_id,diagnoses.ajcc_pathologic_t,demographic.age_at_index",
        "format": "JSON",
        "size": 600,
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    n = len(data["data"]["hits"])
    print(f"GDC: fetched {n} TCGA-PRAD cases")
    with open(os.path.join(OUT_DIR, "gdc_tstage_age.json"), "w") as f:
        json.dump(data, f)


def fetch_cbioportal():
    url = ("https://www.cbioportal.org/api/studies/prad_tcga_pub/clinical-data"
           "?clinicalDataType=PATIENT&projection=SUMMARY")
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    print(f"cBioPortal prad_tcga_pub: fetched {len(data)} patient clinical-data records")
    with open(os.path.join(OUT_DIR, "prad_pub_patient_clinical.json"), "w") as f:
        json.dump(data, f)


def fetch_cbioportal_sample():
    """Cache sample-level molecular/clinical attributes used by the confounder audits."""
    url = ("https://www.cbioportal.org/api/studies/prad_tcga_pub/clinical-data"
           "?clinicalDataType=SAMPLE&projection=SUMMARY")
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    print(f"cBioPortal prad_tcga_pub: fetched {len(data)} sample clinical-data records")
    with open(os.path.join(OUT_DIR, "prad_pub_sample_clinical.json"), "w") as f:
        json.dump(data, f)


def fetch_cbioportal_pancan():
    url = ("https://www.cbioportal.org/api/studies/prad_tcga_pan_can_atlas_2018/clinical-data"
           "?clinicalDataType=PATIENT&projection=SUMMARY")
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    print(f"cBioPortal prad_tcga_pan_can_atlas_2018: fetched {len(data)} patient clinical-data records")
    with open(os.path.join(OUT_DIR, "prad_pancan_clinical.json"), "w") as f:
        json.dump(data, f)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    fetch_gdc()
    fetch_cbioportal()
    fetch_cbioportal_sample()
    fetch_cbioportal_pancan()
