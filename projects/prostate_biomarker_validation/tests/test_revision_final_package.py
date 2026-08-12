"""End-to-end contracts for the Scientific Reports submission package."""
from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pandas as pd

from projects.prostate_biomarker_validation.paper import build_revision_package as builder


ROOT = Path(__file__).resolve().parents[3]
HEX64 = r"[0-9a-f]{64}"


class RevisionFinalPackageTests(unittest.TestCase):
    def test_public_builder_interface_exists(self):
        self.assertTrue(hasattr(builder, "build_submission_package"))
        self.assertTrue(hasattr(builder, "PackageReport"))

    def test_staged_build_preserves_final_audit_reports_byte_for_byte(self):
        report_names = (
            "MajorRevision-v1-compliance-report.md",
            "numeric_consistency_report.md",
            "reproducibility_report.md",
        )
        with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as stage_tmp:
            source_paper = Path(source_tmp) / "paper"
            source_paper.mkdir()
            expected = {}
            for index, name in enumerate(report_names, start=1):
                payload = f"final audit report {index}\n".encode()
                (source_paper / name).write_bytes(payload)
                expected[name] = payload

            stage = Path(stage_tmp)
            with mock.patch.object(builder, "PAPER", source_paper):
                builder._copy_paper_sources(stage)
            builder._write_reports(stage, build_pdf=False, status="partial", blocker_count=8)

            actual = {
                name: (stage / "paper" / name).read_bytes() for name in report_names
            }
            self.assertEqual(actual, expected)

    def test_repository_publish_does_not_replace_final_audit_reports(self):
        report_names = (
            "MajorRevision-v1-compliance-report.md",
            "numeric_consistency_report.md",
            "reproducibility_report.md",
        )
        always_published = (
            "figure_manifest.csv", "table_manifest.csv", "numeric_qa_mapping.csv",
            "numeric_consistency_report.csv", "results_numeric_derivations.csv",
            "compliance_report.md",
        )
        with tempfile.TemporaryDirectory() as stage_tmp, tempfile.TemporaryDirectory() as out_tmp:
            stage, output = Path(stage_tmp), Path(out_tmp)
            (stage / "paper").mkdir()
            (output / "paper").mkdir()
            before = {}
            for index, name in enumerate(report_names, start=1):
                payload = f"root final audit report {index}\n".encode()
                (output / "paper" / name).write_bytes(payload)
                (stage / "paper" / name).write_text(
                    f"staged replacement {index}\n", encoding="utf-8"
                )
                before[name] = payload
            for name in always_published:
                (stage / "paper" / name).write_text(
                    f"fresh {name}\n", encoding="utf-8"
                )

            with (
                mock.patch.object(builder, "MAIN_FIGURES", ()),
                mock.patch.object(builder, "SUPPLEMENT_FIGURES", ()),
                mock.patch.object(builder, "TABLES", ()),
                mock.patch.object(builder, "OPTIONAL_BUILD_OUTPUTS", ()),
            ):
                builder._transactional_publish(stage, output, repository_run=True)

            after = {
                name: (output / "paper" / name).read_bytes() for name in report_names
            }
            self.assertEqual(after, before)
            self.assertEqual(
                (output / "paper/compliance_report.md").read_text(encoding="utf-8"),
                "fresh compliance_report.md\n",
            )

    def test_copy_paper_sources_fails_closed_when_final_audit_report_is_missing(self):
        with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as stage_tmp:
            source_paper = Path(source_tmp) / "paper"
            source_paper.mkdir()
            (source_paper / "MajorRevision-v1-compliance-report.md").write_text(
                "present\n", encoding="utf-8"
            )
            (source_paper / "numeric_consistency_report.md").write_text(
                "present\n", encoding="utf-8"
            )
            with mock.patch.object(builder, "PAPER", source_paper):
                with self.assertRaisesRegex(
                    FileNotFoundError, "final-audit report.*reproducibility_report"
                ):
                    builder._copy_paper_sources(Path(stage_tmp))

    def test_temporary_build_covers_active_assets_without_mutating_repository(self):
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "projects/prostate_biomarker_validation/paper/figure_manifest.csv",
                ROOT / "projects/prostate_biomarker_validation/paper/table_manifest.csv",
                ROOT / "projects/prostate_biomarker_validation/paper/main.pdf",
                ROOT / "projects/prostate_biomarker_validation/paper/supplement_main.pdf",
            )
            if path.is_file()
        }
        with tempfile.TemporaryDirectory() as tmp:
            report = builder.build_submission_package(Path(tmp), build_pdf=False)
            figures = pd.read_csv(report.figure_manifest)
            tables = pd.read_csv(report.table_manifest)
            self.assertEqual(set(figures["figure_id"]), {
                "F1", "F2", "F3", "F4", "F5", "F6", "F7",
                "SF1", "SF2", "SF3", "SF4", "SF5",
            })
            self.assertEqual(
                set(tables["table_id"]),
                {"T1", "S1", "S2", "S3", "S4", "S5", "S6", "S7"},
            )
            self.assertEqual(report.status, "partial")
            self.assertIsNone(report.main_pdf)
            self.assertIsNone(report.supplement_pdf)
            self.assertEqual(list(Path(tmp).rglob("__pycache__")), [])
            self.assertEqual(list(Path(tmp).rglob("*.pyc")), [])
            for frame in (figures, tables):
                self.assertFalse(frame.astype(str).apply(
                    lambda column: column.str.contains(str(ROOT), regex=False).any()
                ).any())
            for column in ("source_bundle_sha256", "script_sha256", "output_sha256",
                           "manuscript_sha256"):
                self.assertTrue(figures[column].str.fullmatch(HEX64).all(), column)
                self.assertTrue(tables[column].str.fullmatch(HEX64).all(), column)
            self.assertTrue(figures["fresh"].all())
            self.assertTrue(tables["fresh"].all())
            self.assertNotIn("manifest_sha256", figures.columns)
            self.assertNotIn("manifest_sha256", tables.columns)
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
        self.assertEqual(after, before)

    def test_two_temporary_roots_have_identical_declared_artifacts(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = builder.build_submission_package(Path(first), build_pdf=False)
            two = builder.build_submission_package(Path(second), build_pdf=False)
            for left, right in (
                (one.figure_manifest, two.figure_manifest),
                (one.table_manifest, two.table_manifest),
                (one.numeric_mapping, two.numeric_mapping),
                (one.numeric_report, two.numeric_report),
            ):
                self.assertEqual(
                    hashlib.sha256(left.read_bytes()).hexdigest(),
                    hashlib.sha256(right.read_bytes()).hexdigest(),
                    left.name,
                )

    def test_numeric_mapping_is_source_field_based_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = builder.build_submission_package(Path(tmp), build_pdf=False)
            mapping = pd.read_csv(report.numeric_mapping, dtype=str).fillna("")
            self.assertEqual(list(mapping.columns), [
                "claim_id", "source_path", "row_key", "field", "display_format",
                "expected_tex_token", "tex_path", "context_anchor",
            ])
            self.assertFalse(mapping.duplicated().any())
            self.assertTrue(mapping["source_path"].str.endswith((".csv", ".json")).all())
            self.assertFalse(mapping["field"].str.contains("CELLS_CAP|coverage_from").any())
            self.assertTrue({
                "OFFICIAL_PFI_CINDEX", "OFFICIAL_PFI_EVENTS", "COMMON_COHORT_N",
                "RECON_GRADE_DELTA", "NADT_GLEASON_BOOTSTRAPS",
                "STABILITY_TOTAL_CELLS_DESIGN", "SPOP_NULL_STRADDLE_RESULT",
                "MARKER7_NULL_STRADDLE_RESULT",
            }.issubset(set(mapping["claim_id"])))
            qa = pd.read_csv(report.numeric_report)
            self.assertTrue(qa["passed"].all(), qa.to_string(index=False))
            self.assertEqual(len(qa), len(mapping))
            self.assertTrue(mapping["context_anchor"].str.contains(r"{token}", regex=False).all())
            self.assertEqual(mapping["claim_id"].nunique(), len(mapping))
            self.assertEqual(mapping["context_anchor"].nunique(), len(mapping))

    def test_numeric_qa_rejects_duplicate_mapping_anchor_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            self._numeric_stage(stage)
            rows = builder._numeric_rows()
            rows[1]["context_anchor"] = rows[0]["context_anchor"]
            with mock.patch.object(builder, "_numeric_rows", return_value=rows):
                with self.assertRaisesRegex(ValueError, "context_anchor.*unique"):
                    builder.run_numeric_qa(stage)

    @staticmethod
    def _numeric_stage(root: Path) -> Path:
        results = root / "paper/sections/results.tex"
        results.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "projects/prostate_biomarker_validation/paper/sections/results.tex", results)
        builder._generate_numeric_derivations(root)
        return results

    def test_numeric_qa_rejects_context_mutation_even_when_same_token_remains_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            results = self._numeric_stage(stage)
            text = results.read_text(encoding="utf-8")
            self.assertGreaterEqual(text.count("270"), 3)
            mutated, replacements = re.subn(
                r"a fixed\s+270-patient\s+TCGA-PRAD target frame",
                "a fixed TCGA-PRAD target frame of 270 patients",
                text,
                count=1,
            )
            self.assertEqual(replacements, 1)
            results.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "context|occurrence"):
                builder.run_numeric_qa(stage)

    def test_numeric_qa_rejects_unmapped_number_after_geq_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            results = self._numeric_stage(stage)
            with results.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\nThe prespecified primary event threshold was $\\geq42$.\n"
                )
            with self.assertRaisesRegex(ValueError, "coverage.*42"):
                builder.run_numeric_qa(stage)

    def test_numeric_qa_rejects_unmapped_signed_numbers_after_tex_control_words(self):
        hostile_sentences = (
            r"The threshold was $\geq-0.25$.",
            r"The primary p value was $p\leq0.05$.",
            r"The estimate was $\approx0.42$.",
            r"The product shift was $\times-0.25$.",
        )
        for sentence in hostile_sentences:
            with self.subTest(sentence=sentence), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                results = self._numeric_stage(stage)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(f"\n{sentence}\n")
                with self.assertRaisesRegex(ValueError, "coverage"):
                    builder.run_numeric_qa(stage)

    def test_numeric_tokenizer_returns_exact_control_word_and_plain_spans(self):
        text = (
            r"\geq-0.25 \leq  +12 \approx0.42 \times -3/4 "
            r"\sim+1,234.5 p=0.05 $-0.25$ +0.42 8/12"
        )
        expected = [
            (4, 9, "-0.25"),
            (16, 19, "+12"),
            (27, 31, "0.42"),
            (39, 43, "-3/4"),
            (48, 56, "+1,234.5"),
            (59, 63, "0.05"),
            (65, 70, "-0.25"),
            (72, 77, "+0.42"),
            (78, 82, "8/12"),
        ]
        self.assertEqual(builder._numeric_occurrences(text), expected)

    def test_numeric_qa_rejects_broad_hostile_numeric_forms(self):
        hostile_sentences = (
            r"The estimate was $.42$.",
            r"The estimate was $-.42$.",
            r"The estimate was $\approx.42$.",
            r"The estimate was $.2e-3$.",
            r"The interval components were $\frac{.3}{.4}$.",
            r"The estimate was $\foo@bar0.42$.",
            "The fraction was ½.",
        )
        for sentence in hostile_sentences:
            with self.subTest(sentence=sentence), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                results = self._numeric_stage(stage)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(f"\n{sentence}\n")
                with self.assertRaisesRegex(ValueError, "coverage"):
                    builder.run_numeric_qa(stage)

    def test_numeric_tokenizer_handles_broad_literal_span_table(self):
        cases = (
            (".42", [(0, 3, ".42")]),
            ("-.42", [(0, 4, "-.42")]),
            (r"\approx.42", [(7, 10, ".42")]),
            (".2e-3", [(0, 5, ".2e-3")]),
            (r"\frac{.3}{.4}", [(6, 8, ".3"), (10, 12, ".4")]),
            (r"\foo@bar0.42", [(8, 12, "0.42")]),
            ("½", [(0, 1, "½")]),
            ("-0.25--+0.42", [(0, 5, "-0.25"), (7, 12, "+0.42")]),
            (r"\cmd  -1,234.5e+2/.4", [(6, 20, "-1,234.5e+2/.4")]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(builder._numeric_occurrences(text), expected)

    def test_numeric_tokenizer_scans_technical_tex_arguments_without_generic_mask(self):
        text = (
            "A 0.5\n"
            r"\input{generated/table1.tex}" "\n"
            r"\includegraphics[width=0.9\textwidth]{figures/fig2.pdf}" "\n"
            r"\label{fig:marker7}" "\n"
            r"\ref{fig:marker7}" "\n"
            "B .42\n"
        )
        self.assertFalse(hasattr(builder, "_mask_technical_tex_arguments"))
        self.assertFalse(hasattr(builder, "_TECHNICAL_TEX_ARGUMENT"))
        self.assertEqual(builder._numeric_occurrences(text), [
            (2, 5, "0.5"), (28, 29, "1"), (58, 61, "0.9"),
            (84, 85, "2"), (108, 109, "7"), (126, 127, "7"),
            (131, 134, ".42"),
        ])

    def test_numeric_qa_rejects_visible_values_inside_ref_like_syntax(self):
        hostile_sentences = (
            r"The estimate was \ref{0.42}.",
            r"\verb|\ref{0.42}|",
            r"{\let\ref\relax The estimate was \ref{0.42}.}",
        )
        for sentence in hostile_sentences:
            with self.subTest(sentence=sentence), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                results = self._numeric_stage(stage)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(f"\n{sentence}\n")
                with self.assertRaisesRegex(ValueError, "coverage"):
                    builder.run_numeric_qa(stage)

    def test_numeric_qa_rejects_quantitative_sentinel_forms(self):
        hostile_sentences = (
            "The value was ∞.",
            r"The value was $\infty$.",
            "The stage was IV.",
            "The value was -∞.",
            "The value was −∞.",
            r"The value was $\pm\infty$.",
            "The value was NaN.",
            "The value was Inf.",
            "The value was Infinity.",
            "The stage was II.",
            "The stage was III.",
            "The stage was V.",
        )
        for sentence in hostile_sentences:
            with self.subTest(sentence=sentence), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                results = self._numeric_stage(stage)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(f"\n{sentence}\n")
                with self.assertRaisesRegex(ValueError, "coverage"):
                    builder.run_numeric_qa(stage)

    def test_quantitative_sentinel_tokenizer_returns_exact_spans_without_ci(self):
        cases = (
            ("∞", [(0, 1, "∞")]),
            ("-∞", [(0, 2, "-∞")]),
            ("−∞", [(0, 2, "−∞")]),
            (r"\infty", [(0, 6, r"\infty")]),
            (r"\pm\infty", [(0, 9, r"\pm\infty")]),
            ("NaN", [(0, 3, "NaN")]),
            ("Inf", [(0, 3, "Inf")]),
            ("Infinity", [(0, 8, "Infinity")]),
            ("II", [(0, 2, "II")]),
            ("III", [(0, 3, "III")]),
            ("IV", [(0, 2, "IV")]),
            ("V", [(0, 1, "V")]),
            ("CI", []),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(builder._numeric_occurrences(text), expected)

    def test_nonfinite_sentinel_is_case_insensitive_and_scans_tex_wrappers(self):
        cases = (
            ("inf", [(0, 3, "inf")]),
            ("INF", [(0, 3, "INF")]),
            ("infinity", [(0, 8, "infinity")]),
            ("INFINITY", [(0, 8, "INFINITY")]),
            ("nan", [(0, 3, "nan")]),
            ("NAN", [(0, 3, "NAN")]),
            ("Nan", [(0, 3, "Nan")]),
            ("iNf", [(0, 3, "iNf")]),
            (r"\mathrm{inf}", [(8, 11, "inf")]),
            (r"\operatorname{nan}", [(14, 17, "nan")]),
            (r"\texttt{NAN}", [(8, 11, "NAN")]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(builder._numeric_occurrences(text), expected)

    def test_numeric_qa_rejects_case_insensitive_and_tex_wrapped_nonfinite_values(self):
        hostile_values = (
            "inf", "INF", "infinity", "INFINITY", "nan", "NAN", "Nan", "iNf",
            r"\mathrm{inf}", r"\operatorname{nan}", r"\texttt{NAN}",
        )
        for value in hostile_values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                results = self._numeric_stage(stage)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(f"\nThe quantitative result was {value}.\n")
                with self.assertRaisesRegex(ValueError, "coverage"):
                    builder.run_numeric_qa(stage)

    def test_clinical_roman_sentinel_is_case_insensitive_and_keeps_stage_suffix(self):
        cases = (
            ("stage IVB", [(6, 9, "IVB")]),
            ("stage IIIA", [(6, 10, "IIIA")]),
            ("stage iv", [(6, 8, "iv")]),
            (r"stage~\textsc{iv}", [(14, 16, "iv")]),
            ("CI", []),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(builder._numeric_occurrences(text), expected)

    def test_numeric_qa_rejects_case_insensitive_clinical_roman_stages(self):
        hostile_sentences = (
            "The clinical stage was IVB.",
            "The clinical stage was IIIA.",
            "The clinical stage was iv.",
            r"The clinical stage was~\textsc{iv}.",
        )
        for sentence in hostile_sentences:
            with self.subTest(sentence=sentence), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                results = self._numeric_stage(stage)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(f"\n{sentence}\n")
                with self.assertRaisesRegex(ValueError, "coverage"):
                    builder.run_numeric_qa(stage)

    def test_technical_numeric_allowlist_is_exact_and_unique(self):
        expected_ids = {
            "TECH_INPUT_TABLE1", "TECH_FIG1_PATH", "TECH_FIG2_PATH",
            "TECH_FIG3_PATH", "TECH_FIG4_PATH", "TECH_MARKER7_REF_STABILITY",
            "TECH_FIG5_PATH", "TECH_FIG5_MARKER7_PATH", "TECH_MARKER7_LABEL",
            "TECH_FIG6_PATH", "TECH_FIG7_PATH", "TECH_MARKER7_REF_RECURRENCE",
        }
        self.assertTrue(hasattr(builder, "TECHNICAL_NUMERIC_OCCURRENCES"))
        technical = builder.TECHNICAL_NUMERIC_OCCURRENCES
        self.assertEqual({item["occurrence_id"] for item in technical}, expected_ids)
        self.assertEqual(len(technical), 12)
        self.assertEqual(len({item["context_anchor"] for item in technical}), 12)
        text = (ROOT / "projects/prostate_biomarker_validation/paper/sections/results.tex").read_text(encoding="utf-8")
        technical_spans = builder._technical_numeric_spans(text)
        structural_spans = builder._structural_numeric_spans(text)
        parsed = set(builder._numeric_occurrences(text))
        self.assertEqual(len(parsed), 106)
        self.assertEqual(len(technical_spans), 12)
        self.assertEqual(len(structural_spans), 4)
        self.assertFalse(technical_spans & structural_spans)
        self.assertEqual(len(parsed - technical_spans - structural_spans), 90)

    def test_technical_numeric_allowlist_rejects_missing_and_duplicate_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            results = self._numeric_stage(stage)
            text = results.read_text(encoding="utf-8")
            results.write_text(text.replace("table1_qualification", "table9_qualification"),
                               encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "TECH_INPUT_TABLE1.*exactly once"):
                builder.run_numeric_qa(stage)
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            results = self._numeric_stage(stage)
            with results.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\nendpoint-conditioned transfer summary "
                    "(Figure~\\ref{fig:marker7-transfer}), and the decision-level grid summary\n"
                )
            with self.assertRaisesRegex(
                ValueError, "TECH_MARKER7_REF_STABILITY.*exactly once"
            ):
                builder.run_numeric_qa(stage)

    def test_technical_numeric_allowlist_rejects_duplicate_configuration(self):
        self.assertTrue(hasattr(builder, "TECHNICAL_NUMERIC_OCCURRENCES"))
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            self._numeric_stage(stage)
            duplicated = tuple(builder.TECHNICAL_NUMERIC_OCCURRENCES) + (
                dict(builder.TECHNICAL_NUMERIC_OCCURRENCES[0]),
            )
            with mock.patch.object(
                builder, "TECHNICAL_NUMERIC_OCCURRENCES", duplicated
            ):
                with self.assertRaisesRegex(ValueError, "occurrence_id.*unique"):
                    builder.run_numeric_qa(stage)

    def test_numeric_tokenizer_finite_adversarial_table_is_fail_closed(self):
        cases = (
            ("(.42),", [(1, 4, ".42")]),
            ("{-.42}", [(1, 5, "-.42")]),
            ("abc0.42xyz", [(3, 7, "0.42")]),
            ("½", [(0, 1, "½")]),
            ("²³", [(0, 2, "²³")]),
            ("٣", [(0, 1, "٣")]),
            (".2E+3", [(0, 5, ".2E+3")]),
            ("badⅫ", [(3, 4, "Ⅻ")]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                occurrences = builder._numeric_occurrences(text)
                self.assertTrue(occurrences, text)
                self.assertEqual(occurrences, expected)

    def test_structural_numeric_allowlist_is_exact_and_fail_closed(self):
        expected_ids = {
            "STRUCT_ISUP_BENIGN", "STRUCT_ISUP_TUMOR", "STRUCT_R_SQUARED",
            "STRUCT_LEGACY_MARKER7_NAME",
        }
        self.assertTrue(hasattr(builder, "STRUCTURAL_NUMERIC_OCCURRENCES"))
        structural = builder.STRUCTURAL_NUMERIC_OCCURRENCES
        self.assertEqual({item["occurrence_id"] for item in structural}, expected_ids)
        self.assertEqual(len(structural), 4)
        self.assertEqual(len({item["context_anchor"] for item in structural}), 4)
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            results = self._numeric_stage(stage)
            builder.run_numeric_qa(stage)
            text = results.read_text(encoding="utf-8")
            self.assertEqual(len(builder._numeric_occurrences(text)), 106)
            with results.open("a", encoding="utf-8") as handle:
                handle.write("\nThis score is called ``marker 7'' only in legacy analysis artifacts.\n")
            with self.assertRaisesRegex(
                ValueError, "STRUCT_LEGACY_MARKER7_NAME.*exactly once"
            ):
                builder.run_numeric_qa(stage)

    def test_numeric_qa_maps_each_occurrence_to_the_intended_source_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            self._numeric_stage(stage)
            builder.run_numeric_qa(stage)
            mapping = pd.read_csv(stage / "paper/numeric_qa_mapping.csv", dtype=str)
            row = mapping.set_index("claim_id").loc["OFFICIAL_PFI_CINDEX"]
            self.assertEqual(row["row_key"], "semantic_key=E08_official_pfi:frozen_risk:c_index")
            self.assertEqual(row["field"], "primary_estimate")
            source = stage / row["source_path"]
            source.parent.mkdir(parents=True, exist_ok=True)
            frame = pd.read_csv(builder._source_path(row["source_path"]))
            mask = frame["semantic_key"].eq("E08_official_pfi:frozen_risk:c_index")
            frame.loc[mask, "primary_estimate"] = 0.5
            frame.to_csv(source, index=False)
            with self.assertRaisesRegex(ValueError, "OFFICIAL_PFI_CINDEX"):
                builder.run_numeric_qa(stage)

    def test_atomic_publish_removes_partial_new_target_after_copy_failure(self):
        with tempfile.TemporaryDirectory() as stage_tmp, tempfile.TemporaryDirectory() as out_tmp:
            stage, output = Path(stage_tmp), Path(out_tmp)
            source = stage / "paper/new.csv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"complete")
            real_copy2 = shutil.copy2

            def fail_after_partial(src, dst, *args, **kwargs):
                if Path(src) == source:
                    Path(dst).write_bytes(b"partial")
                    raise OSError("injected copy failure")
                return real_copy2(src, dst, *args, **kwargs)

            with mock.patch.object(builder.shutil, "copy2", side_effect=fail_after_partial):
                with self.assertRaisesRegex(OSError, "injected"):
                    builder._transactional_publish(stage, output, repository_run=False)
            self.assertFalse((output / "paper/new.csv").exists())
            self.assertEqual(list((output / "paper").glob(".*publish-*")), [])

    def test_package_status_is_shared_by_actions_report_and_return_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            partial = root / "partial.md"
            partial.write_text(
                "package_status: partial\nblocking: yes\nblocking: yes\n", encoding="utf-8"
            )
            ready = root / "ready.md"
            ready.write_text("package_status: ready\n", encoding="utf-8")
            self.assertEqual(builder.determine_package_status(partial), ("partial", 2))
            self.assertEqual(builder.determine_package_status(ready), ("ready", 0))
            mismatch = root / "mismatch.md"
            mismatch.write_text(
                "package_status: ready\nblocking: yes\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                builder.determine_package_status(mismatch)
            actual = builder.determine_package_status(ROOT / "projects/prostate_biomarker_validation/paper/author_action_items.md")
            self.assertEqual(actual, ("partial", 8))

    def test_table_generator_uses_config_outputs_and_rejects_unknown_id(self):
        from projects.prostate_biomarker_validation.paper.generate_submission_tables import generate_submission_tables
        from projects.prostate_biomarker_validation.paper.submission_config import TABLES
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            custom = replace(TABLES[0], output="paper/generated/config-owned.tex")
            outputs = generate_submission_tables(ROOT, output_root, table_specs=(custom,))
            self.assertEqual(outputs, {"T1": output_root / custom.output})
            self.assertTrue((output_root / custom.output).is_file())
            unknown = replace(custom, table_id="UNKNOWN")
            with self.assertRaisesRegex(ValueError, "unknown table"):
                generate_submission_tables(ROOT, output_root, table_specs=(unknown,))

    def test_table_registry_covers_all_active_submission_tables(self):
        from projects.prostate_biomarker_validation.paper.submission_config import TABLES

        self.assertEqual(
            [spec.table_id for spec in TABLES],
            ["T1", "S1", "S2", "S3", "S4", "S5", "S6", "S7"],
        )
        by_id = {spec.table_id: spec for spec in TABLES}
        self.assertEqual(by_id["S2"].sources, ("resources/projects/prostate_biomarker_validation/model_workspace/revision_global_fdr_summary.csv",))
        self.assertEqual(by_id["S2"].label, "tab:supp-family")
        self.assertEqual(
            by_id["S2"].output, "paper/generated/stable2_multiplicity_family.tex"
        )
        self.assertEqual(by_id["S3"].sources, ("resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv",))
        self.assertEqual(by_id["S3"].label, "tab:supp-stability-summary")
        self.assertEqual(
            by_id["S3"].output, "paper/generated/stable3_stability_summary.tex"
        )
        self.assertEqual(
            by_id["S4"].sources,
            (
                "paper/figure_data/evidence_axis_matrix.csv",
                "paper/claim_evidence_matrix.csv",
            ),
        )
        self.assertEqual(by_id["S4"].label, "tab:supp-evidence-axis-audit")
        self.assertEqual(
            by_id["S4"].output, "paper/generated/stable4_evidence_axis_audit.tex"
        )
        self.assertEqual(
            by_id["S5"].output, "paper/generated/stable5_analysis_frame_inventory.tex"
        )
        self.assertEqual(
            by_id["S6"].sources,
            ("paper/figure_data/fig9_stability_contrasts.csv",),
        )
        self.assertEqual(
            by_id["S7"].sources, ("resources/projects/prostate_biomarker_validation/model_workspace/pfi_endpoint_concordance.csv",)
        )

    def test_evidence_axis_table_requires_complete_source_linked_grid(self):
        from projects.prostate_biomarker_validation.paper.generate_submission_tables import render_evidence_axis_audit

        matrix = pd.read_csv(ROOT / "projects/prostate_biomarker_validation/paper/figure_data/evidence_axis_matrix.csv")
        claims = pd.read_csv(ROOT / "projects/prostate_biomarker_validation/paper/claim_evidence_matrix.csv")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "s4.tex"
            render_evidence_axis_audit(matrix, claims, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn(r"\label{tab:supp-evidence-axis-audit}", text)
            self.assertIn("Grade and phenotype", text)
            self.assertIn("unsupported in frozen design", text)
            self.assertIn("Next evidence needed", text)
            with self.assertRaisesRegex(ValueError, "30 unique"):
                render_evidence_axis_audit(matrix.iloc[:-1], claims, output)
            bad = matrix.copy()
            bad.loc[0, "source_claim_ids"] = "C99"
            with self.assertRaisesRegex(ValueError, "unknown claim"):
                render_evidence_axis_audit(bad, claims, output)

    def test_multiplicity_renderer_requires_exact_schema_keys_and_source_order(self):
        from projects.prostate_biomarker_validation.paper.generate_submission_tables import _display_test, render_multiplicity_family

        source = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/revision_global_fdr_summary.csv")
        expected_columns = (
            "family_member_type", "test", "effect_metric", "effect", "p_value",
            "encoder", "validation_type", "reliability_tier",
            "q_value_BH_FDR_17_tests",
        )
        self.assertEqual(tuple(source.columns), expected_columns)
        expected_keys = list(zip(source["family_member_type"], source["test"]))
        self.assertEqual(len(expected_keys), 17)
        self.assertEqual(len(set(expected_keys)), 17)
        self.assertEqual(
            source["family_member_type"].value_counts().to_dict(),
            {"marker_hypothesis": 13, "nested_refit_confounder_audit": 4},
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "s2.tex"
            render_multiplicity_family(source, output)
            text = output.read_text(encoding="utf-8")
            positions = [text.index(_display_test(test)) for test in source["test"]]
            self.assertEqual(positions, sorted(positions))
            self.assertNotRegex(text, "[①②③④⑤⑥]")
            self.assertIn("9.63\\times10^{-10}", text)
            self.assertIn("\\label{tab:supp-family}", text)

            with self.assertRaisesRegex(ValueError, "schema mismatch"):
                render_multiplicity_family(source.assign(extra="x"), output)
            duplicate = source.copy()
            duplicate.loc[1, ["family_member_type", "test"]] = duplicate.loc[
                0, ["family_member_type", "test"]
            ]
            with self.assertRaisesRegex(ValueError, "exact 17-row key order"):
                render_multiplicity_family(duplicate, output)
            with self.assertRaisesRegex(ValueError, "exact 17-row key order"):
                render_multiplicity_family(source.iloc[::-1].reset_index(drop=True), output)

    def test_stability_renderer_recomputes_exact_six_by_twelve_summary(self):
        from projects.prostate_biomarker_validation.paper.generate_submission_tables import render_stability_summary

        source = pd.read_csv(ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/stability_summary.csv")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "s3.tex"
            render_stability_summary(source, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("\\label{tab:supp-stability-summary}", text)
            labels = ("Gleason", "Phenotype", "PTEN", "AR", "SPOP", "Recurrence risk")
            positions = [text.index(label) for label in labels]
            self.assertEqual(positions, sorted(positions))
            for expected in ("Gleason & 0.271 & 0.646 & 0/12 & 0/12", "SPOP & 0.348 & 0.679 & 8/12 & 9/12", "Recurrence risk & 0.481 & 0.755 & 1/12 & 2/12"):
                self.assertIn(expected, text)

            with self.assertRaisesRegex(ValueError, "schema mismatch"):
                render_stability_summary(source.drop(columns=["n_ties"]), output)
            with self.assertRaisesRegex(ValueError, "12 unique configurations"):
                render_stability_summary(source.iloc[:-1], output)
            altered = source.copy()
            altered.loc[0, "n_seeds"] = 4
            with self.assertRaisesRegex(ValueError, "five seeds"):
                render_stability_summary(altered, output)

    def test_external_skip_pdf_publish_removes_stale_optional_outputs(self):
        with tempfile.TemporaryDirectory() as stage_tmp, tempfile.TemporaryDirectory() as out_tmp:
            stage, output = Path(stage_tmp), Path(out_tmp)
            generated = stage / "paper/report.csv"
            generated.parent.mkdir(parents=True)
            generated.write_text("fresh\n", encoding="utf-8")
            paper = output / "paper"
            paper.mkdir()
            for name in ("main.pdf", "supplement_main.pdf", "main_build.log",
                         "supplement_main_build.log", "main.aux", "main.log", "main.out",
                         "supplement_main.aux", "supplement_main.log", "supplement_main.out"):
                (paper / name).write_text("stale", encoding="utf-8")
            builder._transactional_publish(stage, output, repository_run=False)
            self.assertTrue((paper / "report.csv").is_file())
            for name in ("main.pdf", "supplement_main.pdf", "main_build.log",
                         "supplement_main_build.log", "main.aux", "main.log", "main.out",
                         "supplement_main.aux", "supplement_main.log", "supplement_main.out"):
                self.assertFalse((paper / name).exists())

    def test_external_optional_removal_rolls_back_when_later_copy_fails(self):
        with tempfile.TemporaryDirectory() as stage_tmp, tempfile.TemporaryDirectory() as out_tmp:
            stage, output = Path(stage_tmp), Path(out_tmp)
            source = stage / "paper/report.csv"
            source.parent.mkdir(parents=True)
            source.write_text("new\n", encoding="utf-8")
            paper = output / "paper"
            paper.mkdir()
            stale = paper / "main.pdf"
            stale.write_text("old pdf", encoding="utf-8")
            existing = paper / "report.csv"
            existing.write_text("old report\n", encoding="utf-8")
            real_copy2 = shutil.copy2

            def fail_stage_copy(src, dst, *args, **kwargs):
                if Path(src) == source:
                    Path(dst).write_text("partial", encoding="utf-8")
                    raise OSError("injected copy failure")
                return real_copy2(src, dst, *args, **kwargs)

            with mock.patch.object(builder.shutil, "copy2", side_effect=fail_stage_copy):
                with self.assertRaisesRegex(OSError, "injected"):
                    builder._transactional_publish(stage, output, repository_run=False)
            self.assertEqual(stale.read_text(encoding="utf-8"), "old pdf")
            self.assertEqual(existing.read_text(encoding="utf-8"), "old report\n")

    def test_stale_output_is_rejected_by_manifest_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = builder.build_submission_package(Path(tmp), build_pdf=False)
            manifest = pd.read_csv(report.figure_manifest)
            output = Path(tmp) / manifest.iloc[0]["output_path"]
            source = builder._source_path(manifest.iloc[0]["source_paths"].split(";")[0])
            stale_time = source.stat().st_mtime - 10
            output.touch()
            output.chmod(0o644)
            import os
            os.utime(output, (stale_time, stale_time))
            with self.assertRaisesRegex(ValueError, "stale"):
                builder.validate_manifest_freshness(report.figure_manifest, Path(tmp))

    def test_table_generator_fails_closed_on_missing_semantic_row(self):
        from projects.prostate_biomarker_validation.paper.generate_submission_tables import render_qualification_summary
        source = pd.read_csv(ROOT / "projects/prostate_biomarker_validation/paper/claim_evidence_matrix.csv").iloc[:-1]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "C01--C08"):
                render_qualification_summary(source, Path(tmp) / "table.tex")


if __name__ == "__main__":
    unittest.main()
