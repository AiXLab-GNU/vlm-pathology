"""Submission-facing Scientific Reports manuscript contracts."""
from __future__ import annotations

import csv
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from paper.manuscript_contract import (
    count_prose_words,
    extract_environment,
    scan_forbidden_submission_language,
    strip_tex_commands,
    validate_manuscript,
)
from paper.submission_config import MAIN_FIGURES


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    path = ROOT / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _rows(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _appear_in_order(text: str, required: tuple[str, ...]) -> bool:
    position = -1
    for value in required:
        position = text.find(value, position + 1)
        if position < 0:
            return False
    return True


def _subsection_bodies(text: str) -> list[str]:
    return re.split(r"\\subsection\s*\{[^{}]+\}", text)[1:]


def _pdf_text(relative: str) -> str:
    mutool = shutil.which("mutool")
    if mutool is None:
        raise unittest.SkipTest("mutool is required for compiled-PDF text contracts")
    return subprocess.run(
        (mutool, "draw", "-F", "txt", "-o", "-", str(ROOT / relative)),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


class ManuscriptContractUnitTests(unittest.TestCase):
    def test_strip_tex_commands_keeps_visible_prose_only(self) -> None:
        text = (
            "Visible \\textbf{prose} % comment words\n"
            "\\label{sec:ignored} \\cite{ignored2026} $x^2$ \\url{https://example.org/path}"
        )
        self.assertEqual(strip_tex_commands(text), "Visible prose")

    def test_count_prose_words_excludes_metadata_math_and_urls(self) -> None:
        text = (
            "One foundation-model result \\cite{source} has $p = 0.01$ "
            "and \\href{https://example.org}{a link}."
        )
        self.assertEqual(count_prose_words(text), 7)

    def test_citation_variants_and_notes_do_not_count_as_prose(self) -> None:
        text = (
            "Visible \\cite[see][p.~3]{Smith2026} "
            "\\Cite*{Smith2026} \\parencite[see][p.~3]{Smith2026} "
            "\\textcite*{Smith2026} \\autocite[see][p.~3]{Smith2026} "
            "\\footcite*{Smith2026} prose."
        )
        self.assertEqual(strip_tex_commands(text), "Visible prose.")
        self.assertEqual(count_prose_words(text), 2)

    def test_extract_environment_returns_abstract_body(self) -> None:
        text = "before\\begin{abstract}Visible prose.\\end{abstract}after"
        self.assertEqual(extract_environment(text, "abstract"), "Visible prose.")

    def test_extract_environment_preserves_nested_named_environment(self) -> None:
        text = (
            "before\\begin{abstract}Outer "
            "\\begin{abstract}Inner\\end{abstract} tail\\end{abstract}after"
        )
        self.assertEqual(
            extract_environment(text, "abstract"),
            "Outer \\begin{abstract}Inner\\end{abstract} tail",
        )

    def test_forbidden_workflow_patterns_match_labels_with_boundaries(self) -> None:
        text = (
            "Gate A Gate E Gate Q R1 R7 A1 A3 O1 O3 MajorRevision-v1 "
            "Additional GPU unused compute not run optional experiments "
            "internal analysis embargo pending To be completed"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(text, encoding="utf-8")
            findings = scan_forbidden_submission_language(root)
        self.assertEqual(
            set(findings),
            {
                "Gate A", "Gate E", "Gate Q", "R1", "R7", "A1", "A3", "O1", "O3",
                "MajorRevision-v1", "Additional GPU", "unused compute",
                "not run optional experiments", "internal analysis", "embargo pending",
                "To be completed",
            },
        )

    def test_forbidden_workflow_patterns_do_not_match_normal_word_fragments(self) -> None:
        text = "gated gatekeeper R10 AR1 A30 O30 MajorRevision-v10 GPU acceleration"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(text, encoding="utf-8")
            self.assertEqual(scan_forbidden_submission_language(root), [])


class SubmissionDraftContractTests(unittest.TestCase):
    def test_supplement_is_a_separate_compilable_manuscript(self) -> None:
        main = _read("paper/main.tex")
        supplement_main = _read("paper/supplement_main.tex")
        self.assertIn(r"\input{sections/declarations}", main)
        self.assertIn(r"\input{sections/bibliography}", main)
        self.assertNotIn("supplementary_information", main)
        self.assertIn(r"\documentclass", supplement_main)
        self.assertIn(r"\begin{document}", supplement_main)
        self.assertIn(r"\input{sections/supplementary_information}", supplement_main)
        self.assertNotIn(r"\input{main}", supplement_main)

    def test_declaration_bodies_are_explicit_and_not_placeholders(self) -> None:
        declarations = _read("paper/sections/declarations.tex")
        required = (
            "Data Availability",
            "Code Availability",
            "Author Contributions",
            "Competing Interests",
            "Ethics and consent statement",
        )
        for index, heading in enumerate(required):
            start = declarations.find(f"\\section*{{{heading}}}")
            self.assertGreaterEqual(start, 0, heading)
            next_start = (
                declarations.find(r"\section*{", start + 10)
                if index + 1 < len(required)
                else len(declarations)
            )
            body = strip_tex_commands(declarations[start:next_start])
            self.assertGreaterEqual(count_prose_words(body), 8, heading)
        self.assertIn("public cohorts", declarations.lower())
        self.assertIn("access-governed", declarations.lower())
        self.assertIn("derived analysis artifacts", declarations.lower())
        self.assertIn("build_revision_p0_artifacts.py", declarations)
        self.assertNotRegex(declarations, r"(?i)to be completed|tbd|insert here|placeholder")

    def test_citations_resolve_and_bibliography_has_no_verification_debt(self) -> None:
        tex = "\n".join(
            _read(path)
            for path in (
                "paper/main.tex",
                "paper/sections/introduction.tex",
                "paper/sections/methods.tex",
                "paper/sections/declarations.tex",
                "paper/sections/supplementary_information.tex",
            )
        )
        bibliography = _read("paper/sections/bibliography.tex")
        cited: set[str] = set()
        for match in re.finditer(r"\\cite(?:\[[^]]*\])?\{([^{}]+)\}", tex):
            cited.update(key.strip() for key in match.group(1).split(","))
        keys = set(re.findall(r"\\bibitem\{([^{}]+)\}", bibliography))
        self.assertTrue(cited)
        self.assertEqual(cited - keys, set())
        self.assertEqual(len(keys), len(re.findall(r"\\bibitem\{", bibliography)))
        self.assertNotRegex(bibliography, r"(?i)\[VERIFY\]|re-verify|embargo|pending")
        self.assertIn("MIDL 2026", bibliography)
        self.assertRegex(bibliography, r"(?is)leopard2026.*conference")
        self.assertRegex(bibliography, r"(?is)grisi2026.*arXiv:2603\.14187.*preprint")

    def test_author_actions_are_structured_and_keep_package_partial(self) -> None:
        actions = _read("paper/author_action_items.md")
        self.assertIn("package_status: partial", actions)
        self.assertNotIn("package_status: ready", actions)
        items = re.split(r"(?m)^## Action ", actions)[1:]
        self.assertEqual(len(items), 8)
        for item in items:
            with self.subTest(item=item[:60]):
                self.assertRegex(item, r"(?m)^blocking: (?:yes|no)$")
                self.assertRegex(item, r"(?m)^required_value_or_action: \S.+$")
        self.assertRegex(actions, r"(?is)author.*contributions.*blocking: yes")
        self.assertRegex(actions, r"(?is)competing interests.*blocking: yes")
        self.assertRegex(actions, r"(?is)ethics.*blocking: yes")
        self.assertRegex(actions, r"(?is)(?:large.language.model|LLM|Codex).*blocking: yes")
        self.assertEqual(len(re.findall(r"(?m)^blocking: yes$", actions)), 8)

    def test_visible_declarations_are_unambiguously_author_pending(self) -> None:
        declarations = _read("paper/sections/declarations.tex")
        self.assertRegex(declarations, r"(?is)draft status.*author confirmation required")
        self.assertRegex(declarations, r"(?is)author contributions.*must.*before submission")
        self.assertRegex(declarations, r"(?is)competing interests.*must.*before submission")

    def test_code_availability_names_the_public_repository_and_entry_points(self) -> None:
        declarations = _read("paper/sections/declarations.tex")
        flattened = " ".join(declarations.split())
        self.assertIn(
            "https://github.com/AiXLab-GNU/vlm-pathology/tree/"
            "feat/precise-pni-morphology-rereview",
            declarations,
        )
        self.assertNotIn("No public code archive", declarations)
        for path in (
            "models/build_revision_p0_artifacts.py",
            "models/aggregate_stability_grid.py",
            "models/build_tcga_cdr_pfi_evidence.py",
            "models/build_marker7_survival_paired_analysis.py",
            "models/run_marker7_common_source_sensitivity.py",
            "models/build_ar_spop_evidence_closure.py",
        ):
            self.assertIn(path, declarations)
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertIn("patient-level derived outputs are not redistributed", flattened)

    def test_main_and_standalone_supplement_show_same_provisional_metadata_notice(self) -> None:
        notice = (
            "Draft submission metadata: the final author list, affiliations and "
            "corresponding-author details require author confirmation before submission."
        )
        for relative in ("paper/main.tex", "paper/supplement_main.tex"):
            with self.subTest(source=relative):
                visible = strip_tex_commands(_read(relative))
                self.assertIn(notice, visible)
        for relative in ("paper/main.pdf", "paper/supplement_main.pdf"):
            with self.subTest(pdf=relative):
                visible = " ".join(_pdf_text(relative).split())
                self.assertIn(notice, visible)

    def test_llm_assistance_is_disclosed_without_inventing_author_review(self) -> None:
        methods = _read("paper/sections/methods.tex")
        self.assertRegex(methods, r"(?is)large language model.*OpenAI Codex")
        self.assertRegex(methods, r"(?is)code editing.*manuscript")
        self.assertNotRegex(methods, r"(?is)all authors (?:reviewed|approved).*(?:Codex|LLM)")

    def test_supplement_covers_saved_extended_analyses_and_figures(self) -> None:
        supplement = _read("paper/sections/supplementary_information.tex")
        required = (
            "17-test family",
            "72 configurations",
            "360 correlated seed cells",
            "undefined bootstrap",
            "common-498",
            "endpoint concordance",
            "minimum detectable AUROC",
            "not effect-exclusion bounds",
            "target-by-axis evidence coverage",
            "provenance",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), supplement.lower())
        self.assertIn("0.661", supplement)
        self.assertIn("0.685", supplement)
        expected_figures = (
            ("figures/sfig1_detailed_roc.pdf", "fig:supp-discrimination-details"),
            ("figures/sfig2_marker7_survival.pdf", "fig:supp-marker7-survival"),
            ("figures/sfig3_stability_heatmaps.pdf", "fig:supp-stability-heatmaps"),
            ("figures/sfig5_stability_distributions.pdf", "fig:supp-stability-distributions"),
            ("figures/sfig6_endpoint_concordance.pdf", "fig:supp-endpoint-concordance"),
        )
        for output, label in expected_figures:
            self.assertIn(output, supplement)
            self.assertIn(f"\\label{{{label}}}", supplement)
        prohibited = (
            r"\bGate\s+[A-Z0-9]",
            r"\b[RAO][1-7]\b",
            r"MajorRevision",
            r"additional GPU",
            r"360 independent",
        )
        findings = [pattern for pattern in prohibited if re.search(pattern, supplement, re.I)]
        self.assertEqual(findings, [])

    def test_every_supplementary_figure_and_table_has_interpretive_guidance(self) -> None:
        supplement = _read("paper/sections/supplementary_information.tex")
        normalized_supplement = " ".join(supplement.split())
        generated = "\n".join(
            _read(f"paper/generated/stable{index}_{name}.tex")
            for index, name in (
                (1, "endpoint_hierarchy"),
                (2, "multiplicity_family"),
                (3, "stability_summary"),
                (4, "evidence_axis_audit"),
                (5, "analysis_frame_inventory"),
                (6, "stability_contrast_summary"),
                (7, "endpoint_concordance"),
            )
        )
        guidance = (
            "The hierarchy distinguishes what each analysis can answer",
            "no selected subset is presented as the family",
            "directional continuity rather than uniformly precise effect-size estimation",
            "not two replications and not evidence of Official PFI calibration",
            "the 360 cells are not independent validations",
            "evidence completeness is target-specific",
            "the listed counts must be interpreted within their row-specific analysis frames",
            "do not rank encoders causally or turn repeated seeds into independent experiments",
            "raw agreement alone is insufficient",
        )
        for phrase in guidance:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized_supplement)
        self.assertEqual(supplement.count(r"\label{fig:supp-"), 5)
        self.assertEqual(generated.count(r"\label{tab:supp-"), 7)
        for phrase in (
            "hierarchy levels are not interchangeable",
            "Every discovery-family row is shown",
            "Not evaluated and not applicable are not negative results",
            "patients, slides, folds, and settings can overlap across rows",
            "All 390 seed-matched setting contrasts",
            "agreement is raw event agreement",
        ):
            with self.subTest(caption_phrase=phrase):
                self.assertIn(phrase, generated)

    def test_active_tables_are_generated_and_sf1_scope_is_unit_exact(self) -> None:
        supplement = _read("paper/sections/supplementary_information.tex")
        self.assertIn(r"\input{generated/stable2_multiplicity_family.tex}", supplement)
        self.assertIn(r"\input{generated/stable3_stability_summary.tex}", supplement)
        self.assertIn(r"\input{generated/stable4_evidence_axis_audit.tex}", supplement)
        self.assertIn(r"\input{generated/stable5_analysis_frame_inventory.tex}", supplement)
        self.assertIn(r"\input{generated/stable6_stability_contrast_summary.tex}", supplement)
        self.assertIn(r"\input{generated/stable7_endpoint_concordance.tex}", supplement)
        self.assertNotRegex(supplement, r"(?is)\begin\{longtable\}.*complete multiplicity")
        sf1_scope = supplement[
            supplement.index(r"\subsection*{Detailed discrimination summaries}"):
            supplement.index(r"\subsection*{Recurrence endpoints")
        ]
        sf1_flat = " ".join(sf1_scope.split())
        self.assertIn("grade and phenotype transfer across NADT, PANDA and PRECISE", sf1_flat)
        self.assertNotIn("molecular", sf1_scope.lower())
        self.assertIn("Aggregate patient-, case-image-, or session-level estimates", sf1_flat)

    def test_active_submission_uses_fixed_units_and_saved_family_language(self) -> None:
        active = "\n".join(
            _read(path)
            for path in (
                "paper/main.tex", "paper/supplement_main.tex",
                "paper/sections/abstract.tex", "paper/sections/introduction.tex",
                "paper/sections/results.tex", "paper/sections/discussion.tex",
                "paper/sections/methods.tex", "paper/sections/declarations.tex",
                "paper/sections/bibliography.tex", "paper/sections/figure_legends.tex",
                "paper/sections/supplementary_information.tex",
            )
        )
        self.assertNotRegex(active, r"(?i)prespecif")
        self.assertIn(
            "Candidate signals were evaluated at their fixed analysis unit whenever an "
            "endpoint was available.",
            " ".join(_read("paper/sections/results.tex").split()),
        )
        self.assertIn(
            "saved 17-row revision-analysis multiplicity family", " ".join(active.split())
        )

    def test_legacy_bootstrap_accounting_is_explicit_and_not_reconstructed(self) -> None:
        results = " ".join(_read("paper/sections/results.tex").split())
        methods = " ".join(_read("paper/sections/methods.tex").split())
        self.assertIn(
            "2,000 requested resamples; valid and undefined replicate counts were not "
            "retained in the saved legacy output",
            results,
        )
        self.assertIn("saved tables retained interval endpoints", methods)
        self.assertIn("unavailable counts were not reconstructed", methods)
        self.assertIn("Paired recurrence-risk outputs separately retained 2,000 valid and zero undefined", methods)

    def test_official_tcga_cdr_pfi_has_liu_cell_citation(self) -> None:
        methods = _read("paper/sections/methods.tex")
        bibliography = _read("paper/sections/bibliography.tex")
        self.assertRegex(
            methods,
            r"(?s)Official\s+TCGA-CDR PFI[^.]*\\cite\{tcgacdr2018\}",
        )
        self.assertRegex(
            bibliography,
            r"(?is)\\bibitem\{tcgacdr2018\}.*Liu, J\..*\\textit\{Cell\}.*"
            r"173.*400--416\.e11.*10\.1016/j\.cell\.2018\.02\.052",
        )

    def test_figure_legends_are_defined_once_for_inline_rendering(self) -> None:
        legends = _read("paper/sections/figure_legends.tex")
        commands = (
            "figQualificationLegend", "figTransportLegend", "figMolecularLegend",
            "figConfounderLegend", "figMarkerSevenLegend", "figStabilityLegend",
            "figEvidenceAxisLegend",
        )
        for command in commands:
            self.assertEqual(legends.count(rf"\newcommand{{\{command}}}"), 1)
        self.assertNotIn(r"\section*{Figure legends}", legends)
        stable3 = _read("paper/generated/stable3_stability_summary.tex")
        self.assertIn(r"\captionof{table}", stable3)
        self.assertIn("justification=raggedright", stable3)

    def test_main_and_supplement_figure_legends_are_self_contained(self) -> None:
        legends = _read("paper/sections/figure_legends.tex")
        blocks = {
            match.group(1): " ".join(match.group(2).split())
            for match in re.finditer(
                r"\\newcommand\{\\(\w+)\}\{%?(.*?)(?=\n\\newcommand|\Z)",
                legends,
                flags=re.DOTALL,
            )
        }
        required_by_legend = {
            "figQualificationLegend": (
                r"\textbf{a}", r"\textbf{b}", "four primary decisions",
                "not a model-performance ranking",
            ),
            "figTransportLegend": (
                "Filled circles", "open circles", "metric null", "case-image",
            ),
            "figMolecularLegend": (
                r"\textbf{a--b}", "60 correlated", "cross marks CH", "Dashed lines",
            ),
            "figConfounderLegend": (
                "patient-cluster bootstrap", "slide/patient denominators",
                "positive increments",
            ),
            "figMarkerSevenLegend": (
                "2,000 valid paired draws", "IBS improvement is reference minus comparison",
                "endpoint definitions are not equivalent",
            ),
            "figStabilityLegend": (
                "12 encoder--scale--tile configurations", "65 seed-matched",
                "population uncertainty estimates",
            ),
            "figEvidenceAxisLegend": (
                "six distinct qualification axes", "Not evaluated and not applicable",
                "supplementary evidence-axis audit table",
            ),
        }
        self.assertEqual(set(blocks), set(required_by_legend))
        for command, phrases in required_by_legend.items():
            for phrase in phrases:
                with self.subTest(command=command, phrase=phrase):
                    self.assertIn(phrase, blocks[command])

        results = " ".join(_read("paper/sections/results.tex").split())
        self.assertIn(
            "At the CH site (a deidentified source institution code), no patient was "
            "SPOP-positive",
            results,
        )
        self.assertIn("other five source-coded sites included the AUROC null", results)

        supplement = " ".join(
            _read("paper/sections/supplementary_information.tex").split()
        )
        for phrase in (
            "Filled points with whiskers",
            "connecting lines are visual guides across quintiles",
            "shared 1.76~$\\mu$m-per-pixel minus native scale (180)",
            "The abscissa is metric $B-A$",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, supplement)

    def test_figure_one_explains_each_decision_and_hierarchy_encoding(self) -> None:
        results = " ".join(_read("paper/sections/results.tex").split())
        legends = " ".join(_read("paper/sections/figure_legends.tex").split())
        for phrase in (
            "The horizontal position of each dot records an evidence decision, not an "
            "effect size or a ranking",
            "Grade and phenotype occupy the transportable column",
            "PTEN remains context-sensitive",
            "AR is also context-sensitive",
            "SPOP is unsupported in the frozen primary design",
            "The two recurrence rows apply different questions to the same post-hoc Cox "
            "risk score",
            "Recurrence transfer asks whether",
            "recurrence increment asks whether",
            "Panel b counts how many decisions were primary or exploratory",
        ):
            with self.subTest(location="results", phrase=phrase):
                self.assertIn(phrase, results)
        for phrase in (
            "Transportable denotes directionally consistent cross-cohort evidence",
            "context-sensitive denotes an interpretation restricted by confounding",
            "not biological absence",
            "The two recurrence rows apply different questions to the same post-hoc Cox "
            "risk score",
            "Bar lengths count four primary decisions and two exploratory recurrence-risk "
            "decisions",
            "they do not encode performance, effect magnitude, or evidentiary strength",
        ):
            with self.subTest(location="legend", phrase=phrase):
                self.assertIn(phrase, legends)

    def test_supplement_numbering_and_first_citation_order_are_s1_to_s7(self) -> None:
        supplement_main = _read("paper/supplement_main.tex")
        supplement = _read("paper/sections/supplementary_information.tex")
        self.assertIn(r"\renewcommand{\thefigure}{S\arabic{figure}}", supplement_main)
        self.assertIn(r"\renewcommand{\thetable}{S\arabic{table}}", supplement_main)
        self.assertIn(r"\usepackage{pdflscape}", supplement_main)
        labels = (
            "fig:supp-discrimination-details",
            "fig:supp-marker7-survival",
            "fig:supp-stability-heatmaps",
            "fig:supp-stability-distributions",
            "fig:supp-endpoint-concordance",
        )
        self.assertTrue(_appear_in_order(supplement, labels))
        generated_tables = (
            _read("paper/generated/stable1_endpoint_hierarchy.tex")
            + _read("paper/generated/stable2_multiplicity_family.tex")
            + _read("paper/generated/stable3_stability_summary.tex")
            + _read("paper/generated/stable4_evidence_axis_audit.tex")
            + _read("paper/generated/stable5_analysis_frame_inventory.tex")
            + _read("paper/generated/stable6_stability_contrast_summary.tex")
            + _read("paper/generated/stable7_endpoint_concordance.tex")
        )
        stable4 = _read("paper/generated/stable4_evidence_axis_audit.tex")
        self.assertNotIn(r"\begin{landscape}", stable4)
        self.assertIn(r"\fontsize{9.5pt}{11pt}\selectfont", stable4)
        evidence_section = supplement[
            supplement.index("\\begin{landscape}\n\\subsection*{Target-by-axis"):
            supplement.index("\\clearpage\n\n\\begin{landscape}", supplement.index(
                r"\subsection*{Target-by-axis"
            ))
        ]
        self.assertIn(r"\input{generated/stable4_evidence_axis_audit.tex}", evidence_section)
        self.assertIn(r"\end{landscape}", evidence_section)
        self.assertEqual(supplement.count(r"\caption{"), 5)
        self.assertEqual(
            generated_tables.count(r"\caption{")
            + generated_tables.count(r"\captionof{table}"),
            7,
        )

    def test_supplementary_figure_3_places_six_heatmaps_two_up(self) -> None:
        supplement = _read("paper/sections/supplementary_information.tex")
        self.assertNotRegex(supplement, r"\\includepdf")
        self.assertNotRegex(supplement, r"pages\s*=\s*-")
        page_calls = re.findall(
            r"\\includegraphics\[([^]]*page\s*=\s*(\d+)[^]]*)\]"
            r"\{figures/sfig3_stability_heatmaps\.pdf\}",
            supplement,
        )
        self.assertEqual([int(page) for _options, page in page_calls], list(range(1, 10)))
        for options, page in page_calls:
            with self.subTest(page=page):
                self.assertRegex(options, r"width\s*=\s*0\.9[0-9]\\textwidth")
                self.assertRegex(options, r"height\s*=\s*0\.[0-8][0-9]\\textheight")
                self.assertIn("keepaspectratio", options)
                height = float(re.search(r"height\s*=\s*(0\.[0-9]+)", options).group(1))
                if int(page) <= 6:
                    self.assertLessEqual(height, 0.39)
        self.assertIn("heatmaps 3--4 of 6", supplement)
        self.assertIn("heatmaps 5--6 of 6", supplement)
        self.assertEqual(supplement.count("Supplementary Figure S3 (continued;"), 5)
        page_one = supplement.find("page=1")
        caption = supplement.find(r"\caption{\textbf{Complete stability grids")
        self.assertGreaterEqual(page_one, 0)
        self.assertGreater(caption, page_one)
        self.assertLess(caption - page_one, 1600)

    def test_supplementary_figure_2_is_exactly_legacy_reconstructed_endpoint(self) -> None:
        supplement = _read("paper/sections/supplementary_information.tex")
        self.assertRegex(supplement, r"(?is)supplementary figure.*reconstructed with-tumor")
        self.assertRegex(supplement, r"(?is)not.*official TCGA-CDR PFI")
        self.assertRegex(supplement, r"(?is)270 patients.*57 events")

    def test_references_heading_is_owned_once_by_thebibliography(self) -> None:
        main = _read("paper/main.tex")
        bibliography = _read("paper/sections/bibliography.tex")
        self.assertNotIn(r"\section*{References}", main)
        self.assertEqual(bibliography.count(r"\begin{thebibliography}"), 1)

    def test_seven_complete_figure_legends_render_with_their_figures(self) -> None:
        main = _read("paper/main.tex")
        results = _read("paper/sections/results.tex")
        legends = _read("paper/sections/figure_legends.tex")
        self.assertLess(
            main.index(r"\input{sections/figure_legends}"), main.index(r"\begin{document}")
        )
        commands = (
            "figQualificationLegend", "figTransportLegend", "figMolecularLegend",
            "figConfounderLegend", "figMarkerSevenLegend", "figStabilityLegend",
            "figEvidenceAxisLegend",
        )
        self.assertEqual(results.count(r"\caption{"), 7)
        self.assertNotIn(r"\refstepcounter{figure}", results)
        for command in commands:
            self.assertEqual(results.count(rf"\caption{{\{command}}}"), 1)
        self.assertEqual(legends.count(r"\newcommand{"), 7)

    def test_compiled_main_has_inline_legends_and_no_legend_appendix(self) -> None:
        text = _pdf_text("paper/main.pdf")
        self.assertEqual(len(re.findall(r"(?m)^References\s*$", text)), 1)
        self.assertNotIn("Figure legends", text)
        for number in range(1, 8):
            self.assertEqual(len(re.findall(rf"Figure {number}:", text)), 1)

    def test_compiled_supplement_exposes_s1_s2_s3_and_legacy_endpoint(self) -> None:
        text = _pdf_text("paper/supplement_main.pdf")
        for number in range(1, 4):
            self.assertRegex(text, rf"Supplementary Figure S{number}")
        for number in range(1, 3):
            self.assertRegex(text, rf"Supplementary Table S{number}")
        self.assertIn("Reconstructed with-tumor endpoint", text)
        self.assertIn("not Official TCGA-CDR PFI", text)

    def test_submission_title_abstract_section_order_and_declarations(self) -> None:
        results = {row.check_id: row for row in validate_manuscript(ROOT)}
        for check_id in (
            "TITLE_WORDS_LE_20",
            "ABSTRACT_WORDS_LE_200",
            "SECTION_ORDER",
            "DECLARATIONS_PRESENT",
        ):
            with self.subTest(check_id=check_id):
                self.assertTrue(results[check_id].passed)

    def test_submission_has_no_internal_workflow_or_embargo_block_text(self) -> None:
        failures = scan_forbidden_submission_language(ROOT)
        self.assertEqual(failures, [])

    def test_title_and_abstract_meet_scientific_reports_targets(self) -> None:
        main = _read("paper/main.tex")
        abstract = extract_environment(_read("paper/sections/abstract.tex"), "abstract")
        self.assertIn(
            "\\title{Qualification of Pathology Foundation-Model Signals Across Cohorts, "
            "Sites and Clinical Endpoints}",
            main,
        )
        self.assertIn("\\date{}", main)
        self.assertGreaterEqual(count_prose_words(abstract), 170)
        self.assertLessEqual(count_prose_words(abstract), 195)
        self.assertIsNone(re.search(r"\\[A-Za-z@]*cite", abstract, flags=re.IGNORECASE))

    def test_results_use_approved_decision_order_and_explicit_decisions(self) -> None:
        text = _read("paper/sections/results.tex")
        required = (
            "Qualification framework converts the propositions into evidence tests",
            "Morphology-linked signals show the strongest cross-cohort transport",
            "Pooled molecular associations do not determine qualification",
            "Confounder and site audits narrow the PTEN and AR claims",
            "Recurrence transfer changes with endpoint and covariate hierarchy",
            "Correlated setting audits distinguish stable from conditional signals",
            "Joint evidence states replace a single performance ranking",
        )
        self.assertTrue(_appear_in_order(text, required))
        bodies = _subsection_bodies(text)
        self.assertEqual(len(bodies), 7)
        self.assertIn("Evidence test", bodies[0])
        self.assertIn("Interpretive boundary", bodies[0])
        self.assertIn("Qualification rule", bodies[0])
        for body in bodies[1:6]:
            with self.subTest(body=strip_tex_commands(body)[:60]):
                self.assertIn("Analysis frame", body)
                self.assertIn("Evidence state", body)
                self.assertIn("Local limitation", body)
                self.assertIn("Qualification decision", body)
        self.assertIn("Qualification decision", bodies[6])
        self.assertIn("primary synthesis", bodies[6])

    def test_discussion_uses_five_bounded_parts(self) -> None:
        text = _read("paper/sections/discussion.tex")
        required = (
            "The contribution is a qualification logic, not another performance benchmark",
            "The three propositions are supported at different evidentiary levels",
            "Why pooled performance fails as a scientific claim",
            "Limitations and unresolved inferential problems",
            "Implications and conclusion",
        )
        self.assertTrue(_appear_in_order(text, required))
        self.assertEqual(len(_subsection_bodies(text)), 5)

    def test_sections_and_subsections_open_with_navigational_sentences(self) -> None:
        results = " ".join(_read("paper/sections/results.tex").split())
        discussion = " ".join(_read("paper/sections/discussion.tex").split())
        methods = " ".join(_read("paper/sections/methods.tex").split())
        supplement = " ".join(
            _read("paper/sections/supplementary_information.tex").split()
        )
        required = {
            results: (
                "The Results test the three propositions in sequence",
                "We begin by converting the study propositions",
                "Having defined the qualification rule, we first test",
                "We next ask whether pooled molecular associations",
                "this subsection tests whether the PTEN and AR signals",
                "We then examine whether the exploratory recurrence signal",
                "we assess whether each interpretation remains stable",
                "Finally, we integrate the preceding evidence axes",
            ),
            discussion: (
                "The Discussion interprets the evidence states",
                "We first clarify the study's central contribution",
                "We next consider the three propositions separately",
                "The target-specific results motivate a broader explanation",
                "these limitations bound every qualification decision",
                "We close by translating the unresolved evidence axes",
            ),
            methods: (
                "The Methods follow the same evidentiary sequence",
                "This subsection defines the data source, label provenance",
                "With the cohorts defined, we describe how frozen image representations",
                "preventing information from the same patient",
                "converted into evidence states",
                "two alternative explanations for pooled performance",
                "without treating reused cohorts and folds as independent validation data",
                "keep the competing endpoint definitions separate",
                "how unavailable outcomes or unretained bootstrap accounting were handled",
                "Finally, we describe the records that connect each manuscript result",
            ),
            supplement: (
                "This subsection enumerates the complete multiplicity family",
                "We first expand the cross-cohort grade and phenotype evidence",
                "paired uncertainty estimation, and restriction to a common patient source frame",
                "We next expose the complete sensitivity grid",
                "This subsection makes the synthesis explicit",
                "the site-specific AR interpretation",
                "The final subsection identifies the saved records",
            ),
        }
        for text, phrases in required.items():
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    self.assertIn(phrase, text)

    def test_main_narrative_and_methods_structure_are_bounded(self) -> None:
        narrative = "\n".join(
            _read(path)
            for path in (
                "paper/sections/introduction.tex",
                "paper/sections/results.tex",
                "paper/sections/discussion.tex",
            )
        )
        self.assertLessEqual(count_prose_words(narrative), 4500)
        methods = _read("paper/sections/methods.tex")
        required = (
            "Cohorts and labels",
            "Frozen embeddings and aggregation",
            "Fixed probes and patient-disjoint evaluation",
            "Qualification criteria and multiplicity",
            "Confounder and site analyses",
            "Correlated stability analysis",
            "Recurrence endpoints and paired comparisons",
            "Bootstrap uncertainty and missingness",
            "Software and provenance",
        )
        self.assertTrue(_appear_in_order(methods, required))
        self.assertRegex(methods, r"(?is)PCA.*exploratory sensitivity")
        self.assertRegex(methods, r"(?is)not.*nested.*unbiased.*selection")

    def test_all_seven_main_figures_are_referenced(self) -> None:
        results = _read("paper/sections/results.tex")
        expected = (
            ("figures/fig1_qualification_map.pdf", "fig:qualification-framework"),
            ("figures/fig2_transportable_signals.pdf", "fig:transportable-signals"),
            ("figures/fig3_molecular_qualification.pdf", "fig:molecular-qualification"),
            ("figures/fig4_confounder_site_audit.pdf", "fig:confounder-site-audit"),
            ("figures/fig5_marker7_transfer.pdf", "fig:marker7-transfer"),
            ("figures/fig6_stability_overview.pdf", "fig:stability-overview"),
            ("figures/fig7_evidence_axis_matrix.pdf", "fig:evidence-axis-matrix"),
        )
        for output, label in expected:
            with self.subTest(label=label):
                self.assertIn(output, results)
                self.assertIn(f"\\label{{{label}}}", results)

    def test_submission_avoids_prohibited_scientific_claims(self) -> None:
        text = "\n".join(
            _read(path)
            for path in (
                "paper/main.tex",
                "paper/sections/abstract.tex",
                "paper/sections/introduction.tex",
                "paper/sections/results.tex",
                "paper/sections/discussion.tex",
                "paper/sections/methods.tex",
            )
        )
        prohibited = (
            r"robust null",
            r"universal encoder",
            r"360 independent",
            r"clinically validated",
            r"prognostic biomarker",
            r"external validation",
            r"clinical utility",
            r"treatment guidance",
            r"whole-slide diagnos",
        )
        findings = [pattern for pattern in prohibited if re.search(pattern, text, re.I)]
        self.assertEqual(findings, [])

    def test_typed_results_track_saved_numeric_sources(self) -> None:
        results = _read("paper/sections/results.tex")
        results_without_math_delimiters = results.replace("$", "")
        f2 = {row["semantic_key"]: row for row in _rows(
            "paper/figure_data/fig2_transportable_signals.csv"
        )}
        f3 = {row["semantic_key"]: row for row in _rows(
            "paper/figure_data/fig3_molecular_qualification.csv"
        )}
        f4 = {row["semantic_key"]: row for row in _rows(
            "paper/figure_data/fig4_confounder_site_audit.csv"
        )}
        f5 = {row["semantic_key"]: row for row in _rows(
            "paper/figure_data/fig5_marker7_transfer.csv"
        )}
        f6 = {row["semantic_key"]: row for row in _rows(
            "paper/figure_data/fig6_stability_overview.csv"
        )}
        expected_fragments = (
            f"{float(f2['gleason:nadt']['primary_estimate']):.3f}",
            f"{float(f2['phenotype_panda:radboud']['primary_estimate']):.3f}",
            f"{float(f3['pten:frozen_primary']['primary_estimate']):.3f}",
            f"{float(f3['spop:configuration_summary']['range_low']):.3f}--"
            f"{float(f3['spop:configuration_summary']['range_high']):.3f}",
            f"{float(f4['pten:CONCH:increment']['primary_estimate']):+.3f}",
            f"{float(f5['E08_official_pfi:frozen_risk:c_index']['primary_estimate']):.3f}",
            f"{float(f5['E04_reconstructed_with_tumor:GRADE_COMBINED_VS_GRADE:c_index']['primary_estimate']):+.3f}",
            f"{int(float(f6['spop:configuration_range']['n_null_crossings']))}/"
            f"{int(float(f6['spop:configuration_range']['n_configurations']))}",
        )
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, results_without_math_delimiters)

    def test_stability_counts_distinguish_seed_ranges_from_t_intervals(self) -> None:
        results = _read("paper/sections/results.tex")
        summary = _rows("models/stability_summary.csv")
        for marker, range_count, t_count in (("spop", 8, 9), ("marker7", 1, 2)):
            rows = [row for row in summary if row["marker"] == marker]
            null = float(rows[0]["null_value"])
            observed_range_straddles = sum(
                float(row["min"]) < null < float(row["max"]) for row in rows
            )
            t_interval_contains_null = sum(
                float(row["sampling_seed_t_ci_low"]) <= null
                <= float(row["sampling_seed_t_ci_high"])
                for row in rows
            )
            self.assertEqual(observed_range_straddles, range_count)
            self.assertEqual(t_interval_contains_null, t_count)
        self.assertIn("observed five-seed range straddled", results)
        self.assertIn("SPOP in $8/12$", results)
        self.assertIn("recurrence risk signal in $1/12$", results)
        self.assertNotIn("sampling-seed interval crossing", results)
        self.assertIn("$6\\times12\\times5=360$ correlated seed cells", results)
        self.assertNotRegex(results, r"(?i)360\s+independent")
        self.assertIn("seed-cell range", results)

    def test_first_use_defines_key_abbreviations_and_legacy_marker_name(self) -> None:
        abstract = " ".join(_read("paper/sections/abstract.tex").split())
        introduction = " ".join(_read("paper/sections/introduction.tex").split())
        results = " ".join(_read("paper/sections/results.tex").split())
        legends = " ".join(_read("paper/sections/figure_legends.tex").split())
        supplement = " ".join(
            _read("paper/sections/supplementary_information.tex").split()
        )
        for phrase in (
            "CONtrastive learning from Captions for Histopathology (CONCH)",
            "phosphatase and tensin homolog (PTEN)",
            "speckle type BTB/POZ protein (SPOP)",
            "androgen-receptor (AR) activity",
            "The Cancer Genome Atlas prostate adenocarcinoma (TCGA-PRAD)",
        ):
            self.assertIn(phrase, abstract)
        for phrase in (
            "area under the receiver operating characteristic curve (AUROC)",
            "Prostate cANcer graDe Assessment (PANDA)",
            "International Society of Urological Pathology (ISUP)",
        ):
            self.assertIn(phrase, introduction + " " + results)
        self.assertIn("called ``marker 7'' only in legacy analysis artifacts", results)
        self.assertIn("post-hoc recurrence risk signal in the manuscript", results)
        self.assertIn("integrated Brier score (IBS)", results)
        self.assertIn("CH site (a deidentified source institution code)", results)
        self.assertIn("legacy analysis identifier was ``marker 7.''", legends)
        self.assertIn(r"\noindent\textbf{Abbreviations.}", supplement)

    def test_panda_sampling_labels_events_and_probe_are_disclosed(self) -> None:
        results = _read("paper/sections/results.tex")
        methods = _read("paper/sections/methods.tex")
        expected_results = (
            "100-case cap per institution--International Society of Urological Pathology (ISUP) stratum",
            "1,200 sampled cases",
            "1,137 passed tissue filtering",
            "469/565 tumor cases",
            "483/572 tumor cases",
            "ISUP 0 as benign and ISUP $\\geq1$ as tumor",
        )
        for phrase in expected_results:
            self.assertIn(phrase, results)
        self.assertIn(r"LogisticRegression}\allowbreak\texttt{(C=1.0)", methods)
        self.assertIn("without class weighting", methods)
        self.assertNotIn("all binary probes use", methods.lower())
        self.assertIn("labels and predictions were aggregated within patient", methods)

    def test_cohort_label_provenance_distinguishes_source_from_derivation(self) -> None:
        methods = _read("paper/sections/methods.tex")
        normalized = " ".join(methods.split())
        self.assertIn(
            "per-core or per-slide grade and phenotype labels, and patient identifiers",
            normalized,
        )
        self.assertIn(
            "PANDA provided institution-labelled case images and official ISUP grades",
            normalized,
        )
        self.assertIn(
            "tumor/benign phenotype was derived as ISUP 0 versus ISUP at least 1",
            normalized,
        )
        self.assertNotIn("patient-level grade and phenotype labels", methods)
        self.assertNotIn("with ISUP grade and tumor/benign labels", methods)

    def test_introduction_orients_pathology_and_medical_ai_readers(self) -> None:
        introduction = " ".join(_read("paper/sections/introduction.tex").split())
        for phrase in (
            "Clinical and analytical orientation",
            "Gleason grading summarizes the gland-forming architecture of prostate cancer",
            "higher scores or International Society of Urological Pathology (ISUP) Grade "
            "Groups indicate less differentiated morphology",
            "Tumor phenotype'' instead denotes the dataset-specific tumor-content target",
            "it is not a molecular subtype",
            "PTEN loss is loss of a tumor-suppressor signal",
            "SPOP mutation is a recurrent genomic alteration",
            "AR activity is a continuous measure of androgen-receptor-regulated transcription",
            "not claims that routine morphology directly diagnoses the underlying alteration",
            "Spearman correlation measures preservation of continuous or ordinal ranking",
            "area under the receiver operating characteristic curve (AUROC) measures binary "
            "discrimination",
            "the concordance index measures time-to-event risk ordering",
            "do not by themselves establish calibration, causal interpretation, or "
            "readiness for clinical use",
            "transfer without refitting means applying that source-cohort probe unchanged",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, introduction)

    def test_main_text_exposes_study_frames_and_integrated_evidence_axes(self) -> None:
        introduction = " ".join(_read("paper/sections/introduction.tex").split())
        results = " ".join(_read("paper/sections/results.tex").split())
        for phrase in (
            "Study resources, analysis frames, and roles in signal qualification",
            "NADT-Prostate \\cite{nadt2021} & Grade and phenotype; 39 patients",
            "565 Karolinska and 572 Radboud case images",
            "Molecular analyses: 273 patients; recurrence transfer: 270 patients",
            "72 configurations, 360 seed cells, and 390 paired contrasts",
            "must not be summed because patients, slides, folds, and settings can overlap",
        ):
            with self.subTest(frame_phrase=phrase):
                self.assertIn(phrase, introduction)
        for phrase in (
            r"Figure~\ref{fig:evidence-axis-matrix} summarizes the complete study architecture",
            "Unevaluated or unresolved cells identify open evidence gaps",
            r"\label{fig:evidence-axis-matrix}",
        ):
            with self.subTest(matrix_phrase=phrase):
                self.assertIn(phrase, results)

    def test_cross_disciplinary_terms_are_defined_at_point_of_use(self) -> None:
        introduction = " ".join(_read("paper/sections/introduction.tex").split())
        methods = " ".join(_read("paper/sections/methods.tex").split())
        legends = " ".join(_read("paper/sections/figure_legends.tex").split())
        supplement = " ".join(
            _read("paper/sections/supplementary_information.tex").split()
        )
        for phrase in (
            "digitized views of complete tissue sections",
            "a tile is a small crop sampled from a whole-slide image",
            "A held-out estimate is computed on patients not used to fit",
            "A null denotes the no-association or chance benchmark",
            "copy-number loss means fewer genomic copies than the reference state",
            "Ridge regression is linear regression with coefficient shrinkage",
            "zero-shot transfer, meaning direct application to a new cohort",
            "The Mann--Whitney test compares score distributions between two groups",
            "This nested evaluation separates inner model construction from outer testing",
            "The Cox model relates predictors to relative event hazard",
            "A cryptographic hash is a file fingerprint",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, introduction + " " + methods)
        self.assertIn("Held-out means evaluated on patients not used for fitting", legends)
        self.assertIn("a seed cell is one score from one reproducible", legends)
        self.assertIn("Cohen's kappa measures agreement", supplement)
        self.assertIn("Kaplan--Meier is a nonparametric estimate", supplement)
        self.assertIn("minimum detectable'' means the smallest assumed AUROC", supplement)
        self.assertIn("A SHA256 hash is a file fingerprint", supplement)

    def test_nadt_results_name_local_bootstrap_interval_and_resamples(self) -> None:
        results = _read("paper/sections/results.tex")
        nadt = results.split("Among 39 NADT-Prostate patients", 1)[1].split(
            "In PANDA", 1
        )[0]
        nadt_flat = " ".join(nadt.split())
        self.assertEqual(nadt.count(r"95\% percentile patient-bootstrap interval"), 2)
        self.assertEqual(nadt.count("2,000 requested resamples"), 2)
        self.assertEqual(
            nadt_flat.count("valid and undefined replicate counts were not retained"), 2
        )

    def test_figure_two_states_transport_scope_and_precision_limit(self) -> None:
        results = " ".join(_read("paper/sections/results.tex").split())
        legends = " ".join(_read("paper/sections/figure_legends.tex").split())
        for text in (results, legends):
            self.assertIn(
                "Grade signals retained a positive direction in both PANDA and PRECISE",
                text,
            )
            self.assertIn(
                "phenotype discrimination was retained in the Karolinska and Radboud "
                "PANDA subsets",
                text,
            )
            self.assertIn(
                "strongest cross-cohort transport evidence among the evaluated targets",
                text,
            )
        self.assertIn(
            "no uncertainty intervals were saved for the PANDA or PRECISE estimates",
            results,
        )
        self.assertIn("precision of their effect sizes remains unresolved", legends)

    def test_multiplicity_sidedness_and_bootstrap_are_exact(self) -> None:
        methods = _read("paper/sections/methods.tex")
        required = (
            "13 marker hypotheses",
            "seven additional screening candidates",
            "four nested/refit confounder audits",
            "two-sided Spearman",
            "two-sided Mann--Whitney",
            "one-sided refit-permutation",
            "$\\alpha=0.05$",
            "Benjamini--Hochberg false-discovery-rate",
            "95\% percentile patient-bootstrap intervals",
            "except requested 2,000 where explicitly recorded",
            "2,000 valid and zero undefined replicates",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, methods)

    def test_figure_environment_order_matches_active_figure_identity(self) -> None:
        results = _read("paper/sections/results.tex")
        environments = re.findall(
            r"\\begin\{figure\}.*?\\end\{figure\}", results, flags=re.DOTALL
        )
        actual: list[tuple[str, str]] = []
        for environment in environments:
            output = re.search(r"\\includegraphics(?:\[[^]]*\])?\{([^{}]+)\}", environment)
            label = re.search(r"\\label\{([^{}]+)\}", environment)
            self.assertIsNotNone(output)
            self.assertIsNotNone(label)
            actual.append((f"paper/{output.group(1)}", label.group(1)))
        expected = [(figure.output, figure.label) for figure in MAIN_FIGURES]
        self.assertEqual(actual, expected)
        first_reference_positions = [
            results.find(f"\\ref{{{figure.label}}}") for figure in MAIN_FIGURES
        ]
        self.assertNotIn(-1, first_reference_positions)
        self.assertEqual(first_reference_positions, sorted(first_reference_positions))

    def test_pten_seed_cell_range_has_one_primary_narrative_location(self) -> None:
        results = _read("paper/sections/results.tex").replace("$", "")
        self.assertEqual(results.count("0.519--0.717"), 1)

    def test_all_typed_results_numbers_are_on_validated_allowlist(self) -> None:
        results = _read("paper/sections/results.tex")
        cleaned = re.sub(
            r"\\(?:includegraphics|label|ref)\s*(?:\[[^]]*\])?\{[^{}]*\}", "", results
        ).replace("--", " to ")
        found = set(re.findall(
            r"(?<![A-Za-z])(?:[+-]?\d+(?:,\d{3})*(?:\.\d+)?(?:/\d+)?)", cleaned
        ))
        # Literals are validated against fig2--fig6 source CSVs, the PANDA cached rows,
        # and the saved grid schema. This is an allowlist, not a claim that every value
        # must appear in every manuscript revision.
        allowed = {
            "-0.040", "-0.036", "-0.025", "-0.015", "-0.013",
            "+0.004", "+0.012", "+0.019", "+0.032", "+0.035", "+0.042",
            "+0.051", "+0.068", "+0.083", "+0.087", "+0.126", "+0.157",
            "0.074", "0.136", "0.170", "0.195", "0.271", "0.297", "0.310",
            "0.348", "0.354", "0.408", "0.478", "0.482", "0.519", "0.560",
            "0.586", "0.587", "0.625", "0.627", "0.632", "0.646", "0.673",
            "0.679", "0.689", "0.706", "0.712", "0.717", "0.759", "0.786",
            "0.800", "0.845", "0.865", "0.871", "0.909", "0.965",
            "0", "1/12", "8/12", "469/565", "483/572", "1,137", "1,200",
            "2", "2,000", "5", "6", "7", "12",
            "15", "17", "30", "39", "42", "57", "60", "95", "100", "153",
            "270", "273", "360", "469", "483", "565", "572",
        }
        self.assertEqual(found - allowed, set())


if __name__ == "__main__":
    unittest.main()
