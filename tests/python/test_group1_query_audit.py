from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from common.jsonl import read_jsonl
from materials import query_audit_cli
from materials.query_audit import (
    DEFAULT_GROUP1_OUTPUT_ROOT,
    DEFAULT_GROUP1_QUERY_DIR,
    OllamaTemplateEnricher,
    QueryAuditClassificationError,
    QueryIconDecision,
    TemplateDraft,
    TemplateDownloadCandidate,
    TemplatePlan,
    VariantManifestEntry,
    parse_ollama_query_response,
    parse_ollama_template_response,
    run_group1_query_audit,
)


def _write_query_image(path: Path, boxes: list[tuple[int, int, int, int]]) -> None:
    image = Image.new("RGBA", (64, 24), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for x1, y1, x2, y2 in boxes:
        draw.rectangle((x1, y1, x2, y2), fill=(0, 0, 0, 255))
    image.save(path)


class Group1QueryAuditTests(unittest.TestCase):
    def test_query_audit_cli_defaults_to_validation_query_and_pack_output(self) -> None:
        parser = query_audit_cli.build_parser()
        args = parser.parse_args(["--model", "gemma4:26b"])
        self.assertEqual(args.query_dir, DEFAULT_GROUP1_QUERY_DIR)
        self.assertEqual(args.output_root, DEFAULT_GROUP1_OUTPUT_ROOT)
        self.assertIsNone(args.template_report_json)
        self.assertEqual(args.timeout_seconds, 600)
        self.assertEqual(args.report_root.name, "20260411")
        self.assertEqual(
            args.report_root.parent.as_posix(),
            Path.cwd().joinpath("work_home/reports/group1/materials").as_posix(),
        )
        self.assertFalse(args.quiet)

    def test_query_audit_cli_uses_current_directory_as_run_root(self) -> None:
        result = {"status": "ok"}
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            with patch("pathlib.Path.cwd", return_value=work_dir):
                with patch("materials.query_audit_cli.run_group1_query_audit", return_value=result) as audit:
                    code = query_audit_cli.main(
                        [
                            "--model",
                            "gemma4:26b",
                            "--query-dir",
                            "/tmp/query",
                            "--output-root",
                            "/tmp/output",
                            "--report-root",
                            "/tmp/report",
                            "--cache-dir",
                            "/tmp/cache",
                        ]
                    )

        self.assertEqual(code, 0)
        self.assertEqual(audit.call_args.kwargs["repo_root"], work_dir.resolve())

    def test_query_audit_cli_requires_confirmation_for_default_paths_in_noninteractive_mode(self) -> None:
        buffer = io.StringIO()
        with patch("sys.stdin.isatty", return_value=False):
            with redirect_stderr(buffer):
                with self.assertRaises(SystemExit) as exc:
                    query_audit_cli.main(["--model", "gemma4:26b"])
        self.assertEqual(exc.exception.code, 2)
        self.assertIn("以下路径未显式指定", buffer.getvalue())
        self.assertIn("添加 --yes 接受默认路径", buffer.getvalue())

    def test_query_audit_cli_yes_accepts_default_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            audit = Mock(return_value={"status": "ok"})
            with patch("pathlib.Path.cwd", return_value=work_dir):
                with patch("materials.query_audit_cli.run_group1_query_audit", audit):
                    code = query_audit_cli.main(["--model", "gemma4:26b", "--yes"])

        self.assertEqual(code, 0)
        self.assertEqual(audit.call_args.kwargs["repo_root"], work_dir.resolve())
        self.assertEqual(audit.call_args.kwargs["query_dir"], DEFAULT_GROUP1_QUERY_DIR)

    def test_parse_ollama_query_response_normalizes_template_ids_and_tags(self) -> None:
        icons = parse_ollama_query_response(
            """
            {
              "icons": [
                {
                  "order": 2,
                  "template_id": "shopping cart",
                  "zh_name": "购物车",
                  "family": "Commerce",
                  "tags": "shopping, cart / trolley",
                  "description": "线框购物车",
                  "reason": "常见购物车图标"
                },
                {
                  "order": 1,
                  "template_id": "tpl_house",
                  "zh_name": "房子",
                  "family": "symbol",
                  "tags": ["home", "house"],
                  "description": "房屋外轮廓",
                  "reason": "房子图标"
                }
              ]
            }
            """
        )

        self.assertEqual([icon.template_id for icon in icons], ["tpl_house", "tpl_shopping_cart"])
        self.assertEqual(icons[1].tags, ("shopping", "cart", "trolley"))
        self.assertEqual(icons[1].family, "commerce")

    def test_parse_ollama_template_response_normalizes_library_aliases(self) -> None:
        plans = parse_ollama_template_response(
            """
            {
              "templates": [
                {
                  "template_id": "house",
                  "zh_name": "房子",
                  "family": "symbol",
                  "tags": ["home", "house"],
                  "description": "房屋轮廓",
                  "target_variant_count": 5,
                  "download_candidates": [
                    {"library": "tabler-outline", "slug": "home"},
                    {"library": "google-material", "slug": "house"}
                  ]
                }
              ]
            }
            """,
            drafts=[
                type(
                    "Draft",
                    (),
                    {
                        "template_id": "tpl_house",
                    },
                )(),
            ],
        )

        self.assertEqual(plans[0].template_id, "tpl_house")
        self.assertEqual(plans[0].target_variant_count, 5)
        self.assertEqual(plans[0].download_candidates[0].library, "tabler_outline")
        self.assertEqual(plans[0].download_candidates[1].library, "google_material")

    def test_ollama_template_enricher_wraps_timeout_with_request_context(self) -> None:
        draft = TemplateDraft(
            template_id="tpl_house",
            cluster_ids=("cluster_001",),
            zh_name_hints=("房子",),
            family_hints=("symbol",),
            tag_hints=("home",),
            descriptions=("房屋轮廓",),
            member_count=1,
        )
        enricher = OllamaTemplateEnricher(model="gemma4:26b", timeout_seconds=600)

        with patch("materials.query_audit._post_json", side_effect=TimeoutError("timed out")):
            with self.assertRaises(QueryAuditClassificationError) as exc:
                enricher([draft])

        self.assertIn("timed out", str(exc.exception))
        self.assertIsNotNone(exc.exception.request_payload)
        assert exc.exception.request_payload is not None
        self.assertEqual(exc.exception.request_payload["timeout_seconds"], 600)
        self.assertEqual(exc.exception.request_payload["template_count"], 1)

    def test_run_group1_query_audit_writes_tpl_pack_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "work_home/materials/validation/group1/query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18), (38, 2, 44, 22)])
            _write_query_image(query_dir / "b.png", [(4, 6, 16, 18)])

            output_root = repo_root / "work_home/materials/incoming/group1_icon_pack"
            (output_root / "manifests").mkdir(parents=True, exist_ok=True)
            (output_root / "manifests/group1.classes.yaml").write_text("legacy: true\n", encoding="utf-8")

            def fake_classifier(image_path: Path) -> tuple[QueryIconDecision, ...]:
                if image_path.name == "a.png":
                    return (
                        QueryIconDecision(
                            order=1,
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home", "house"),
                            description="房屋外轮廓",
                            reason="房子",
                        ),
                        QueryIconDecision(
                            order=2,
                            template_id="tpl_star",
                            zh_name="星星",
                            family="symbol",
                            tags=("star", "favorite"),
                            description="五角星图标",
                            reason="星形",
                        ),
                    )
                return (
                    QueryIconDecision(
                        order=1,
                        template_id="tpl_house",
                        zh_name="房子",
                        family="symbol",
                        tags=("home", "house"),
                        description="房屋外轮廓",
                        reason="房子",
                    ),
                )

            def fake_enricher(drafts: list[object]) -> tuple[TemplatePlan, ...]:
                return (
                    TemplatePlan(
                        template_id="tpl_house",
                        zh_name="房子",
                        family="symbol",
                        tags=("home", "house"),
                        description="房屋外轮廓图标",
                        cluster_ids=("cluster_001",),
                        target_variant_count=4,
                        download_candidates=(
                            TemplateDownloadCandidate("lucide", "house", "outline"),
                            TemplateDownloadCandidate("bootstrap", "house", "glyph"),
                        ),
                    ),
                    TemplatePlan(
                        template_id="tpl_star",
                        zh_name="星星",
                        family="symbol",
                        tags=("star", "favorite"),
                        description="五角星图标",
                        cluster_ids=("cluster_002",),
                        target_variant_count=3,
                        download_candidates=(
                            TemplateDownloadCandidate("lucide", "star", "outline"),
                            TemplateDownloadCandidate("bootstrap", "star", "glyph"),
                        ),
                    ),
                )

            def fake_downloads(**kwargs: object) -> list[VariantManifestEntry]:
                target_dir = kwargs["target_dir"]
                min_variants = int(kwargs["min_variants_per_template"])
                existing_variant_ids = set(kwargs["existing_variant_ids"])
                created: list[VariantManifestEntry] = []
                while len(existing_variant_ids) + len(created) < min_variants:
                    index = len(existing_variant_ids) + len(created) + 1
                    variant_id = f"var_boot_fake_icon_{chr(ord('a') + index - 1)}"
                    img = Image.new("RGBA", (24, 24), (255, 255, 255, 0))
                    ImageDraw.Draw(img).ellipse((4, 4, 20, 20), fill=(0, 0, 0, 255))
                    img.save(Path(target_dir) / f"{variant_id}.png")
                    created.append(
                        VariantManifestEntry(
                            variant_id=variant_id,
                            source="fake_library",
                            source_ref=f"fake_{index:02d}",
                            style="outline",
                        )
                    )
                return created

            with patch("materials.query_audit._download_template_variants", side_effect=fake_downloads):
                result = run_group1_query_audit(
                    query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=output_root,
                    report_root=repo_root / "work_home/reports/group1/materials/20260411",
                    repo_root=repo_root,
                    min_variants_per_template=3,
                    image_classifier=fake_classifier,
                    template_enricher=fake_enricher,
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["template_count"], 2)
            self.assertEqual(result["generated_variant_count"], 7)
            self.assertFalse((output_root / "manifests/group1.classes.yaml").exists())

            manifest_text = (output_root / "manifests/group1.templates.yaml").read_text(encoding="utf-8")
            self.assertIn("template_id: tpl_house", manifest_text)

            house_files = sorted(path.stem for path in (output_root / "group1/icons/tpl_house").glob("*.png"))
            star_files = sorted(path.stem for path in (output_root / "group1/icons/tpl_star").glob("*.png"))
            self.assertTrue(any(name.startswith("var_real_house_") for name in house_files))
            self.assertTrue(any(name.startswith("var_real_star_") for name in star_files))
            self.assertTrue(any(name.startswith("var_boot_fake_icon_") for name in house_files))
            self.assertTrue(all(len(name) <= 30 for name in (*house_files, *star_files)))
            self.assertFalse(any(name.endswith("_01") or name.endswith("_02") for name in (*house_files, *star_files)))

            rows = read_jsonl(repo_root / "work_home/reports/group1/materials/20260411/group1-query-audit.jsonl")
            self.assertEqual(rows[0]["template_sequence"], ["tpl_house", "tpl_star"])
            self.assertEqual(rows[1]["template_sequence"], ["tpl_house"])

            template_report = json.loads(
                (
                    repo_root / "work_home/reports/group1/materials/20260411/group1-query-audit-templates.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(template_report["template_count"], 2)
            self.assertEqual(template_report["templates"][0]["template_id"], "tpl_house")
            self.assertIn("target_variant_count", template_report["templates"][0])

    def test_run_group1_query_audit_dry_run_keeps_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18)])

            output_root = repo_root / "work_home/materials/incoming/group1_icon_pack"
            original_output = output_root.exists()

            result = run_group1_query_audit(
                query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=output_root,
                    report_root=repo_root / "work_home/reports/group1/materials/20260411",
                    repo_root=repo_root,
                    dry_run=True,
                image_classifier=lambda _image_path: (
                    QueryIconDecision(
                        order=1,
                        template_id="tpl_house",
                        zh_name="房子",
                        family="symbol",
                        tags=("home",),
                        description="房屋轮廓",
                        reason="房子",
                    ),
                ),
                template_enricher=lambda _drafts: (
                    TemplatePlan(
                        template_id="tpl_house",
                        zh_name="房子",
                        family="symbol",
                        tags=("home",),
                        description="房屋轮廓",
                        cluster_ids=("cluster_001",),
                        target_variant_count=3,
                        download_candidates=(),
                    ),
                ),
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(output_root.exists(), original_output)
            self.assertFalse((repo_root / "work_home/reports/group1/materials/20260411/group1-query-audit.jsonl").exists())

    def test_run_group1_query_audit_reports_terminal_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18)])

            messages: list[str] = []

            with patch(
                "materials.query_audit._download_template_variants",
                return_value=[
                    VariantManifestEntry(
                        variant_id="var_boot_house_outline",
                        source="fake_library",
                        source_ref="fake",
                        style="outline",
                    )
                ],
            ):
                run_group1_query_audit(
                    query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=repo_root / "work_home/materials/incoming/group1_icon_pack",
                    report_root=repo_root / "work_home/reports/group1/materials/20260411",
                    repo_root=repo_root,
                    min_variants_per_template=2,
                    progress_reporter=messages.append,
                    image_classifier=lambda image_path: (
                        QueryIconDecision(
                            order=1,
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home",),
                            description="房屋轮廓",
                            reason=str(image_path.name),
                        ),
                    ),
                    template_enricher=lambda _drafts: (
                        TemplatePlan(
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home",),
                            description="房屋轮廓",
                            cluster_ids=("cluster_001",),
                            target_variant_count=2,
                            download_candidates=(),
                        ),
                    ),
                )

            joined = "\n".join(messages)
            self.assertIn("开始执行 group1 query 审计并生成模板素材", joined)
            self.assertIn("正在分析 query 图片 1/1", joined)
            self.assertIn("query 图片处理完成 1/1", joined)
            self.assertIn("执行完成", joined)

    def test_run_group1_query_audit_marks_error_when_variants_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18)])

            with patch("materials.query_audit._download_template_variants", return_value=[]):
                result = run_group1_query_audit(
                    query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=repo_root / "work_home/materials/incoming/group1_icon_pack",
                    report_root=repo_root / "work_home/reports/group1/materials/20260411",
                    repo_root=repo_root,
                    min_variants_per_template=2,
                    image_classifier=lambda _image_path: (
                        QueryIconDecision(
                            order=1,
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home",),
                            description="房屋轮廓",
                            reason="house",
                        ),
                    ),
                    template_enricher=lambda _drafts: (
                        TemplatePlan(
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home",),
                            description="房屋轮廓",
                            cluster_ids=("cluster_001",),
                            target_variant_count=2,
                            download_candidates=(),
                        ),
                    ),
                )

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["insufficient_templates"], ["tpl_house"])

    def test_run_group1_query_audit_partial_success_still_writes_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18)])
            circle = Image.new("RGBA", (64, 24), (255, 255, 255, 255))
            ImageDraw.Draw(circle).ellipse((20, 2, 40, 22), fill=(0, 0, 0, 255))
            circle.save(query_dir / "b.png")

            def fake_classifier(image_path: Path) -> tuple[QueryIconDecision, ...]:
                if image_path.name == "b.png":
                    raise QueryAuditClassificationError("mock classification failure")
                return (
                    QueryIconDecision(
                        order=1,
                        template_id="tpl_house",
                        zh_name="房子",
                        family="symbol",
                        tags=("home",),
                        description="房屋轮廓",
                        reason="house",
                    ),
                )

            with patch(
                "materials.query_audit._download_template_variants",
                return_value=[
                    VariantManifestEntry(
                        variant_id="var_boot_house_outline",
                        source="fake_library",
                        source_ref="fake",
                        style="outline",
                    )
                ],
            ):
                result = run_group1_query_audit(
                    query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=repo_root / "work_home/materials/incoming/group1_icon_pack",
                    report_root=repo_root / "work_home/reports/group1/materials/20260411",
                    repo_root=repo_root,
                    min_variants_per_template=2,
                    image_classifier=fake_classifier,
                    template_enricher=lambda _drafts: (
                        TemplatePlan(
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home",),
                            description="房屋轮廓",
                            cluster_ids=("cluster_001",),
                            target_variant_count=2,
                            download_candidates=(),
                        ),
                    ),
                )

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_count"], 1)
            self.assertEqual(result["template_count"], 1)
            self.assertEqual(result["generated_variant_count"], 2)
            self.assertTrue(
                (repo_root / "work_home/materials/incoming/group1_icon_pack/manifests/group1.templates.yaml").exists()
            )
            self.assertTrue(
                any(
                    path.name.startswith("var_real_house_")
                    for path in (
                        repo_root / "work_home/materials/incoming/group1_icon_pack/group1/icons/tpl_house"
                    ).glob("*.png")
                )
            )

            rows = read_jsonl(repo_root / "work_home/reports/group1/materials/20260411/group1-query-audit.jsonl")
            self.assertEqual([row["status"] for row in rows], ["ok", "error"])

    def test_run_group1_query_audit_retry_from_report_reuses_success_and_retries_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18)])
            circle = Image.new("RGBA", (64, 24), (255, 255, 255, 255))
            ImageDraw.Draw(circle).ellipse((20, 2, 40, 22), fill=(0, 0, 0, 255))
            circle.save(query_dir / "b.png")

            retry_report = repo_root / "previous-group1-query-audit.jsonl"
            retry_report.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "image_path": "query/a.png",
                                "status": "ok",
                                "error": None,
                                "request_payload": None,
                                "template_sequence": ["tpl_house"],
                                "icons": [
                                    {
                                        "order": 1,
                                        "template_id": "tpl_house",
                                        "zh_name": "房子",
                                        "family": "symbol",
                                        "tags": ["home"],
                                        "description": "房屋轮廓",
                                        "reason": "house",
                                        "cluster_id": "cluster_001",
                                    }
                                ],
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "image_path": "query/b.png",
                                "status": "error",
                                "error": "mock classification failure",
                                "request_payload": None,
                                "template_sequence": [],
                                "icons": [],
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            classifier_calls: list[str] = []

            def fake_classifier(image_path: Path) -> tuple[QueryIconDecision, ...]:
                classifier_calls.append(image_path.name)
                if image_path.name == "a.png":
                    raise AssertionError("success row should have been reused from retry report")
                return (
                    QueryIconDecision(
                        order=1,
                        template_id="tpl_star",
                        zh_name="星星",
                        family="symbol",
                        tags=("star",),
                        description="五角星",
                        reason="star",
                    ),
                )

            with patch("materials.query_audit._download_template_variants", return_value=[]):
                result = run_group1_query_audit(
                    query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=repo_root / "work_home/materials/incoming/group1_icon_pack",
                    report_root=repo_root / "work_home/reports/group1/materials/20260411",
                    repo_root=repo_root,
                    retry_from_report=retry_report,
                    min_variants_per_template=1,
                    max_hamming_distance=0,
                    image_classifier=fake_classifier,
                    template_enricher=lambda _drafts: (
                        TemplatePlan(
                            template_id="tpl_house",
                            zh_name="房子",
                            family="symbol",
                            tags=("home",),
                            description="房屋轮廓",
                            cluster_ids=("cluster_001",),
                            target_variant_count=1,
                            download_candidates=(),
                        ),
                        TemplatePlan(
                            template_id="tpl_star",
                            zh_name="星星",
                            family="symbol",
                            tags=("star",),
                            description="五角星",
                            cluster_ids=("cluster_002",),
                            target_variant_count=1,
                            download_candidates=(),
                        ),
                    ),
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["template_count"], 2)
            self.assertEqual(result["generated_variant_count"], 2)
            self.assertEqual(classifier_calls, ["b.png"])

            rows = read_jsonl(repo_root / "work_home/reports/group1/materials/20260411/group1-query-audit.jsonl")
            self.assertEqual([row["status"] for row in rows], ["ok", "ok"])
            self.assertEqual(rows[0]["template_sequence"], ["tpl_house"])
            self.assertEqual(rows[1]["template_sequence"], ["tpl_star"])

    def test_run_group1_query_audit_checkpoints_each_image_before_later_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            _write_query_image(query_dir / "a.png", [(4, 6, 16, 18)])
            _write_query_image(query_dir / "b.png", [(24, 6, 36, 18)])

            classifier_calls: list[str] = []

            def fake_classifier(image_path: Path) -> tuple[QueryIconDecision, ...]:
                classifier_calls.append(image_path.name)
                if image_path.name == "b.png":
                    raise KeyboardInterrupt("simulate interrupted long request")
                return (
                    QueryIconDecision(
                        order=1,
                        template_id="tpl_house",
                        zh_name="房子",
                        family="symbol",
                        tags=("home",),
                        description="房屋轮廓",
                        reason="house",
                    ),
                )

            report_root = repo_root / "work_home/reports/group1/materials/20260411"
            with self.assertRaises(KeyboardInterrupt):
                run_group1_query_audit(
                    query_dir=query_dir,
                    model="gemma4:26b",
                    output_root=repo_root / "work_home/materials/incoming/group1_icon_pack",
                    report_root=report_root,
                    repo_root=repo_root,
                    min_variants_per_template=1,
                    max_hamming_distance=0,
                    image_classifier=fake_classifier,
                    template_enricher=lambda _drafts: (),
                )

            self.assertEqual(classifier_calls, ["a.png", "b.png"])
            rows = read_jsonl(report_root / "group1-query-audit.jsonl")
            trace_rows = read_jsonl(report_root / "group1-query-audit-trace.jsonl")
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(trace_rows), 1)
            self.assertEqual(rows[0]["status"], "ok")
            self.assertEqual(rows[0]["image_path"], "query/a.png")


if __name__ == "__main__":
    unittest.main()
