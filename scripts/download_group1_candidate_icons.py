from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import urllib.request
from pathlib import Path

DEFAULT_MAPPING_FILE = Path("work_home/materials/incoming/group1_query_clusters/semantic_candidates.json")
DEFAULT_CLUSTER_ROOT = Path("work_home/materials/incoming/group1_query_clusters")
DEFAULT_OUTPUT_DIR = Path("work_home/materials/incoming/group1_icon_candidates")

TABLER_SVG_RE = re.compile(
    r"(<svg[^>]*class=\"icon icon-tabler[^\"]*\"[^>]*>.*?</svg>)",
    re.DOTALL,
)


def extract_tabler_svg(page_html: str) -> str:
    match = TABLER_SVG_RE.search(page_html)
    if not match:
        raise ValueError("unable to locate Tabler SVG in page")
    return html.unescape(match.group(1)).strip() + "\n"


def fetch_text(url: str, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; sinan-captcha/0.1; "
                "+https://github.com/openai)"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def load_mapping(mapping_file: Path) -> dict:
    return json.loads(mapping_file.read_text(encoding="utf-8"))


def download_selected_icons(
    *,
    mapping_file: Path,
    cluster_root: Path,
    output_dir: Path,
    timeout: float,
    overwrite: bool,
) -> dict:
    mapping = load_mapping(mapping_file)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[dict] = []
    skipped: list[dict] = []
    failures: list[dict] = []

    for entry in mapping.get("entries", []):
        selected = entry.get("selected_source")
        if not selected:
            skipped.append(
                {
                    "cluster_id": entry["cluster_id"],
                    "class_name": entry["class_name"],
                    "reason": "no selected_source",
                }
            )
            continue

        if selected.get("library") != "tabler":
            skipped.append(
                {
                    "cluster_id": entry["cluster_id"],
                    "class_name": entry["class_name"],
                    "reason": f"unsupported library: {selected.get('library')}",
                }
            )
            continue

        class_dir = output_dir / entry["class_name"]
        class_dir.mkdir(parents=True, exist_ok=True)
        svg_path = class_dir / f"{selected['library']}_{selected['slug']}.svg"
        ref_src = cluster_root / "representatives" / f"{entry['cluster_id']}.png"
        ref_dst = class_dir / f"{entry['cluster_id']}_reference.png"
        meta_path = class_dir / "candidate.json"

        try:
            if overwrite or not svg_path.exists():
                page_html = fetch_text(selected["url"], timeout)
                svg_text = extract_tabler_svg(page_html)
                svg_path.write_text(svg_text, encoding="utf-8")

            if ref_src.exists() and (overwrite or not ref_dst.exists()):
                shutil.copy2(ref_src, ref_dst)

            meta_path.write_text(
                json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            downloaded.append(
                {
                    "cluster_id": entry["cluster_id"],
                    "class_name": entry["class_name"],
                    "svg_path": str(svg_path),
                    "reference_path": str(ref_dst) if ref_dst.exists() else None,
                    "source_url": selected["url"],
                }
            )
        except Exception as exc:
            failures.append(
                {
                    "cluster_id": entry["cluster_id"],
                    "class_name": entry["class_name"],
                    "source_url": selected["url"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    result = {
        "mapping_file": str(mapping_file),
        "cluster_root": str(cluster_root),
        "output_dir": str(output_dir),
        "downloaded_count": len(downloaded),
        "skipped_count": len(skipped),
        "failure_count": len(failures),
        "downloaded": downloaded,
        "skipped": skipped,
        "failures": failures,
    }
    (output_dir / "download_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download candidate icon assets for clustered group1 query icons."
    )
    parser.add_argument(
        "--mapping-file",
        type=Path,
        default=DEFAULT_MAPPING_FILE,
        help=f"Semantic candidate mapping file. Default: {DEFAULT_MAPPING_FILE}",
    )
    parser.add_argument(
        "--cluster-root",
        type=Path,
        default=DEFAULT_CLUSTER_ROOT,
        help=f"Cluster output root containing representatives/. Default: {DEFAULT_CLUSTER_ROOT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to store downloaded candidate icons. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds. Default: 20",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = download_selected_icons(
        mapping_file=args.mapping_file,
        cluster_root=args.cluster_root,
        output_dir=args.output_dir,
        timeout=args.timeout,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
