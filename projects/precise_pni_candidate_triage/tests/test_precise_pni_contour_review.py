import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from projects.precise_pni_candidate_triage.code.contour_review.build_precise_pni_contour_review import (
    build_case_manifest,
    build_contour_html,
    build_status_template,
    locator_feature_collection,
    validate_case_annotations,
    validate_submission,
)


def fixture_inputs():
    mapping = pd.DataFrame({
        "temporary_id": ["MORPH-001", "MORPH-002"],
        "candidate_id": ["C-1", "C-2"],
        "subject_id": ["sub-1", "sub-2"],
        "image_id": ["sub-1_ses-1", "sub-2_ses-1"],
        "x0": [100, 200], "y0": [300, 400], "window_px": [120, 120],
        "window_um": [300.0, 300.0],
    })
    locked = pd.DataFrame({
        "temporary_id": ["MORPH-001", "MORPH-002"],
        "pni_status": ["definite", "probable"],
        "overall_relation": ["touching", "touching"],
        "nerve_multiplicity": ["single", "single"],
    })
    eligibility = pd.DataFrame({
        "temporary_id": ["MORPH-001", "MORPH-002"],
        "contour_disposition": ["eligible_for_contouring", "adjudication_required"],
        "unresolved_morphology_fields": ["", ""],
    })
    wsi = pd.DataFrame({
        "image_id": ["sub-1_ses-1", "sub-2_ses-1"],
        "wsi_path": ["/data/one.ome.tif", "/data/two.ome.tif"],
        "wsi_sha256": ["a" * 64, "b" * 64],
        "width_px": [1000, 1000], "height_px": [1000, 1000],
        "mpp_x": [0.25, 0.25], "mpp_y": [0.25, 0.25],
    })
    return mapping, locked, eligibility, wsi


def feature(annotation_id, object_type, geometry, object_role="related",
            parent_annotation_id=""):
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "annotation_id": annotation_id,
            "temporary_id": "MORPH-001",
            "object_type": object_type,
            "object_role": object_role,
            "parent_annotation_id": parent_annotation_id,
            "reviewer_id": "Song",
            "review_stage": "primary_contour",
            "evidence_mode": "H&E_only",
            "source": "pathologist_drawn",
            "approval_status": "approved",
            "contour_completeness": "complete",
            "revision_number": 1,
            "reviewer_notes": "",
        },
    }


class ManifestTests(unittest.TestCase):
    def test_manifest_reconciles_inputs_and_separates_primary_from_adjudication(self):
        mapping, locked, eligibility, wsi = fixture_inputs()
        manifest = build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2)
        self.assertEqual(manifest.review_stream.tolist(), ["primary_contour", "adjudication"])
        self.assertEqual(manifest.locator_center_x.tolist(), [160, 260])
        self.assertEqual(manifest.locator_center_y.tolist(), [360, 460])
        self.assertEqual(manifest.wsi_sha256.tolist(), ["a" * 64, "b" * 64])

    def test_manifest_rejects_duplicate_or_unreconciled_ids(self):
        mapping, locked, eligibility, wsi = fixture_inputs()
        mapping.loc[1, "candidate_id"] = "C-1"
        with self.assertRaisesRegex(ValueError, "duplicate candidate"):
            build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2)
        mapping, locked, eligibility, wsi = fixture_inputs()
        eligibility.loc[1, "temporary_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "ID sets"):
            build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2)

    def test_locator_geojson_is_private_label_blind_and_explicitly_not_a_contour(self):
        mapping, locked, eligibility, wsi = fixture_inputs()
        row = build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2).iloc[0]
        collection = locator_feature_collection(row)
        item = collection["features"][0]
        self.assertEqual(item["geometry"], {"type": "Point", "coordinates": [160.0, 360.0]})
        self.assertTrue(item["properties"]["locator_only"])
        serialized = str(collection)
        for prohibited in ["candidate_id", "image_id", "pni_status", "combined_score", "rank", "stratum"]:
            self.assertNotIn(prohibited, serialized)

    def test_status_template_preserves_pending_and_adjudication_state(self):
        mapping, locked, eligibility, wsi = fixture_inputs()
        manifest = build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2)
        status = build_status_template(manifest)
        self.assertEqual(status.contour_status.tolist(), ["pending", "pending"])
        self.assertEqual(status.adjudication_required.tolist(), ["no", "yes"])
        self.assertTrue(status.reviewer_id.eq("").all())

    def test_html_explains_roadmap_and_supports_contour_exports_without_private_ids(self):
        cases = [{
            "temporary_id": "MORPH-001",
            "review_stream": "primary_contour",
            "locked_pni_status": "definite",
            "locked_overall_relation": "touching",
            "nerve_multiplicity": "single",
            "unresolved_morphology_fields": "",
            "contour_task": "nerve_tumor_interface",
            "wsi_width": 1000,
            "wsi_height": 1000,
            "locator_center_x": 160.0,
            "locator_center_y": 360.0,
            "views": {
                "300": {"uri": "data:image/jpeg;base64,AAA", "x0": 100,
                        "y0": 300, "size": 120},
                "600": {"uri": "data:image/jpeg;base64,BBB", "x0": 40,
                        "y0": 240, "size": 240},
                "1200": {"uri": "data:image/jpeg;base64,CCC", "x0": -80,
                         "y0": 120, "size": 480},
            },
        }]
        html = build_contour_html(cases)
        for required in ["프로젝트의 최종 목표", "현재 위치", "M6", "nerve_outer_boundary",
                         "GeoJSON", "JSON 백업", "상태 CSV", "localStorage",
                         'coordinate_system:"H&E_WSI_level0_pixels_origin_top_left"']:
            self.assertIn(required, html)
        for private in ["C-1", "sub-1_ses-1", "combined_score", "selection_stratum"]:
            self.assertNotIn(private, html)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for JavaScript syntax check")
    def test_html_javascript_is_syntactically_valid(self):
        html = build_contour_html([])
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            script_path = Path(directory) / "contour-review.js"
            script_path.write_text(script, encoding="utf-8")
            result = subprocess.run(
                [shutil.which("node"), "--check", str(script_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


class GeometryValidationTests(unittest.TestCase):
    def setUp(self):
        mapping, locked, eligibility, wsi = fixture_inputs()
        self.row = build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2).iloc[0]
        self.status = build_status_template(
            build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2)
        ).iloc[0].copy()
        self.status["contour_status"] = "complete"
        self.status["approval_status"] = "approved"
        self.status["index_nerve_annotation_id"] = "MORPH-001-nerve_outer_boundary-001"
        self.status["required_object_completeness"] = "complete"
        self.status["reviewer_id"] = "Song"
        self.status["revision_number"] = "1"
        self.status["review_timestamp_utc"] = "2026-08-11T12:00:00+00:00"

    def valid_collection(self):
        nerve = feature(
            "MORPH-001-nerve_outer_boundary-001", "nerve_outer_boundary",
            {"type": "Polygon", "coordinates": [[[100, 100], [150, 100], [150, 150],
                                                        [100, 150], [100, 100]]]},
            object_role="index",
        )
        tumor = feature(
            "MORPH-001-tumor_boundary-001", "tumor_boundary",
            {"type": "Polygon", "coordinates": [[[150, 100], [180, 100], [180, 150],
                                                        [150, 150], [150, 100]]]},
        )
        contact = feature(
            "MORPH-001-contact_segment-001", "contact_segment",
            {"type": "LineString", "coordinates": [[150, 100], [150, 150]]},
            parent_annotation_id="MORPH-001-nerve_outer_boundary-001",
        )
        return {"type": "FeatureCollection", "features": [nerve, tumor, contact]}

    def test_valid_definite_touching_case_passes(self):
        issues = validate_case_annotations(self.valid_collection(), self.row, self.status)
        self.assertEqual(issues, [])

    def test_validator_flags_self_intersection_out_of_bounds_and_bad_parent(self):
        collection = self.valid_collection()
        collection["features"][0]["geometry"]["coordinates"] = [
            [[100, 100], [160, 160], [100, 160], [160, 100], [100, 100]]
        ]
        collection["features"][1]["geometry"]["coordinates"][0][1][0] = 1001
        collection["features"][2]["properties"]["parent_annotation_id"] = "MISSING"
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("self_intersection", codes)
        self.assertIn("coordinate_out_of_bounds", codes)
        self.assertIn("unknown_parent_annotation", codes)

    def test_validator_requires_objects_without_inventing_negative_annotations(self):
        collection = self.valid_collection()
        collection["features"] = collection["features"][:1]
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("missing_tumor_boundary", codes)
        self.assertIn("missing_contact_segment", codes)
        self.assertNotIn("missing_encasement_arc", codes)

    def test_contact_segment_must_reference_and_follow_a_nerve_boundary(self):
        collection = self.valid_collection()
        collection["features"][2]["geometry"]["coordinates"] = [[200, 100], [200, 150]]
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("contact_not_on_nerve_boundary", codes)

        collection = self.valid_collection()
        collection["features"][2]["properties"]["parent_annotation_id"] = (
            "MORPH-001-tumor_boundary-001"
        )
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("contact_parent_not_nerve", codes)

        collection = self.valid_collection()
        collection["features"][2]["properties"]["parent_annotation_id"] = ""
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("missing_interface_parent", codes)

    def test_interface_line_is_checked_between_vertices_in_micrometers(self):
        collection = self.valid_collection()
        collection["features"][2]["geometry"]["coordinates"] = [[100, 100], [150, 150]]
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("contact_not_on_nerve_boundary", codes)

    def test_wsi_bounds_use_half_open_level_zero_pixel_extent(self):
        collection = self.valid_collection()
        collection["features"][1]["geometry"]["coordinates"][0][1][0] = 1000
        codes = {issue["issue_code"] for issue in
                 validate_case_annotations(collection, self.row, self.status)}
        self.assertIn("coordinate_out_of_bounds", codes)

    def test_combined_html_geojson_export_is_accepted(self):
        mapping, locked, eligibility, wsi = fixture_inputs()
        manifest = build_case_manifest(mapping, locked, eligibility, wsi, expected_count=2)
        status = build_status_template(manifest)
        status.loc[status.temporary_id.eq("MORPH-001"), [
            "index_nerve_annotation_id", "required_object_completeness", "contour_status",
            "approval_status", "reviewer_id", "revision_number", "review_timestamp_utc",
        ]] = [
            "MORPH-001-nerve_outer_boundary-001", "complete", "complete", "approved",
            "Song", "1", "2026-08-11T12:00:00+00:00",
        ]
        collection = self.valid_collection()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            geojson = root / "precise_pni_contours_combined.geojson"
            manifest_path = root / "manifest.csv"
            status_path = root / "status.csv"
            geojson.write_text(json.dumps(collection), encoding="utf-8")
            manifest.to_csv(manifest_path, index=False)
            status.to_csv(status_path, index=False)
            issues = validate_submission(geojson, status_path, manifest_path)
            self.assertTrue(issues.empty, issues.to_string(index=False))
            loaded = json.loads(geojson.read_text(encoding="utf-8"))
            self.assertEqual(loaded, collection)
            mpp_x = float(manifest.iloc[0].mpp_x)
            mpp_y = float(manifest.iloc[0].mpp_y)
            for feature_item in loaded["features"]:
                geometry = feature_item["geometry"]
                points = (geometry["coordinates"][0] if geometry["type"] == "Polygon"
                          else geometry["coordinates"])
                for x, y in points:
                    self.assertAlmostEqual((x * mpp_x) / mpp_x, x)
                    self.assertAlmostEqual((y * mpp_y) / mpp_y, y)


if __name__ == "__main__":
    unittest.main()
