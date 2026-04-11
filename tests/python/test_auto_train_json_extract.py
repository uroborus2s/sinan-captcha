from __future__ import annotations

import json
import unittest

from auto_train import json_extract


class AutoTrainJsonExtractTests(unittest.TestCase):
    def test_extract_json_object_accepts_plain_json(self) -> None:
        payload = json_extract.extract_json_object(
            '{"decision":"RETUNE","reason":"ok","confidence":0.8,"next_action":{},"evidence":["x"]}',
            required_keys={"decision", "reason", "confidence", "next_action", "evidence"},
        )

        self.assertEqual(payload["decision"], "RETUNE")

    def test_extract_json_object_accepts_markdown_wrapped_json(self) -> None:
        raw_output = """
Here is the final result:

```json
{"dataset_action":"new_version","study_name":"study_001","task":"group1","trial_id":"trial_0004","boost_classes":[],"focus_failure_patterns":["order_errors"],"rationale_cn":"需要新数据","evidence":["order_errors"]}
```
"""

        payload = json_extract.extract_json_object(
            raw_output,
            required_keys={
                "study_name",
                "task",
                "trial_id",
                "dataset_action",
                "boost_classes",
                "focus_failure_patterns",
                "rationale_cn",
                "evidence",
            },
        )

        self.assertEqual(payload["dataset_action"], "new_version")

    def test_extract_json_object_from_opencode_event_stream(self) -> None:
        raw_output = "\n".join(
            [
                json.dumps({"type": "tool_use", "part": {"state": {"output": "not final"}}}, ensure_ascii=False),
                json.dumps(
                    {
                        "type": "message",
                        "part": {
                            "text": (
                                "Here is the answer:\n```json\n"
                                '{"study_name":"study_001","task":"group1","trial_id":"trial_0004",'
                                '"dataset_action":"new_version","boost_classes":[],"focus_failure_patterns":["order_errors"],'
                                '"rationale_cn":"需要新数据","evidence":["order_errors"]}\n```'
                            )
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        )

        payload = json_extract.extract_json_object_from_opencode_output(
            raw_output,
            required_keys={
                "study_name",
                "task",
                "trial_id",
                "dataset_action",
                "boost_classes",
                "focus_failure_patterns",
                "rationale_cn",
                "evidence",
            },
        )

        self.assertEqual(payload["trial_id"], "trial_0004")
        self.assertEqual(payload["dataset_action"], "new_version")

    def test_extract_json_object_repairs_missing_key_quote(self) -> None:
        raw_output = (
            '{"study_name":"study_001","task":"group1","trial_id":"trial_0004","dataset_action":"new_version",'
            '"boost_classes":[],"focus_failure_patterns":["order_errors"],"rationale_cn":"需要新数据",'
            '"generator_overrides":{"effects":{"click":{"icon_shadow_offset_y_max:4}}},"evidence":["order_errors"]}'
        )

        payload = json_extract.extract_json_object(
            raw_output,
            required_keys={
                "study_name",
                "task",
                "trial_id",
                "dataset_action",
                "boost_classes",
                "focus_failure_patterns",
                "rationale_cn",
                "evidence",
            },
        )

        self.assertEqual(payload["trial_id"], "trial_0004")
        overrides = payload["generator_overrides"]
        self.assertIsInstance(overrides, dict)
        click = overrides["effects"]["click"]
        self.assertEqual(click["icon_shadow_offset_y_max"], 4)

    def test_extract_json_object_from_opencode_event_stream_repairs_invalid_payload(self) -> None:
        raw_output = "\n".join(
            [
                json.dumps({"type": "step_start", "part": {"type": "step-start"}}, ensure_ascii=False),
                json.dumps(
                    {
                        "type": "text",
                        "part": {
                            "text": (
                                '{"study_name":"study_001","task":"group1","trial_id":"trial_0004","dataset_action":"new_version",'
                                '"boost_classes":[],"focus_failure_patterns":["order_errors","sequence_consistency"],'
                                '"generator_overrides":{"effects":{"click":{"icon_shadow_offset_y_max:4}}},'
                                '"rationale_cn":"需要新数据","evidence":["order_errors"]}'
                            )
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        )

        payload = json_extract.extract_json_object_from_opencode_output(
            raw_output,
            required_keys={
                "study_name",
                "task",
                "trial_id",
                "dataset_action",
                "boost_classes",
                "focus_failure_patterns",
                "rationale_cn",
                "evidence",
            },
        )

        self.assertEqual(payload["dataset_action"], "new_version")
        overrides = payload["generator_overrides"]
        self.assertIsInstance(overrides, dict)
        click = overrides["effects"]["click"]
        self.assertEqual(click["icon_shadow_offset_y_max"], 4)


if __name__ == "__main__":
    unittest.main()
