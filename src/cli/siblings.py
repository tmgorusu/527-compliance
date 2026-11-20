"""Resolve sibling agent public APIs with clear, actionable import errors."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable


class SiblingUnavailableError(RuntimeError):
    """Raised when a required sibling module/API is missing or incomplete."""


@dataclass(frozen=True)
class SiblingApis:
    """Resolved callables from Agents A–D (may be partially None)."""

    # Agent A — prefer run_pipeline (returns PipelineResult)
    run_ingest_pipeline: Callable[..., Any] | None
    build_normalized_bundle: Callable[..., Any] | None
    # Agent D
    apply_thresholds_and_rollups: Callable[..., Any] | None
    run_compliance: Callable[..., Any] | None
    reconcile: Callable[..., Any] | None
    write_reconciliation_report: Callable[..., Any] | None
    # Agent B
    build_form_8872: Callable[..., Any] | None
    validate_form_8872: Callable[..., Any] | None
    # Agent C
    texas_build: Callable[..., Any] | None
    texas_validate: Callable[..., Any] | None
    texas_required_spec_files: Callable[..., Any] | None
    SpecMissingError: type[BaseException] | None


def _try_import(module_name: str) -> ModuleType | None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _get(mod: ModuleType | None, name: str) -> Any | None:
    if mod is None:
        return None
    return getattr(mod, name, None)


def _first_callable(
    module_names: tuple[str, ...], attr_names: tuple[str, ...]
) -> Callable[..., Any] | None:
    for mod_name in module_names:
        mod = _try_import(mod_name)
        if mod is None:
            continue
        for attr in attr_names:
            obj = getattr(mod, attr, None)
            if callable(obj):
                return obj
    return None


def _resolve_texas() -> tuple[
    Callable[..., Any] | None,
    Callable[..., Any] | None,
    Callable[..., Any] | None,
    type[BaseException] | None,
]:
    errors_mod = _try_import("src.xmlbuild.texas.errors")
    pkg = _try_import("src.xmlbuild.texas")
    plugin_mod = _try_import("src.xmlbuild.texas.plugin")

    spec_err = _get(errors_mod, "SpecMissingError") or _get(pkg, "SpecMissingError")
    if not (isinstance(spec_err, type) and issubclass(spec_err, BaseException)):
        spec_err = None

    build = validate = required = None

    # Prefer package-level ``plugin`` singleton (Agent C)
    for mod in (pkg, plugin_mod):
        if mod is None:
            continue
        plug = getattr(mod, "plugin", None)
        if plug is None:
            cls = getattr(mod, "TexasTecPlugin", None) or getattr(
                mod, "TexasPlugin", None
            )
            if isinstance(cls, type):
                plug = cls()
        if plug is None:
            continue
        if hasattr(plug, "build") and callable(plug.build):
            build = plug.build
        if hasattr(plug, "validate") and callable(plug.validate):
            validate = plug.validate
        if hasattr(plug, "required_spec_files") and callable(plug.required_spec_files):
            required = plug.required_spec_files
        break

    if required is None:
        required = _first_callable(
            ("src.xmlbuild.texas", "src.xmlbuild.texas.plugin"),
            ("required_spec_file_paths", "required_spec_files"),
        )

    return build, validate, required, spec_err


def resolve_siblings() -> SiblingApis:
    """Best-effort discovery of sibling public APIs."""
    run_ingest = _first_callable(
        ("src.ingest", "src.ingest.pipeline"),
        ("run_pipeline",),
    )
    build_bundle = _first_callable(
        ("src.ingest", "src.ingest.pipeline"),
        ("build_normalized_bundle",),
    )

    apply_thresholds = _first_callable(
        ("src.compliance", "src.compliance.thresholds"),
        ("apply_thresholds_and_rollups",),
    )
    run_compliance = _first_callable(
        ("src.compliance", "src.compliance.checks"),
        ("run_compliance",),
    )
    reconcile = _first_callable(
        ("src.compliance", "src.compliance.reconcile"),
        ("reconcile",),
    )
    write_recon = _first_callable(
        ("src.compliance", "src.compliance.reconcile"),
        ("write_reconciliation_report",),
    )

    build_federal = _first_callable(
        ("src.xmlbuild.federal", "src.xmlbuild.federal.builder"),
        ("build_form_8872",),
    )
    validate_federal = _first_callable(
        (
            "src.xmlbuild.federal",
            "src.xmlbuild.federal.validate",
            "src.xmlbuild.federal.builder",
        ),
        ("validate_form_8872",),
    )

    texas_build, texas_validate, texas_required, spec_err = _resolve_texas()

    return SiblingApis(
        run_ingest_pipeline=run_ingest,
        build_normalized_bundle=build_bundle,
        apply_thresholds_and_rollups=apply_thresholds,
        run_compliance=run_compliance,
        reconcile=reconcile,
        write_reconciliation_report=write_recon,
        build_form_8872=build_federal,
        validate_form_8872=validate_federal,
        texas_build=texas_build,
        texas_validate=texas_validate,
        texas_required_spec_files=texas_required,
        SpecMissingError=spec_err,
    )


def require(api: Callable[..., Any] | None, label: str) -> Callable[..., Any]:
    if api is None:
        raise SiblingUnavailableError(
            f"Sibling module unavailable: {label}. "
            "Complete the owning agent package, then re-run."
        )
    return api


def sibling_status() -> dict[str, bool]:
    """Map of capability name → available (for diagnostics / tests)."""
    apis = resolve_siblings()
    return {
        "agent_a_ingest_clean": (
            apis.run_ingest_pipeline is not None
            or apis.build_normalized_bundle is not None
        ),
        "agent_d_thresholds": apis.apply_thresholds_and_rollups is not None,
        "agent_d_compliance": apis.run_compliance is not None,
        "agent_d_reconcile": apis.reconcile is not None,
        "agent_b_federal_build": apis.build_form_8872 is not None,
        "agent_b_federal_validate": apis.validate_form_8872 is not None,
        "agent_c_texas_build": apis.texas_build is not None,
        "agent_c_spec_missing_error": apis.SpecMissingError is not None,
    }
