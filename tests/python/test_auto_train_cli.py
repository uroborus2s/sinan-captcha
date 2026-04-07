from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.auto_train import cli


class AutoTrainCliTests(unittest.TestCase):
    def test_run_command_forwards_business_eval_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train_root = root / "train-root"
            generator_workspace = root / "generator-workspace"
            business_cases = root / "business-cases"
            for path in (train_root, generator_workspace, business_cases):
                path.mkdir(parents=True, exist_ok=True)

            captured_request = None

            class FakeController:
                def __init__(self, *, request: object) -> None:
                    nonlocal captured_request
                    captured_request = request

                def run(self, *, max_steps: int) -> object:
                    self.max_steps = max_steps
                    return type(
                        "Result",
                        (),
                        {
                            "executed": [],
                            "final_stage": "STOP",
                        },
                    )()

            with patch("core.auto_train.cli.controller.AutoTrainController", FakeController):
                code = cli.main(
                    [
                        "run",
                        "group2",
                        "--study-name",
                        "study_001",
                        "--train-root",
                        str(train_root),
                        "--generator-workspace",
                        str(generator_workspace),
                        "--business-eval-dir",
                        str(business_cases),
                        "--business-eval-success-threshold",
                        "0.98",
                        "--business-eval-min-cases",
                        "8",
                        "--business-eval-sample-size",
                        "100",
                        "--business-eval-occlusion-threshold",
                        "0.81",
                    ]
                )

            self.assertEqual(code, 0)
            assert captured_request is not None
            self.assertEqual(captured_request.business_eval_dir, business_cases)
            self.assertEqual(captured_request.business_eval_success_threshold, 0.98)
            self.assertEqual(captured_request.business_eval_min_cases, 8)
            self.assertEqual(captured_request.business_eval_sample_size, 100)
            self.assertEqual(captured_request.business_eval_occlusion_threshold, 0.81)


if __name__ == "__main__":
    unittest.main()
