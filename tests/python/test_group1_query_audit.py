from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr
import io
from pathlib import Path
from unittest.mock import patch

from core.common.jsonl import read_jsonl
from core.materials import query_audit_cli
from core.materials.query_audit import (
    DEFAULT_GROUP1_AUDIT_TRACE,
    DEFAULT_GROUP1_QUERY_DIR,
    QueryAuditClassificationError,
    QueryImageClassification,
    QueryIconDecision,
    parse_ollama_icon_response,
    require_repo_root,
    run_group1_query_audit,
)


BACKLOG_TEMPLATE = """# 训练者角色：`group1` 素材类别补齐清单

## 3. 待补齐的新类别

| 建议类别名 | 中文名 | 图形描述 | 不要混到哪些旧类 | 样本状态 | 备注 |
| --- | --- | --- | --- | --- | --- |

## 3.1 已确认可直接归到现有素材类的案例

| 截图批次 | 图标描述 | 归属现有类 | 备注 |
| --- | --- | --- | --- |

## 4. 类别判定边界
"""


MANIFEST_TEMPLATE = """classes:
  - id: 0
    name: icon_plane
    zh_name: 飞机
  - id: 1
    name: icon_gift
    zh_name: 礼物
"""


class Group1QueryAuditTests(unittest.TestCase):
    def test_query_audit_cli_defaults_to_materials_test_group1_query(self) -> None:
        parser = query_audit_cli.build_parser()
        args = parser.parse_args(["--model", "qwen2.5vl:7b"])
        self.assertEqual(args.query_dir, DEFAULT_GROUP1_QUERY_DIR)
        self.assertEqual(args.trace_jsonl, DEFAULT_GROUP1_AUDIT_TRACE)
        self.assertFalse(args.quiet)

    def test_query_audit_cli_prints_clean_error_outside_repo_root(self) -> None:
        buffer = io.StringIO()
        with patch("core.materials.query_audit_cli.require_repo_root", side_effect=FileNotFoundError("请到仓库根目录执行")):
            with redirect_stderr(buffer):
                with self.assertRaises(SystemExit) as exc:
                    query_audit_cli.main(["--model", "qwen2.5vl:7b"])
        self.assertEqual(exc.exception.code, 2)
        self.assertIn("请到仓库根目录执行", buffer.getvalue())

    def test_require_repo_root_rejects_solver_subdirectory(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "请到仓库根目录执行"):
            require_repo_root(Path(__file__).resolve().parents[2] / "solver")

    def test_require_repo_root_accepts_repo_root(self) -> None:
        expected_repo_root = Path(__file__).resolve().parents[2]
        self.assertEqual(require_repo_root(expected_repo_root), expected_repo_root)

    def test_run_group1_query_audit_resolves_default_query_dir_from_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "materials/test/group1/query"
            query_dir.mkdir(parents=True, exist_ok=True)
            (query_dir / "a.png").write_bytes(b"a")

            backlog_doc = repo_root / "docs/02-user-guide/group1-material-category-backlog.md"
            backlog_doc.parent.mkdir(parents=True, exist_ok=True)
            backlog_doc.write_text(BACKLOG_TEMPLATE, encoding="utf-8")

            manifest_path = repo_root / "materials/incoming/group1_icon_pack/manifests/group1.classes.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(MANIFEST_TEMPLATE, encoding="utf-8")

            output_jsonl = repo_root / "reports/materials/group1-query-audit.jsonl"
            trace_jsonl = repo_root / "reports/materials/group1-query-audit-trace.jsonl"

            result = run_group1_query_audit(
                query_dir=DEFAULT_GROUP1_QUERY_DIR,
                model="qwen2.5vl:7b",
                backlog_doc=backlog_doc,
                manifest_path=manifest_path,
                output_jsonl=output_jsonl,
                trace_jsonl=trace_jsonl,
                repo_root=repo_root,
                dry_run=True,
                classifier=lambda *_args: (
                    QueryIconDecision(
                        order=1,
                        decision="existing",
                        category_name="icon_plane",
                        category_zh_name="飞机",
                        description="飞机轮廓图标",
                        reason="现有类",
                    ),
                ),
            )

            self.assertEqual(result["image_count"], 1)
            self.assertEqual(
                result["query_dir"],
                str((repo_root / "materials/test/group1/query").resolve()),
            )

    def test_run_group1_query_audit_writes_report_and_updates_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            (query_dir / "b.png").write_bytes(b"b")
            (query_dir / "a.png").write_bytes(b"a")

            backlog_doc = repo_root / "docs/02-user-guide/group1-material-category-backlog.md"
            backlog_doc.parent.mkdir(parents=True, exist_ok=True)
            backlog_doc.write_text(BACKLOG_TEMPLATE, encoding="utf-8")

            manifest_path = repo_root / "materials/incoming/group1_icon_pack/manifests/group1.classes.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(MANIFEST_TEMPLATE, encoding="utf-8")

            output_jsonl = repo_root / "reports/materials/group1-query-audit.jsonl"
            trace_jsonl = repo_root / "reports/materials/group1-query-audit-trace.jsonl"

            def fake_classifier(image_path: Path, known_categories: object) -> QueryImageClassification:
                self.assertIn("icon_plane", str(known_categories))
                if image_path.name == "a.png":
                    return QueryImageClassification(
                        icons=(
                            QueryIconDecision(
                                order=1,
                                decision="existing",
                                category_name="icon_plane",
                                category_zh_name="飞机",
                                description="飞机轮廓图标",
                                reason="和现有飞机类一致",
                            ),
                            QueryIconDecision(
                                order=2,
                                decision="new_candidate",
                                category_name="icon_map_marker",
                                category_zh_name="地图定位点",
                                description="地图底座上方带空心定位针的图标",
                                reason="当前素材类中没有定位点类别",
                            ),
                        ),
                        raw_output='{"icons":[{"order":1,"category_name":"icon_plane"},{"order":2,"category_name":"icon_map_marker"}]}',
                    )
                return QueryImageClassification(
                    icons=(
                        QueryIconDecision(
                            order=1,
                            decision="existing",
                            category_name="icon_gift",
                            category_zh_name="礼物",
                            description="礼物盒图标",
                            reason="和现有礼物类一致",
                        ),
                        QueryIconDecision(
                            order=2,
                            decision="new_candidate",
                            category_name="icon_map_marker",
                            category_zh_name="地图定位点",
                            description="地图底座上方带空心定位针的图标",
                            reason="重复出现的新类",
                        ),
                    ),
                    raw_output='{"icons":[{"order":1,"category_name":"icon_gift"},{"order":2,"category_name":"icon_map_marker"}]}',
                )

            result = run_group1_query_audit(
                query_dir=query_dir,
                model="qwen2.5vl:7b",
                backlog_doc=backlog_doc,
                manifest_path=manifest_path,
                output_jsonl=output_jsonl,
                trace_jsonl=trace_jsonl,
                repo_root=repo_root,
                classifier=fake_classifier,
            )

            self.assertEqual(result["image_count"], 2)
            self.assertEqual(result["new_category_count"], 1)
            self.assertTrue(output_jsonl.exists())
            self.assertTrue(trace_jsonl.exists())

            rows = read_jsonl(output_jsonl)
            self.assertEqual([row["image_path"] for row in rows], ["query/a.png", "query/b.png"])
            self.assertEqual(rows[0]["new_categories"], ["icon_map_marker"])

            trace_rows = read_jsonl(trace_jsonl)
            self.assertEqual(trace_rows[0]["raw_output"], '{"icons":[{"order":1,"category_name":"icon_plane"},{"order":2,"category_name":"icon_map_marker"}]}')
            self.assertIsNone(trace_rows[0]["response_payload"])

            updated_backlog = backlog_doc.read_text(encoding="utf-8")
            self.assertIn(
                "| `icon_map_marker` | 地图定位点 | 地图底座上方带空心定位针的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：query/a.png |",
                updated_backlog,
            )
            self.assertIn("## 3.2 自动审计图片与分类映射（脚本生成）", updated_backlog)
            self.assertIn("自动审计发现；示例图片：query/a.png", updated_backlog)
            self.assertIn("1:`icon_plane`；2:`icon_map_marker`", updated_backlog)
            self.assertIn("1:`icon_gift`；2:`icon_map_marker`", updated_backlog)

    def test_run_group1_query_audit_reports_terminal_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            (query_dir / "a.png").write_bytes(b"a")

            backlog_doc = repo_root / "docs/02-user-guide/group1-material-category-backlog.md"
            backlog_doc.parent.mkdir(parents=True, exist_ok=True)
            backlog_doc.write_text(BACKLOG_TEMPLATE, encoding="utf-8")

            manifest_path = repo_root / "materials/incoming/group1_icon_pack/manifests/group1.classes.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(MANIFEST_TEMPLATE, encoding="utf-8")

            messages: list[str] = []
            run_group1_query_audit(
                query_dir=query_dir,
                model="qwen2.5vl:7b",
                backlog_doc=backlog_doc,
                manifest_path=manifest_path,
                repo_root=repo_root,
                dry_run=True,
                progress_reporter=messages.append,
                classifier=lambda image_path, _known_categories: QueryImageClassification(
                    icons=(
                        QueryIconDecision(
                            order=1,
                            decision="existing",
                            category_name="icon_plane",
                            category_zh_name="飞机",
                            description="飞机轮廓图标",
                            reason="现有类",
                        ),
                    ),
                    request_payload={
                        "model": "qwen2.5vl:7b",
                        "image_path": str(image_path),
                        "prompt": "prompt text",
                    },
                    raw_output='{"icons":[{"order":1,"category_name":"icon_plane"}]}',
                    response_payload={"message": {"content": '{"icons":[{"order":1,"category_name":"icon_plane"}]}'}},
                ),
            )

            joined = "\n".join(messages)
            self.assertIn("开始执行 group1 query 审计", joined)
            self.assertIn("正在处理图片 1/1", joined)
            self.assertIn("图片处理完成 1/1", joined)
            self.assertIn('"image_path": "query/a.png"', joined)
            self.assertIn('"request_payload"', joined)
            self.assertIn('"raw_output": "{\\"icons\\":[{\\"order\\":1,\\"category_name\\":\\"icon_plane\\"}]}"', joined)
            self.assertIn("执行完成", joined)

    def test_run_group1_query_audit_dry_run_keeps_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            (query_dir / "a.png").write_bytes(b"a")

            backlog_doc = repo_root / "docs/02-user-guide/group1-material-category-backlog.md"
            backlog_doc.parent.mkdir(parents=True, exist_ok=True)
            backlog_doc.write_text(BACKLOG_TEMPLATE, encoding="utf-8")

            manifest_path = repo_root / "materials/incoming/group1_icon_pack/manifests/group1.classes.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(MANIFEST_TEMPLATE, encoding="utf-8")

            output_jsonl = repo_root / "reports/materials/group1-query-audit.jsonl"
            trace_jsonl = repo_root / "reports/materials/group1-query-audit-trace.jsonl"
            original_backlog = backlog_doc.read_text(encoding="utf-8")

            result = run_group1_query_audit(
                query_dir=query_dir,
                model="qwen2.5vl:7b",
                backlog_doc=backlog_doc,
                manifest_path=manifest_path,
                output_jsonl=output_jsonl,
                trace_jsonl=trace_jsonl,
                repo_root=repo_root,
                dry_run=True,
                classifier=lambda *_args: (
                    QueryIconDecision(
                        order=1,
                        decision="new_candidate",
                        category_name="icon_map_marker",
                        category_zh_name="地图定位点",
                        description="地图底座上方带空心定位针的图标",
                        reason="当前素材类中没有定位点类别",
                    ),
                ),
            )

            self.assertEqual(result["new_category_count"], 1)
            self.assertFalse(output_jsonl.exists())
            self.assertFalse(trace_jsonl.exists())
            self.assertEqual(backlog_doc.read_text(encoding="utf-8"), original_backlog)

    def test_run_group1_query_audit_logs_raw_output_on_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            query_dir = repo_root / "query"
            query_dir.mkdir(parents=True, exist_ok=True)
            (query_dir / "a.png").write_bytes(b"a")

            backlog_doc = repo_root / "docs/02-user-guide/group1-material-category-backlog.md"
            backlog_doc.parent.mkdir(parents=True, exist_ok=True)
            backlog_doc.write_text(BACKLOG_TEMPLATE, encoding="utf-8")

            manifest_path = repo_root / "materials/incoming/group1_icon_pack/manifests/group1.classes.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(MANIFEST_TEMPLATE, encoding="utf-8")

            output_jsonl = repo_root / "reports/materials/group1-query-audit.jsonl"
            trace_jsonl = repo_root / "reports/materials/group1-query-audit-trace.jsonl"

            def broken_classifier(_image_path: Path, _known_categories: object) -> QueryImageClassification:
                raise QueryAuditClassificationError(
                    "no JSON object found with required keys: icons",
                    raw_output="this is not json",
                    response_payload={"message": {"content": "this is not json"}},
                )

            result = run_group1_query_audit(
                query_dir=query_dir,
                model="gemma4:26b",
                backlog_doc=backlog_doc,
                manifest_path=manifest_path,
                output_jsonl=output_jsonl,
                trace_jsonl=trace_jsonl,
                repo_root=repo_root,
                classifier=broken_classifier,
            )

            self.assertEqual(result["error_count"], 1)
            rows = read_jsonl(trace_jsonl)
            self.assertEqual(rows[0]["status"], "error")
            self.assertEqual(rows[0]["raw_output"], "this is not json")
            self.assertEqual(rows[0]["response_payload"], {"message": {"content": "this is not json"}})

    def test_parse_ollama_icon_response_normalizes_names_and_unknown_categories(self) -> None:
        icons = parse_ollama_icon_response(
            """
            {
              "icons": [
                {
                  "order": 2,
                  "decision": "existing",
                  "category_name": "Plane",
                  "category_zh_name": "飞机",
                  "description": "飞机轮廓图标",
                  "reason": "现有类"
                },
                {
                  "order": 1,
                  "decision": "existing",
                  "category_name": "map marker",
                  "category_zh_name": "地图定位点",
                  "description": "地图底座上方带空心定位针的图标",
                  "reason": "未知类"
                }
              ]
            }
            """,
            {"icon_plane": "飞机"},
        )

        self.assertEqual([icon.category_name for icon in icons], ["icon_map_marker", "icon_plane"])
        self.assertEqual(icons[0].decision, "new_candidate")
        self.assertEqual(icons[1].decision, "existing")
        self.assertEqual(icons[1].category_zh_name, "飞机")


if __name__ == "__main__":
    unittest.main()
