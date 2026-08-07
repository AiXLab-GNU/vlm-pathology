# Code availability and reproducibility scope

The manuscript analysis and build code is publicly maintained at:

<https://github.com/AiXLab-GNU/vlm-pathology/tree/feat/precise-pni-morphology-rereview>

## Audited analysis entry points

- `models/build_revision_p0_artifacts.py`: validates and assembles the
  publication-facing revision artifacts.
- `models/aggregate_stability_grid.py`: reconciles the frozen correlated
  encoder--scale--tile--seed stability grid.
- `models/build_tcga_cdr_pfi_evidence.py`: audits official TCGA-CDR PFI
  evidence and endpoint mappings.
- `models/build_marker7_survival_paired_analysis.py`: constructs the paired
  recurrence-endpoint survival analysis.
- `models/run_marker7_common_source_sensitivity.py`: runs the common-source
  marker 7 sensitivity analysis.
- `models/build_ar_spop_evidence_closure.py`: assembles the AR site and SPOP
  evidence closure.

The repository also contains the source scripts required by these entry
points, the frozen stability runners, validation tests, environment
specifications, manuscript builder, table generator and figure renderers.
Repository-authored software and documentation are released under the
[MIT License](LICENSE).

## Reproduction boundary

The repository does not redistribute whole-slide images, source cohort data,
cached embeddings, pretrained model weights, access-governed LEOPARD
artifacts, or patient-level derived outputs. These assets must be obtained
from their original providers under the applicable access and reuse terms.
They are not licensed by the repository's MIT License.
The tracked environment and lock files document the software dependencies.

Publication-facing aggregate tables and rendered figures are separated from
restricted or bulky analysis inputs. The code preserves frozen scores,
analysis units, endpoints and saved configurations; it is not a deployable
whole-slide diagnostic system and does not establish clinical validation.

## Versioning

The branch URL above identifies the live manuscript-development branch. A
versioned release tag and archival DOI should replace or supplement the branch
URL in the final accepted manuscript when they are minted.
