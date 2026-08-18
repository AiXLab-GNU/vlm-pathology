from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = (
    ROOT
    / "projects"
    / "quantitative_foundation_model_validation"
    / "paper"
    / "evidence-qualified-alignment-prostate-cancer"
)


class AlignmentManuscriptContractTests(unittest.TestCase):
    def test_main_and_supplement_sources_exist(self) -> None:
        required = [
            "main.tex",
            "supplement.tex",
            "sections/abstract.tex",
            "sections/introduction.tex",
            "sections/results.tex",
            "sections/discussion.tex",
            "sections/conclusion.tex",
            "sections/methods.tex",
            "sections/supplementary_information.tex",
        ]
        for relative in required:
            self.assertTrue((WORKSPACE / relative).is_file(), relative)

    def test_cross_project_sources_are_hash_locked(self) -> None:
        manifest = WORKSPACE / "provenance" / "source_evidence_manifest.csv"
        with manifest.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 10)
        for row in rows:
            source = ROOT / row["path"]
            self.assertTrue(source.is_file(), row["source_id"])
            self.assertEqual(source.stat().st_size, int(row["size_bytes"]), row["source_id"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), row["sha256"], row["source_id"])

    def test_claim_matrix_scopes_functional_use_and_defers_residual_markers(self) -> None:
        path = WORKSPACE / "provenance" / "claim_evidence_matrix.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        statuses = {row["functional_use_status"] for row in rows}
        self.assertEqual(statuses, {"not_tested", "internal_exploratory_only", "not_claimed"})
        by_id = {row["claim_id"]: row for row in rows}
        self.assertEqual(by_id["A08"]["functional_use_status"], "internal_exploratory_only")
        self.assertEqual(by_id["A10"]["functional_use_status"], "not_claimed")

    def test_main_states_recoverability_functional_use_boundary(self) -> None:
        text = "\n".join(
            (WORKSPACE / relative).read_text(encoding="utf-8")
            for relative in [
                "sections/abstract.tex",
                "sections/introduction.tex",
                "sections/results.tex",
                "sections/discussion.tex",
                "sections/methods.tex",
            ]
        )
        self.assertIn("recoverability", text)
        self.assertIn("functional use", text)
        self.assertIn("internal functional-sensitivity", text)
        self.assertIn("not a comprehensive clinical-increment", " ".join(text.split()))
        self.assertIn("independent-domain", text.lower())
        self.assertIn("residual", text)
        self.assertNotIn("clinically validated biomarker", text.lower())
        self.assertNotIn("universally superior", text.lower())
        self.assertIn("calibrated reliance", text.lower())
        self.assertIn("trust, reliance, diagnostic performance, and clinical utility were not study", text.lower())

    def test_trust_rationale_is_cited_and_not_promoted_to_an_observed_outcome(self) -> None:
        abstract = (WORKSPACE / "sections" / "abstract.tex").read_text(encoding="utf-8")
        normalized_abstract = " ".join(abstract.split())
        introduction = (WORKSPACE / "sections" / "introduction.tex").read_text(encoding="utf-8")
        bibliography = (WORKSPACE / "sections" / "bibliography.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "sections" / "supplementary_information.tex").read_text(encoding="utf-8")

        self.assertIn("comparative map provides an actionable audit vocabulary", normalized_abstract)
        self.assertIn("six non-interchangeable", normalized_abstract)
        self.assertIn("grade, tumor phenotype/content", normalized_abstract)
        self.assertIn("PTEN-related information was recoverable", normalized_abstract)
        self.assertIn("AR activity showed positive pooled alignment", normalized_abstract)
        self.assertIn("most complete evidence chain", normalized_abstract)
        self.assertIn("not the sole organizing target", normalized_abstract)
        self.assertIn("SPOP was unsupported", normalized_abstract)
        self.assertIn("recurrence changed", normalized_abstract)
        self.assertIn("anchor clinician review of agreement and disagreement", normalized_abstract)
        self.assertIn("explanations should be withheld", normalized_abstract)
        self.assertIn("prioritize external or functional validation", normalized_abstract)
        detexed = subprocess.run(
            ["detex"], input=abstract, text=True, capture_output=True, check=True
        ).stdout
        self.assertLessEqual(len(detexed.split()), 200)
        self.assertIn("Position of this study", introduction)
        self.assertIn("Contributions.", introduction)
        self.assertIn("This paper makes four contributions", introduction)
        self.assertIn("contestable shared coordinates", introduction)
        self.assertIn("Why the six prostate-cancer axes are not interchangeable", introduction)
        normalized_introduction = " ".join(introduction.split())
        self.assertIn("Grade/ISUP measures architectural differentiation", normalized_introduction)
        self.assertIn("Recurrence is a patient outcome", normalized_introduction)
        self.assertIn("confirm that the tissue supports the named feature", introduction)
        self.assertIn("agree or disagree with a clinically", normalized_introduction)
        for citation in [
            "tonekaboni2019",
            "prinster2024",
            "kim2018",
            "koh2020",
            "sauter2022",
            "lou2026",
            "han2026",
        ]:
            self.assertIn(citation, introduction)
            self.assertIn(f"\\bibitem{{{citation}}}", bibliography)
        self.assertIn("No clinician trust, reliance", supplement)
        self.assertIn("does not establish absence of clinical increment", supplement)

        conclusion = (WORKSPACE / "sections" / "conclusion.tex").read_text(encoding="utf-8")
        normalized_conclusion = " ".join(conclusion.split())
        self.assertIn("comparative hierarchy", normalized_conclusion)
        self.assertIn("contestable coordinates", normalized_conclusion)
        self.assertIn("pathologist agreement, calibrated reliance", normalized_conclusion)
        self.assertIn("experiments support four connected contributions", normalized_conclusion)
        self.assertIn("The central claim is supported within that boundary", normalized_conclusion)
        for operational_claim in [
            "anchor clinician review of agreement and disagreement",
            "explanations should be withheld",
            "prioritize external or functional validation",
        ]:
            self.assertIn(operational_claim, normalized_abstract)
            self.assertIn(operational_claim, normalized_introduction)
            self.assertIn(operational_claim, normalized_conclusion)
        main = (WORKSPACE / "main.tex").read_text(encoding="utf-8")
        self.assertIn("\\section{Conclusion}", main)
        self.assertLess(main.index("\\section{Discussion}"), main.index("\\section{Conclusion}"))
        self.assertLess(main.index("\\section{Conclusion}"), main.index("\\section{Methods}"))

    def test_cross_disciplinary_orientation_and_result_scaffold_are_retained(self) -> None:
        introduction = (WORKSPACE / "sections" / "introduction.tex").read_text(encoding="utf-8")
        results = (WORKSPACE / "sections" / "results.tex").read_text(encoding="utf-8")
        methods = (WORKSPACE / "sections" / "methods.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "sections" / "supplementary_information.tex").read_text(encoding="utf-8")

        self.assertIn("Clinical orientation and reference availability", introduction)
        self.assertNotIn("\\begin{table}", introduction)
        detexed_introduction = subprocess.run(
            ["detex"], input=introduction, text=True, capture_output=True, check=True
        ).stdout
        self.assertLessEqual(len(detexed_introduction.split()), 1200)
        self.assertIn("Clinical-target, paired-reference, and metric primer", supplement)
        self.assertIn("Study resources, analysis frames, and roles in signal qualification", supplement)
        for clinical_target in [
            "Grade/ISUP",
            "Tumor phenotype",
            "PTEN loss",
            "SPOP mutation",
            "AR activity",
            "Recurrence",
        ]:
            self.assertIn(clinical_target, supplement)
        for reader_boundary in [
            "AUROC does not choose a clinical sensitivity/specificity threshold",
            "it is not a calibrated survival probability",
            "resamples patients rather than slides",
            "not proof that the biological relationship is absent",
        ]:
            self.assertIn(reader_boundary, " ".join(methods.split()))
        self.assertIn("Supplementary Section S1 retains the detailed target, paired-reference", " ".join(results.split()))
        for heading in [
            "Alignment question.",
            "Analysis frame.",
            "Evidence test.",
            "Interpretive boundary.",
            "Qualification rule.",
        ]:
            self.assertGreaterEqual(results.count(heading), 4, heading)
        self.assertIn("How to read the qualification map", results)
        for functional_status in [
            "BL, blocked because same-cohort independent phenotype truth was unavailable",
            "NR, feasible but not run for PTEN and AR",
            "NQ, not qualified because SPOP recoverability was unsupported",
            "NA, not applicable because recurrence is the predicted outcome",
        ]:
            self.assertIn(functional_status, " ".join(results.split()))
        builder = (WORKSPACE / "build_alignment_manuscript.py").read_text(encoding="utf-8")
        for split_target in ["Grade/ISUP", "Tumor phenotype/content", "AR activity"]:
            self.assertIn(split_target, builder)
        for status_code in ['("context_sensitive", "IE")', '("not_tested", "BL")',
                            '("not_tested", "NR")', '("unsupported", "NQ")',
                            '("not_applicable", "NA")']:
            self.assertIn(status_code, builder)
        normalized_methods = " ".join(methods.split()).casefold()
        for statistical_term in [
            "ridge regression",
            "Mann--Whitney",
            "Benjamini--Hochberg",
            "permutation test",
            "patient-bootstrap",
            "Cox model",
            "integrated Brier score",
        ]:
            self.assertIn(statistical_term.casefold(), normalized_methods)
        for statistical_explanation in [
            "target-predictive direction rather than a localized gland or cell type",
            "threshold-free ranking measure rather than classification accuracy",
            "proportion of held-out variation explained",
            "reference minus augmented",
            "not proof that the biological relationship is absent",
        ]:
            self.assertIn(statistical_explanation.casefold(), normalized_methods)

    def test_every_core_section_uses_a_six_axis_portfolio_first_narrative(self) -> None:
        sections = {
            name: (WORKSPACE / "sections" / f"{name}.tex").read_text(encoding="utf-8")
            for name in ["abstract", "introduction", "results", "discussion", "conclusion", "methods"]
        }
        normalized_sections = {name: " ".join(source.split()) for name, source in sections.items()}
        for name, source in sections.items():
            normalized = " ".join(source.split()).casefold()
            for target in ["grade/isup", "phenotype/content", "pten", "ar activity", "spop", "recurrence"]:
                self.assertIn(target, normalized, f"{name}:{target}")

        self.assertIn("Among the six axes", normalized_sections["abstract"])
        self.assertIn("Its primary task is comparative", normalized_sections["introduction"])
        self.assertIn("The primary result is their comparative evidence hierarchy", normalized_sections["results"])
        self.assertIn("The central result is not that one prostate-cancer target", normalized_sections["discussion"])
        self.assertIn("This comparative hierarchy", normalized_sections["conclusion"])
        self.assertIn("The primary design compared", normalized_sections["methods"])

        results = sections["results"]
        for prior_section in ["Molecular coordinates", "Outcome alignment", "Representation audits"]:
            self.assertLess(results.index(prior_section), results.index("ISUP provides the most developed"))
        methods = sections["methods"]
        self.assertLess(
            methods.index("Conditional, setting, and outcome qualification"),
            methods.index("Secondary ISUP functional-sensitivity extension"),
        )

    def test_reference_availability_is_not_misread_as_non_alignment(self) -> None:
        introduction = (WORKSPACE / "sections" / "introduction.tex").read_text(encoding="utf-8")
        results = (WORKSPACE / "sections" / "results.tex").read_text(encoding="utf-8")
        discussion = (WORKSPACE / "sections" / "discussion.tex").read_text(encoding="utf-8")
        conclusion = (WORKSPACE / "sections" / "conclusion.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "sections" / "supplementary_information.tex").read_text(
            encoding="utf-8"
        )

        normalized = {name: " ".join(source.split()) for name, source in {
            "introduction": introduction,
            "results": results,
            "discussion": discussion,
            "conclusion": conclusion,
        }.items()}
        self.assertIn("slides were model inputs, not the only study data", normalized["introduction"])
        self.assertNotIn("\\begin{table}", introduction)
        self.assertIn("Paired reference and availability", supplement)
        self.assertIn(
            "Missing reference data were treated as not evaluable, not as evidence of non-alignment",
            normalized["introduction"],
        )
        self.assertIn("Every numerical alignment result used an available target-specific reference", normalized["results"])
        self.assertIn("not evaluated or blocked denotes a missing prerequisite", normalized["results"])
        self.assertIn("unsupported denotes an available comparison", normalized["results"])
        self.assertIn("did not ask a slide-only model to agree with six unobserved quantities", normalized["discussion"])
        self.assertIn("reflects both biological accessibility", normalized["discussion"])
        self.assertIn("does not treat unavailable labels as negative results", normalized["conclusion"])

    def test_declarations_preserve_source_statements_but_publish_qfm_code_lineage(self) -> None:
        source = ROOT / "projects" / "prostate_biomarker_validation" / "paper" / "sections" / "declarations.tex"
        inherited = WORKSPACE / "sections" / "declarations.tex"
        source_text = source.read_text(encoding="utf-8")
        inherited_text = inherited.read_text(encoding="utf-8")
        for unchanged_statement in [
            "NADT-Prostate is available from The Cancer Imaging Archive",
            "NRF-2023R1A2C1006639",
            "This work was a secondary analysis of deidentified data",
        ]:
            self.assertIn(unchanged_statement, source_text)
            self.assertIn(unchanged_statement, inherited_text)
        self.assertIn("projects/prostate_biomarker_validation/code/legacy/", inherited_text)
        self.assertIn("projects/quantitative_foundation_model_validation/paper/", inherited_text)
        self.assertIn("build_alignment_manuscript.py", inherited_text)
        self.assertIn("submission-specific", inherited_text)
        self.assertNotIn("feat/precise-pni-morphology-rereview", inherited_text)
        self.assertNotIn("resources/projects/prostate_biomarker_validation/model_workspace", inherited_text)

    def test_expanded_results_expose_all_promoted_evidence_axes(self) -> None:
        results = (WORKSPACE / "sections" / "results.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "sections" / "supplementary_information.tex").read_text(encoding="utf-8")
        required_main_assets = [
            "figures/fig1_alignment_map.pdf",
            "figures/fig2_known_target_alignment.pdf",
            "figures/fig3_conditional_alignment.pdf",
            "figures/fig4_representation_sensitivity.pdf",
            "figures/fig5_setting_contrasts.pdf",
            "figures/fig6_outcome_contrasts.pdf",
            "figures/fig7_human_ai_linkage_map.pdf",
            "generated/table1_alignment_summary.tex",
            "generated/table2_primary_evidence.tex",
        ]
        for relative in required_main_assets:
            self.assertTrue((WORKSPACE / relative).is_file(), relative)
        alignment_table = (WORKSPACE / "generated" / "table1_alignment_summary.tex").read_text(encoding="utf-8")
        self.assertIn("p{0.38\\textwidth}", alignment_table)
        self.assertIn("p{0.23\\textwidth}", alignment_table)
        self.assertGreaterEqual(alignment_table.count("\\raggedright\\arraybackslash"), 4)
        self.assertIn("Context-sensitive", alignment_table)
        self.assertIn("Feasible follow-up; not run", alignment_table)
        self.assertIn("Grade/ISUP & Transportable", alignment_table)
        self.assertIn("Tumor phenotype/content & Transportable", alignment_table)
        self.assertNotIn("Grade and phenotype", alignment_table)
        for target in ["Grade/ISUP", "Tumor phenotype/content", "PTEN", "AR activity", "SPOP", "Recurrence"]:
            self.assertIn(target, alignment_table)
        self.assertNotIn("context\\_", alignment_table)
        self.assertNotIn("not\\_", alignment_table)
        for reference in [
            "fig:conditional-alignment",
            "fig:human-ai-linkage",
            "fig:outcome-contrasts",
            "fig:stability",
            "fig:setting-contrasts",
            "tab:alignment-summary",
        ]:
            self.assertIn(reference, results)
        for reference in ["fig:supp-full-grid", "tab:supp-six-axis-evidence-stage"]:
            self.assertIn(reference, supplement)
        self.assertIn("generated/stable2_primary_estimates.tex", supplement)
        for main_only_reference in ["tab:primary-evidence", "tab:six-axis-evidence-stage"]:
            self.assertNotIn(main_only_reference, results)
        normalized_results = " ".join(results.split())
        self.assertIn("generated/table1_alignment_summary.tex", results)
        self.assertLess(results.index("generated/table1_alignment_summary.tex"), results.index("\\subsection"))
        self.assertIn("This does not mean that only ISUP describes prostate cancer", normalized_results)
        self.assertIn("SPOP did not yield a qualified representation feature", normalized_results)
        self.assertIn("PTEN and AR are feasible follow-up tests that were not run", normalized_results)
        discussion = (WORKSPACE / "sections" / "discussion.tex").read_text(encoding="utf-8")
        normalized_discussion = " ".join(discussion.split())
        self.assertIn("six clinically interpretable axes", normalized_discussion)
        self.assertIn("PTEN-related information was recoverable", normalized_discussion)
        self.assertIn("Absence of a functional-use result is therefore not one common negative result", normalized_discussion)
        self.assertIn("does not make ISUP the sole organizing target", normalized_discussion)
        self.assertLess(results.index("Molecular coordinates"), results.index("ISUP provides the most developed"))
        self.assertLess(results.index("Outcome alignment"), results.index("ISUP provides the most developed"))
        self.assertLess(results.index("Representation audits"), results.index("ISUP provides the most developed"))
        for generated_input in [
            "stable_site_audits.tex",
            "stable_contrast_summary.tex",
            "stable_outcome_reconstructed.tex",
            "stable_outcome_official_pfi.tex",
            "stable_missingness_summary.tex",
        ]:
            self.assertIn(generated_input, supplement)

        with (ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig9_stability_contrasts.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 390)
        with (ROOT / "projects/prostate_biomarker_validation/paper/figure_data/fig5_marker7_transfer.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 22)

    def test_fm6_clean_rerun_and_six_axis_boundaries_are_explicit(self) -> None:
        results = (WORKSPACE / "sections" / "results.tex").read_text(encoding="utf-8")
        methods = (WORKSPACE / "sections" / "methods.tex").read_text(encoding="utf-8")
        discussion = (WORKSPACE / "sections" / "discussion.tex").read_text(encoding="utf-8")
        conclusion = (WORKSPACE / "sections" / "conclusion.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "sections" / "supplementary_information.tex").read_text(
            encoding="utf-8"
        )
        normalized = {
            name: " ".join(source.split())
            for name, source in {
                "results": results,
                "methods": methods,
                "discussion": discussion,
                "conclusion": conclusion,
                "supplement": supplement,
            }.items()
        }

        self.assertIn("not exact external tumor-content agreement", normalized["results"])
        self.assertIn("SPOP genomic reference was available and was used", normalized["results"])
        self.assertIn("8 of 12 for SPOP and 1 of 12 for recurrence", normalized["results"])
        self.assertIn("All 20 protocol-defined nonvolatile output SHA-256 hashes matched", normalized["results"])
        self.assertIn("not an independent-cohort replication", normalized["results"])
        self.assertIn("Before execution, the SHA-256 hashes of 20", normalized["methods"])
        self.assertIn("R, recoverability", normalized["methods"])
        self.assertIn("A, internal association", normalized["methods"])
        self.assertIn("U, functional sensitivity", normalized["methods"])
        self.assertIn("T, equivalent external transport", normalized["methods"])
        self.assertIn("All 20 regenerated hashes matched exactly", normalized["supplement"])
        self.assertIn("cannot upgrade the claim to external functional replication", normalized["discussion"])
        self.assertIn("20/20 nonvolatile hash agreement", normalized["conclusion"])
        self.assertIn("does not itself demonstrate a new residual marker", normalized["conclusion"])
        self.assertIn("after jointly accounting for known clinical--pathology targets and technical confounders", normalized["conclusion"])
        self.assertIn("recurs across models and independent cohorts", normalized["conclusion"])
        self.assertIn("were not shown to completely explain AI representations or decisions", normalized["conclusion"])

        run_config_path = (
            ROOT
            / "projects"
            / "quantitative_foundation_model_validation"
            / "milestones"
            / "fm6_internal_development_pilot"
            / "outputs"
            / "fm6_tcga_internal_pilot_analysis_run_config.json"
        )
        run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
        self.assertEqual(len(run_config["output_hashes"]), 20)
        for relative, expected_hash in run_config["output_hashes"].items():
            output = run_config_path.parent / relative
            self.assertTrue(output.is_file(), relative)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), expected_hash, relative)

    def test_built_main_has_a_readable_uncapped_draft(self) -> None:
        main_pdf = WORKSPACE / "main.pdf"
        self.assertTrue(main_pdf.is_file())
        completed = subprocess.run(
            ["mutool", "info", str(main_pdf)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        match = re.search(r"^Pages:\s+(\d+)$", completed.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(match, completed.stdout)
        self.assertGreaterEqual(int(match.group(1)), 1)

    def test_all_figures_and_tables_are_explained_and_called_out(self) -> None:
        introduction = (WORKSPACE / "sections" / "introduction.tex").read_text(encoding="utf-8")
        results = (WORKSPACE / "sections" / "results.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "sections" / "supplementary_information.tex").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("the orientation table below", introduction)
        self.assertIn("tab:supp-clinical-reference-primer", supplement)
        self.assertIn("tab:supp-resource-orientation", supplement)
        self.assertIn("Cell codes are S, supported", results)
        self.assertIn("Positive values indicate improvement after adding the image-derived score", results)

        supplementary_table_labels = [
            "tab:supp-clinical-reference-primer",
            "tab:supp-resource-orientation",
            "tab:supp-target-registry",
            "tab:supp-six-axis-evidence-stage",
            "tab:supp-primary-estimates",
            "tab:supp-conditional-increments",
            "tab:supp-site-audits",
            "tab:supp-stability",
            "tab:supp-contrast-summary",
            "tab:supp-endpoints",
            "tab:supp-outcome-reconstructed",
            "tab:supp-outcome-official-pfi",
            "tab:supp-missingness-summary",
            "tab:supp-claim-matrix",
        ]
        for label in supplementary_table_labels:
            self.assertIn(f"\\ref{{{label}}}", supplement, label)

        supplementary_figure_labels = ["fig:supp-full-grid"]
        for label in supplementary_figure_labels:
            self.assertIn(f"\\ref{{{label}}}", supplement, label)
            self.assertIn(f"\\label{{{label}}}", supplement, label)

        generated_text = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted((WORKSPACE / "generated").glob("*.tex"))
        )
        self.assertNotIn("marker7", generated_text)
        self.assertNotIn("FULL\\_", generated_text)
        self.assertNotIn("M5\\_", generated_text)
        self.assertIn("locked BCR head", generated_text)
        self.assertIn("Delta is the image-augmented model minus the grade reference", generated_text)
        self.assertIn("These are sensitivity summaries, not independent validations", generated_text)
        self.assertIn("endpoint IDs are not interchangeable outcomes", generated_text)
        self.assertIn("Counts are source-table rows, not patients or independent tests", generated_text)
        self.assertIn("recoverability alone does not establish head use", generated_text)
        self.assertIn("Add image to clinical + site (M5 vs M4)", generated_text)
        self.assertIn("Undefined / 2,000", generated_text)
        self.assertIn("0/2,000", generated_text)

    def test_numeric_mapping_and_source_verification_pass(self) -> None:
        completed = subprocess.run(
            [
                str(ROOT / ".venv" / "bin" / "python"),
                str(WORKSPACE / "build_alignment_manuscript.py"),
                "--verify-only",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('"status": "PASS"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
