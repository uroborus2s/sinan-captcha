"""Stable OpenCode command contracts for autonomous training."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from core.auto_train import opencode_skills

INLINE_FILE_PREVIEW_LIMIT = 40_000


@dataclass(frozen=True)
class OpenCodeCommandSpec:
    name: str
    description: str
    message_arguments: tuple[str, ...]
    required_files: tuple[str, ...]
    optional_files: tuple[str, ...]
    output_artifact: str
    skill_name: str | None = None
    agent: str = "build"

    def markdown_path(self, project_root: Path) -> Path:
        return project_root / ".opencode" / "commands" / f"{self.name}.md"


def command_registry() -> "OrderedDict[str, OpenCodeCommandSpec]":
    """Return the fixed V1 OpenCode command set for autonomous training."""

    registry: "OrderedDict[str, OpenCodeCommandSpec]" = OrderedDict()
    registry["result-read"] = OpenCodeCommandSpec(
        name="result-read",
        description="Read trial artifacts and return result_summary.json",
        message_arguments=("study_name", "task", "trial_id", "dataset_version", "train_name", "primary_metric"),
        required_files=("test.json",),
        optional_files=("evaluate.json", "best_trial.json", "recent result_summary.json"),
        output_artifact="result_summary.json",
        skill_name="result-reader",
    )
    registry["judge-trial"] = OpenCodeCommandSpec(
        name="judge-trial",
        description="Judge one summarized trial and return decision.json",
        message_arguments=("study_name", "task", "trial_id"),
        required_files=("study.json", "result_summary.json"),
        optional_files=("leaderboard.json", "decisions.jsonl"),
        output_artifact="decision.json",
        skill_name="training-judge",
    )
    registry["plan-dataset"] = OpenCodeCommandSpec(
        name="plan-dataset",
        description="Plan the next dataset action and return dataset_plan.json",
        message_arguments=("study_name", "task", "trial_id"),
        required_files=("result_summary.json",),
        optional_files=("leaderboard.json", "best_trial.json"),
        output_artifact="dataset_plan.json",
        skill_name="dataset-planner",
    )
    registry["study-status"] = OpenCodeCommandSpec(
        name="study-status",
        description="Summarize the current study and return study_status.json",
        message_arguments=("study_name", "task"),
        required_files=("study.json", "leaderboard.json"),
        optional_files=("best_trial.json", "decisions.jsonl"),
        output_artifact="study_status.json",
        skill_name="study-archivist",
    )
    return registry


def get_command_spec(name: str) -> OpenCodeCommandSpec:
    """Return one registered command spec or raise on unsupported names."""

    registry = command_registry()
    try:
        return registry[name]
    except KeyError as exc:
        allowed = ", ".join(registry.keys())
        raise ValueError(f"unsupported OpenCode command: {name}; allowed: {allowed}") from exc


def _strip_frontmatter(markdown_text: str) -> str:
    stripped = markdown_text.lstrip()
    if not stripped.startswith("---"):
        return markdown_text.strip()
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return markdown_text.strip()
    return parts[2].strip()


def _render_arguments(template: str, arguments: list[str]) -> str:
    rendered = template
    rendered = rendered.replace("$ARGUMENTS", " ".join(arguments))
    for index, argument in enumerate(arguments, start=1):
        rendered = rendered.replace(f"${index}", argument)
    return rendered


def _read_markdown_body(path: Path) -> str:
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


def _render_skill_section(project_root: Path, skill_name: str) -> str:
    skill_path = opencode_skills.skill_registry()[skill_name].markdown_path(project_root)
    try:
        skill_body = _read_markdown_body(skill_path)
    except UnicodeDecodeError as exc:
        skill_body = f"[skill_read_error: unicode_decode_error: {exc}]"
    except OSError as exc:
        skill_body = f"[skill_read_error: os_error: {exc}]"
    return "\n".join(
        [
            f"Local skill guidance (`{skill_name}`, already loaded below; do not call the `skill` tool):",
            "",
            skill_body,
        ]
    )


def render_prompt(
    name: str,
    *,
    arguments: list[str],
    project_root: Path,
    files: list[Path],
) -> str:
    spec = get_command_spec(name)
    command_path = spec.markdown_path(project_root)
    command_body = _render_arguments(_read_markdown_body(command_path), arguments)

    sections = [command_body]
    if spec.skill_name is not None:
        sections.append(_render_skill_section(project_root, spec.skill_name))
    sections.append(
        "\n".join(
            [
                "Tool usage constraints:",
                "- Do not call the `skill` tool. Relevant local skill guidance is already inlined below.",
                "- Do not call `glob_search`; that tool does not exist in this environment.",
                "- Do not call bash, read, glob, grep, edit, write, task, webfetch, or todowrite unless the prompt explicitly requires them.",
                "- All required input files are already inlined below, so file/search tools are unnecessary.",
            ]
        )
    )
    if files:
        file_sections: list[str] = [
            "Inline file contents (already loaded below; do not call any file, search, or glob tools):"
        ]
        for file in files:
            file_sections.append(_render_file_section(file))
        sections.append("\n\n".join(file_sections))
    sections.append(
        "\n".join(
            [
                f"Final output contract: return exactly one JSON object for {spec.output_artifact}.",
                "Do not emit markdown fences.",
                "Do not emit any prose before or after the JSON object.",
                "Do not call tools before returning the final JSON object.",
            ]
        )
    )
    return "\n\n".join(section for section in sections if section.strip())


def _render_file_section(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        body = f"[read_error: unicode_decode_error: {exc}]"
    except OSError as exc:
        body = f"[read_error: os_error: {exc}]"
    else:
        if len(text) > INLINE_FILE_PREVIEW_LIMIT:
            body = text[:INLINE_FILE_PREVIEW_LIMIT] + "\n[truncated]"
        else:
            body = text
    return "\n".join(
        [
            f"--- Begin file: {path} ---",
            body,
            f"--- End file: {path} ---",
        ]
    )


def build_headless_invocation(
    name: str,
    *,
    arguments: list[str],
    files: list[Path],
    project_root: Path,
    attach_url: str | None = None,
    model: str | None = None,
) -> list[str]:
    """Build a stable ``opencode run`` invocation for one autonomous-training command."""

    spec = get_command_spec(name)
    if len(arguments) != len(spec.message_arguments):
        expected = ", ".join(spec.message_arguments)
        raise ValueError(f"{name} expects {len(spec.message_arguments)} arguments: {expected}")

    prompt = render_prompt(name, arguments=arguments, project_root=project_root, files=files)
    command = ["opencode", "run", "--format", "json", "--agent", spec.agent]
    if attach_url is not None:
        command.extend(["--attach", attach_url])
    if model is not None:
        command.extend(["--model", model])
    command.append("--")
    command.append(prompt)
    return command
