"""Optional Optuna runtime adapter for autonomous retune flows."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path

from auto_train import contracts, optimize

DEFAULT_DIRECTION = "maximize"
DEFAULT_MODULE_NAME = "optuna"
DEFAULT_STORAGE_FILE_NAME = "optuna.sqlite3"

OPTUNA_TRIAL_NUMBER_KEY = "_optuna_trial_number"
OPTUNA_ENGINE_KEY = "_optuna_engine"
OPTUNA_TRIAL_ID_ATTR = "sinan_trial_id"
OPTUNA_TASK_ATTR = "sinan_task"
INTERNAL_PARAM_KEYS = {OPTUNA_TRIAL_NUMBER_KEY, OPTUNA_ENGINE_KEY}


@dataclass(frozen=True)
class OptunaRuntimeConfig:
    study_name: str
    storage_path: Path
    direction: str = DEFAULT_DIRECTION
    module_name: str = DEFAULT_MODULE_NAME

    def __post_init__(self) -> None:
        if not self.study_name.strip():
            raise ValueError("study_name must not be empty")
        if self.direction not in {"maximize", "minimize"}:
            raise ValueError("direction must be maximize or minimize")

    @property
    def storage_url(self) -> str:
        return f"sqlite:///{self.storage_path.expanduser().resolve().as_posix()}"


@dataclass(frozen=True)
class OptunaSuggestion:
    study_name: str
    trial_number: int
    params: dict[str, contracts.JsonValue]
    reused_existing: bool

    def __post_init__(self) -> None:
        if not self.study_name.strip():
            raise ValueError("study_name must not be empty")
        if self.trial_number < 0:
            raise ValueError("trial_number must not be negative")
        if not self.params:
            raise ValueError("params must not be empty")


class OptunaRuntimeError(RuntimeError):
    """Raised when the optional Optuna runtime cannot provide a suggestion."""


@dataclass(frozen=True)
class OptunaRuntimeAdapter:
    config: OptunaRuntimeConfig
    module_loader: object = importlib.import_module

    def suggest_next_parameters(
        self,
        *,
        plan: optimize.OptimizationPlan,
        completed_input: contracts.TrialInputRecord,
        summary: contracts.ResultSummaryRecord,
        next_trial_id: str,
    ) -> OptunaSuggestion:
        if not plan.use_optuna:
            raise OptunaRuntimeError("optuna_plan_disabled")
        if summary.primary_score is None:
            raise OptunaRuntimeError("missing_primary_score")

        module = self._load_module()
        study = self._load_study(module)
        self._register_completed_trial(
            module=module,
            study=study,
            plan=plan,
            completed_input=completed_input,
            summary=summary,
        )

        existing = self._find_trial(study, next_trial_id)
        if existing is not None:
            params = self._extract_search_params(existing.params, plan.search_space)
            return OptunaSuggestion(
                study_name=self.config.study_name,
                trial_number=existing.number,
                params=params,
                reused_existing=True,
            )

        distributions = self._build_distributions(module, plan.search_space)
        try:
            trial = study.ask(fixed_distributions=distributions)
        except Exception as exc:  # pragma: no cover - exercised with fake module tests
            raise OptunaRuntimeError(f"optuna_ask_failed: {exc}") from exc

        if hasattr(trial, "set_user_attr"):
            trial.set_user_attr(OPTUNA_TRIAL_ID_ATTR, next_trial_id)
            trial.set_user_attr(OPTUNA_TASK_ATTR, plan.task)
        params = self._extract_search_params(getattr(trial, "params", {}), plan.search_space)
        return OptunaSuggestion(
            study_name=self.config.study_name,
            trial_number=trial.number,
            params=params,
            reused_existing=False,
        )

    def _load_module(self) -> object:
        try:
            return self.module_loader(self.config.module_name)
        except Exception as exc:
            raise OptunaRuntimeError(f"optuna_import_failed: {self.config.module_name}") from exc

    def _load_study(self, module: object) -> object:
        self.config.storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return module.create_study(
                storage=self.config.storage_url,
                study_name=self.config.study_name,
                direction=self.config.direction,
                load_if_exists=True,
            )
        except Exception as exc:
            raise OptunaRuntimeError(f"optuna_create_study_failed: {exc}") from exc

    def _register_completed_trial(
        self,
        *,
        module: object,
        study: object,
        plan: optimize.OptimizationPlan,
        completed_input: contracts.TrialInputRecord,
        summary: contracts.ResultSummaryRecord,
    ) -> None:
        existing = self._find_trial(study, completed_input.trial_id)
        try:
            if existing is not None:
                study.tell(existing.number, float(summary.primary_score), skip_if_finished=True)
                return

            trial_number = _optuna_trial_number(completed_input.params)
            if trial_number is not None:
                study.tell(trial_number, float(summary.primary_score), skip_if_finished=True)
                return

            params = self._extract_search_params(completed_input.params, plan.search_space)
            distributions = self._build_distributions(module, plan.search_space)
            frozen = module.trial.create_trial(
                state=module.trial.TrialState.COMPLETE,
                value=float(summary.primary_score),
                params=params,
                distributions=distributions,
                user_attrs={
                    OPTUNA_TRIAL_ID_ATTR: completed_input.trial_id,
                    OPTUNA_TASK_ATTR: plan.task,
                },
            )
            study.add_trial(frozen)
        except Exception as exc:
            raise OptunaRuntimeError(f"optuna_register_completed_trial_failed: {exc}") from exc

    def _find_trial(self, study: object, trial_id: str) -> object | None:
        for candidate in study.get_trials(deepcopy=False):
            user_attrs = getattr(candidate, "user_attrs", {})
            if isinstance(user_attrs, dict) and user_attrs.get(OPTUNA_TRIAL_ID_ATTR) == trial_id:
                return candidate
        return None

    def _build_distributions(
        self,
        module: object,
        search_space: optimize.SearchSpace,
    ) -> dict[str, object]:
        distributions: dict[str, object] = {}
        for name, values in search_space.parameters.items():
            distributions[name] = module.distributions.CategoricalDistribution(list(values))
        return distributions

    def _extract_search_params(
        self,
        payload: dict[str, contracts.JsonValue],
        search_space: optimize.SearchSpace,
    ) -> dict[str, contracts.JsonValue]:
        params: dict[str, contracts.JsonValue] = {}
        for name, values in search_space.parameters.items():
            if name not in payload:
                raise OptunaRuntimeError(f"missing_search_param: {name}")
            value = payload[name]
            if value not in values:
                raise OptunaRuntimeError(f"invalid_search_param: {name}={value}")
            params[name] = value
        return params


def _optuna_trial_number(payload: dict[str, contracts.JsonValue]) -> int | None:
    value = payload.get(OPTUNA_TRIAL_NUMBER_KEY)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
