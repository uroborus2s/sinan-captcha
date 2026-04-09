from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "download_group1_candidate_icons.py"
    )
    spec = importlib.util.spec_from_file_location("download_group1_candidate_icons", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DownloadGroup1CandidateIconsScriptTest(TestCase):
    def test_extract_tabler_svg_returns_embedded_svg(self) -> None:
        module = _load_script_module()
        page_html = """
        <html>
          <body>
            <h1>heart</h1>
            <div>SVG Code</div>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
                 viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 class="icon icon-tabler icons-tabler-outline icon-tabler-heart">
              <path d="M1 2" />
            </svg>
          </body>
        </html>
        """

        actual = module.extract_tabler_svg(page_html)

        self.assertIn('class="icon icon-tabler', actual)
        self.assertTrue(actual.strip().startswith("<svg"))
        self.assertTrue(actual.strip().endswith("</svg>"))

    def test_extract_tabler_svg_raises_for_missing_svg(self) -> None:
        module = _load_script_module()

        with self.assertRaises(ValueError):
            module.extract_tabler_svg("<html><body>missing</body></html>")
