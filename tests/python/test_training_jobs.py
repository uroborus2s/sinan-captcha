from pathlib import Path
import unittest

from core.train.group1.service import build_group1_training_job
from core.train.group2.service import build_group2_training_job


class TrainingJobTests(unittest.TestCase):
    def test_group1_uses_expected_defaults(self) -> None:
        job = build_group1_training_job(Path("datasets/group1/v1/yolo/dataset.yaml"), Path("runs/group1"))
        command = job.command()
        self.assertIn("model=yolo26n.pt", command)
        self.assertIn("epochs=120", command)

    def test_group2_uses_expected_defaults(self) -> None:
        job = build_group2_training_job(Path("datasets/group2/v1/yolo/dataset.yaml"), Path("runs/group2"))
        command = job.command()
        self.assertIn("model=yolo26n.pt", command)
        self.assertIn("epochs=100", command)


if __name__ == "__main__":
    unittest.main()
