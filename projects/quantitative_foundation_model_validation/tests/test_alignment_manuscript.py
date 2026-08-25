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
            "cover_letter.tex",
            "sections/abstract.tex",
            "sections/introduction.tex",
            "sections/results.tex",
            "sections/discussion.tex",
            "sections/conclusion.tex",
            "sections/methods.tex",
            "sections/availability.tex",
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
        self.assertEqual(statuses, {
            "not_tested",
            "internal_exploratory_only",
            "external_encoder_specific_whole_tissue",
            "not_claimed",
        })
        by_id = {row["claim_id"]: row for row in rows}
        self.assertEqual(by_id["A08"]["functional_use_status"], "internal_exploratory_only")
        self.assertEqual(by_id["A10"]["functional_use_status"], "not_claimed")
        self.assertEqual(
            by_id["A11"]["functional_use_status"],
            "external_encoder_specific_whole_tissue",
        )

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
        self.assertIn("internal functional sensitivity", text)
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
        self.assertIn(
            "clinicians need to know which human-interpretable",
            normalized_abstract.casefold(),
        )
        self.assertIn("whether those axes survive cohort and technical variation", normalized_abstract)
        self.assertIn("whether downstream decisions use them", normalized_abstract)
        self.assertIn("six non-interchangeable", normalized_abstract)
        self.assertIn("grade/isup, tumor phenotype/content", normalized_abstract.casefold())
        self.assertIn("PTEN and AR were conditional", normalized_abstract)
        self.assertIn("ISUP alone underwent locked-head functional tests", normalized_abstract)
        self.assertIn("SPOP was unsupported", normalized_abstract)
        self.assertIn("recurrence changed", normalized_abstract)
        self.assertIn(
            "only Virchow met the prespecified external whole-tissue functional-transport gate",
            normalized_abstract,
        )
        self.assertIn("anchor clinician review of agreement and disagreement", normalized_abstract)
        self.assertIn("explanations should be withheld", normalized_abstract)
        self.assertIn("prioritize external or functional validation", normalized_abstract)
        self.assertIn("clinician-understandable reliability audits", normalized_abstract)
        self.assertIn("bounds future residual-signal discovery", normalized_abstract)
        self.assertIn("does not establish clinical benefit", normalized_abstract)
        self.assertIn("or new biomarkers", normalized_abstract)
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
        self.assertIn("This is the motivating problem for prostate-cancer AI", normalized_introduction)
        self.assertIn("whether each axis remains recoverable across cohorts", normalized_introduction)
        self.assertIn("whether a downstream decision actually uses it", normalized_introduction)
        self.assertIn("defines the prerequisite for residual discovery", normalized_introduction)
        self.assertIn("candidate biomarkers rather than artifacts", normalized_introduction)
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
        self.assertIn("do not demonstrate pathologist agreement", normalized_conclusion)
        self.assertIn("disciplined starting point for potential new-biomarker discovery", normalized_conclusion)
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
        statistical_context = " ".join((methods + "\n" + supplement).split())
        for reader_boundary in [
            "does not choose a clinical sensitivity/specificity threshold",
            "not a calibrated survival probability",
            "resamples patients rather than slides",
            "not proof that the biological relationship is absent",
        ]:
            self.assertIn(reader_boundary, statistical_context)
        self.assertIn("Supplementary Section S1 retains the detailed target, paired-reference", " ".join(results.split()))
        detexed_results = subprocess.run(
            ["detex"], input=results, text=True, capture_output=True, check=True
        ).stdout
        self.assertLessEqual(len(detexed_results.split()), 2400)
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
        for status_code in ['("context_sensitive", "EF")', '("not_tested", "BL")',
                            '("not_tested", "NR")', '("unsupported", "NQ")',
                            '("not_applicable", "NA")']:
            self.assertIn(status_code, builder)
        normalized_methods = statistical_context.casefold()
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
            "auroc is threshold-free",
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

        self.assertIn("among the six axes", normalized_sections["abstract"].casefold())
        self.assertIn("Its primary task is comparative", normalized_sections["introduction"])
        self.assertIn("The primary result is their comparative evidence hierarchy", normalized_sections["results"])
        self.assertIn("The central result is not that one prostate-cancer target", normalized_sections["discussion"])
        self.assertIn("The comparative hierarchy", normalized_sections["conclusion"])
        self.assertIn("The study was motivated by the need", normalized_sections["conclusion"])
        self.assertIn("disciplined starting point for potential new-biomarker discovery", normalized_sections["conclusion"])
        self.assertIn("The primary design compared", normalized_sections["methods"])

        results = sections["results"]
        for prior_section in ["Molecular coordinates", "Outcome alignment", "Representation audits"]:
            self.assertLess(
                results.index(prior_section),
                results.index("ISUP shows encoder-specific external whole-tissue functional transport"),
            )
        methods = sections["methods"]
        self.assertLess(
            methods.index("Conditional, setting, and outcome qualification"),
            methods.index("Secondary ISUP functional-sensitivity extension"),
        )

    def test_each_result_states_its_argumentative_role_and_claim_boundary(self) -> None:
        results = " ".join(
            (WORKSPACE / "sections" / "results.tex").read_text(encoding="utf-8").split()
        )
        discussion = " ".join(
            (WORKSPACE / "sections" / "discussion.tex").read_text(encoding="utf-8").split()
        )
        conclusion = " ".join(
            (WORKSPACE / "sections" / "conclusion.tex").read_text(encoding="utf-8").split()
        )

        for interpretation_contract in [
            "candidate clinician-interpretable coordinates for comparing model behavior",
            "separating information recovery from stable explanatory value",
            "score--endpoint--reference combination",
            "less compatible with a single chosen configuration artifact",
            "only direct bridge from representation availability to a downstream judgment",
            "selective rather than universal interpretability",
        ]:
            self.assertIn(interpretation_contract, results)

        self.assertIn("functional-erasure experiments were feasible but not run", results)
        self.assertIn("positive-means-degradation convention", results)
        self.assertIn("rather than any single performance value", discussion)
        self.assertIn("Each result therefore has a different argumentative role", discussion)
        self.assertIn("The evidence chain supporting that conclusion is deliberately asymmetric", conclusion)

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
        self.assertIn("Unavailable labels are not negative results", normalized["conclusion"])

    def test_declarations_preserve_source_statements_but_publish_qfm_code_lineage(self) -> None:
        source = ROOT / "projects" / "prostate_biomarker_validation" / "paper" / "sections" / "declarations.tex"
        availability = WORKSPACE / "sections" / "availability.tex"
        declarations = WORKSPACE / "sections" / "declarations.tex"
        methods = WORKSPACE / "sections" / "methods.tex"
        source_text = source.read_text(encoding="utf-8")
        inherited_text = "\n".join(
            path.read_text(encoding="utf-8") for path in [availability, declarations, methods]
        )
        for unchanged_statement in [
            "NADT-Prostate is available from The Cancer Imaging Archive",
            "NRF-2023R1A2C1006639",
            "This work was a secondary analysis of deidentified data",
        ]:
            self.assertIn(unchanged_statement, source_text)
            self.assertIn(unchanged_statement, inherited_text)
        self.assertIn("source-analysis snapshots", inherited_text)
        self.assertIn("AiXLab-GNU/evidence-qualified-alignment-prostate-cancer", inherited_text)
        self.assertIn("v1.0.6-submission", inherited_text)
        self.assertIn("build_publication_artifacts.py", inherited_text)
        self.assertIn("REPRODUCIBILITY.md", inherited_text)
        self.assertIn("editable manuscript source", inherited_text)
        self.assertIn("are not redistributed", inherited_text)
        self.assertNotIn("have not yet been assigned", inherited_text)
        self.assertNotIn("feat/precise-pni-morphology-rereview", inherited_text)
        self.assertNotIn("resources/projects/prostate_biomarker_validation/model_workspace", inherited_text)

    def test_scientific_reports_submission_structure_is_explicit(self) -> None:
        main = (WORKSPACE / "main.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "supplement.tex").read_text(encoding="utf-8")
        methods = (WORKSPACE / "sections" / "methods.tex").read_text(encoding="utf-8")
        availability = (WORKSPACE / "sections" / "availability.tex").read_text(encoding="utf-8")
        declarations = (WORKSPACE / "sections" / "declarations.tex").read_text(encoding="utf-8")

        self.assertLess(main.index("sections/availability"), main.index("sections/bibliography"))
        self.assertLess(main.index("sections/declarations"), main.index("sections/bibliography"))
        self.assertIn("\\section*{Data Availability}", availability)
        self.assertIn("\\section*{Code Availability}", availability)
        self.assertIn("\\subsection{Ethics approval and consent to participate}", methods)
        self.assertIn("No additional ethical approval or participant consent was", methods)
        self.assertIn("contains no identifiable participant information", methods)
        self.assertIn("OpenAI Codex assisted with code editing", methods)
        self.assertIn("figure-code preparation", methods)
        self.assertIn("take full responsibility", methods)
        self.assertIn("for the final manuscript", methods)
        self.assertNotIn("Product/model version", methods)
        self.assertIn("\\section*{Author Contributions}", declarations)
        for contribution in [
            "J.H.K. had overall responsibility for the manuscript",
            "D.H.S. contributed to the study concept",
            "assessed the medical validity of the study",
            "H.C. reviewed the manuscript and curated the data",
            "I.L. assessed the overall scientific",
        ]:
            self.assertIn(contribution, declarations)
        self.assertIn("\\section*{Funding}", declarations)
        self.assertIn(
            "NRF-2023R1A2C1006639). This work was also supported by",
            declarations,
        )
        self.assertIn(
            "Research Sabbatical Grant for\nResearch Professors from Gyeongsang National "
            "University in 2026 (GNU-SGRP-2026).",
            declarations,
        )
        self.assertIn("\\section*{Additional Information}", declarations)
        self.assertIn("\\subsection*{Competing Interests}", declarations)
        self.assertIn("The authors declare no competing interests.", declarations)
        for draft_source in [main, supplement, methods, availability, declarations]:
            self.assertNotIn("Draft status", draft_source)
            self.assertNotIn("Draft:", draft_source)
        self.assertNotIn("must confirm", methods)
        self.assertIn("\\renewcommand{\\figurename}{Supplementary Figure}", supplement)
        self.assertIn("\\renewcommand{\\tablename}{Supplementary Table}", supplement)

        for author in ["Jin Hyun Kim", "Dae Hyun Song", "Hyonyoung Choi", "Insup Lee"]:
            self.assertIn(author, main)
            self.assertIn(author, supplement)
        for affiliation in [
            "Gyeongsang National University, Jinju, Republic of Korea",
            "Department of Pathology, Gyeongsang National University School of Medicine",
            "PRECISE Center and Department of Computer and Information Science",
        ]:
            self.assertIn(affiliation, main)
            self.assertIn(affiliation, supplement)

    def test_motivation_focused_title_is_synchronized(self) -> None:
        main = (WORKSPACE / "main.tex").read_text(encoding="utf-8")
        supplement = (WORKSPACE / "supplement.tex").read_text(encoding="utf-8")
        expected_title = (
            "From Clinical Signal Recovery to Evidence-Qualified Interpretation of Prostate Cancer "
            "Pathology Foundation Models"
        )
        sources = [
            WORKSPACE / "main.tex",
            WORKSPACE / "supplement.tex",
            WORKSPACE / "cover_letter.tex",
            WORKSPACE / "README.md",
        ]
        for source in sources:
            normalized = " ".join(source.read_text(encoding="utf-8").split())
            self.assertIn(expected_title, normalized, source.name)
            self.assertNotIn("Morphologic, Molecular, and Outcome Axes", normalized, source.name)
        self.assertIn("\\textsuperscript{1,*}", main)
        self.assertIn("Correspondence: Jin Hyun Kim", main)
        self.assertIn("jin.kim@gnu.ac.kr", main)
        self.assertIn("jin.kim@gnu.ac.kr", supplement)
        for title_page in [main, supplement]:
            self.assertIn("0000-0002-2308-1638", title_page)
            self.assertIn("https://orcid.org/0000-0002-2308-1638", title_page)
        self.assertNotIn("Author details:", main)

        cover_letter = (WORKSPACE / "cover_letter.tex").read_text(encoding="utf-8")
        normalized_cover_letter = " ".join(cover_letter.split())
        for required_cover_letter_text in [
            "Scientific Reports",
            "Jin Hyun Kim",
            "Associate Professor",
            "jin.kim@gnu.ac.kr",
            "0000-0002-2308-1638",
            "The authors declare no competing interests",
            "NRF-2023R1A2C1006639",
            "v1.0.6-submission",
            "Reviewer suggestions or exclusions",
            "prior discussion with a Scientific Reports Editorial Board Member",
        ]:
            self.assertIn(required_cover_letter_text, normalized_cover_letter)

    def test_submission_sources_support_pdflatex(self) -> None:
        engine_block = (
            "\\usepackage{iftex}\n"
            "\\ifPDFTeX\n"
            "  \\usepackage[utf8]{inputenc}\n"
            "\\else\n"
            "  \\usepackage{fontspec}\n"
            "\\fi"
        )
        for name in ["main.tex", "supplement.tex", "cover_letter.tex"]:
            source = (WORKSPACE / name).read_text(encoding="utf-8")
            preserved = (WORKSPACE / "submission_orig" / name).read_text(encoding="utf-8")
            self.assertTrue(source.startswith("% !TEX program = pdflatex\n"), name)
            self.assertIn(engine_block, source, name)
            self.assertTrue(preserved.startswith("% !TEX program = pdflatex\n"), name)
            self.assertIn(engine_block, preserved, name)

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
            "fig:stability",
            "tab:alignment-summary",
        ]:
            self.assertIn(reference, results)
        for reference in [
            "fig:supp-full-grid",
            "fig:supp-setting-contrasts",
            "fig:supp-outcome-contrasts",
            "tab:supp-six-axis-evidence-stage",
        ]:
            self.assertIn(reference, supplement)
        self.assertNotIn("fig:setting-contrasts", results)
        self.assertNotIn("fig:outcome-contrasts", results)
        self.assertIn("figures/fig5_setting_contrasts.pdf", supplement)
        self.assertIn("figures/fig6_outcome_contrasts.pdf", supplement)
        self.assertIn("generated/stable2_primary_estimates.tex", supplement)
        for main_only_reference in ["tab:primary-evidence", "tab:six-axis-evidence-stage"]:
            self.assertNotIn(main_only_reference, results)
        normalized_results = " ".join(results.split())
        self.assertIn("generated/table1_alignment_summary.tex", results)
        self.assertLess(results.index("generated/table1_alignment_summary.tex"), results.index("\\subsection"))
        self.assertIn("This does not mean that only ISUP describes prostate cancer", normalized_results)
        self.assertIn("SPOP did not yield a qualified representation feature", normalized_results)
        self.assertIn(
            "PTEN- and AR-directed functional tests are feasible follow-up experiments that were not run",
            normalized_results,
        )
        discussion = (WORKSPACE / "sections" / "discussion.tex").read_text(encoding="utf-8")
        normalized_discussion = " ".join(discussion.split())
        self.assertIn("six clinically interpretable axes", normalized_discussion.casefold())
        self.assertIn("PTEN-related information was recoverable", normalized_discussion)
        self.assertIn("Absence of a functional-use result is therefore not one common negative result", normalized_discussion)
        self.assertIn(
            "not a universal or sole organizing target",
            normalized_discussion,
        )
        functional_heading = "ISUP shows encoder-specific external whole-tissue functional transport"
        self.assertLess(results.index("Molecular coordinates"), results.index(functional_heading))
        self.assertLess(results.index("Outcome alignment"), results.index(functional_heading))
        self.assertLess(results.index("Representation audits"), results.index(functional_heading))
        for generated_input in [
            "stable_site_audits.tex",
            "stable_contrast_summary.tex",
            "stable_outcome_reconstructed.tex",
            "stable_outcome_official_pfi.tex",
            "stable_external_functional_transport.tex",
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
        self.assertIn("Supplementary Section S5A reports the 20/20 hash audit", normalized["results"])
        self.assertIn("not an independent-cohort replication", normalized["results"])
        self.assertIn("protocol-locked rerun required unchanged estimates", normalized["methods"])
        self.assertIn("R, recoverability", normalized["methods"])
        self.assertIn("A, internal BCR association", normalized["methods"])
        self.assertIn("U, functional sensitivity", normalized["methods"])
        self.assertIn("T, external transport", normalized["methods"])
        self.assertIn("All 20 regenerated hashes matched exactly", normalized["supplement"])
        self.assertIn(
            "qualifies encoder-specific external whole-tissue functional transport",
            normalized["discussion"],
        )
        self.assertIn("Virchow passed every prespecified gate", normalized["supplement"])
        self.assertIn("all six nonvolatile output hashes exactly", normalized["supplement"])
        self.assertIn("does not itself demonstrate a new residual marker", normalized["conclusion"])
        self.assertIn("after jointly accounting for known clinical--pathology targets and technical confounders", normalized["conclusion"].casefold())
        self.assertIn("recur across models and independent cohorts", normalized["conclusion"])
        self.assertIn("complete explanation of AI representations or decisions", normalized["conclusion"])

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
        self.assertIn(
            "positive values indicate improvement after adding the image-derived score",
            " ".join(results.split()).casefold(),
        )

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

        supplementary_figure_labels = [
            "fig:supp-full-grid",
            "fig:supp-setting-contrasts",
            "fig:supp-outcome-contrasts",
        ]
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
