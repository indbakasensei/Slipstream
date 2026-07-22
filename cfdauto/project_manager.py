"""Project & Study Management — a lightweight infrastructure layer above the
existing config.yaml workflow.

A Slipstream "project" is a folder with a fixed standard layout::

    <Project>/
        config/
            config.yaml
        data/
        docs/
        outputs/
        runs/
        project.json

``project.json`` stores only lightweight metadata (name, description,
timestamps, tags) — never simulation results, config values, or anything
owned by the engine or the SQLite ledger. This module is purely about the
project folder's existence, shape, and metadata: it has no Qt, Fluent, or
Workbench imports, and never touches the solver, the ledger, or Study
Analytics. The existing engine (``Orchestrator`` + ``config.yaml``) is
unaffected — a project's ``config/config.yaml`` is opened exactly the same
way any other config file always has been.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

_SUBDIRS = ("config", "data", "docs", "outputs", "runs")
_METADATA_FILE = "project.json"
_RECENTS_FILE = "recent_projects.json"
_MAX_RECENTS_DEFAULT = 10


class ProjectError(Exception):
    """Raised for anything wrong with a project folder or its metadata.

    Deliberately a plain ``Exception`` — project management is desktop
    infrastructure, not a running study, so this is never wired into the
    ``CaseError``/``FrameworkError`` hierarchy in ``cfdauto.exceptions``.
    """


@dataclass
class ProjectMetadata:
    """The full, exact contents of ``project.json``."""

    name: str
    description: str = ""
    created: str = ""             # ISO 8601, set once at creation
    last_opened: str = ""         # ISO 8601, updated on every open_project()
    project_version: int = 1
    created_with: str = ""        # e.g. "Slipstream v1.0.0-alpha.5"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object, *, fallback_name: str = "") -> "ProjectMetadata":
        """Tolerant loader: unknown keys ignored, missing/invalid fields get
        sensible defaults. An empty ``{}`` (or entirely missing) metadata
        object is valid input here, not an error — see ``open_project``."""
        if not isinstance(data, dict):
            data = {}
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        if not clean.get("name"):
            clean["name"] = fallback_name
        if not isinstance(clean.get("tags"), list):
            clean["tags"] = []
        else:
            clean["tags"] = [t for t in clean["tags"] if isinstance(t, str)]
        return cls(**clean)


@dataclass
class ProjectValidationResult:
    """Result of :func:`validate_project_structure`. ``valid`` is exactly
    ``not problems`` — never derived any other way, so the two can never
    disagree."""

    valid: bool
    problems: List[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_metadata(root: Path) -> ProjectMetadata:
    path = root / _METADATA_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        raw = {}
    return ProjectMetadata.from_dict(raw, fallback_name=root.name)


def _write_metadata(root: Path, meta: ProjectMetadata) -> None:
    (root / _METADATA_FILE).write_text(
        json.dumps(meta.to_dict(), indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Structure validation
# --------------------------------------------------------------------------- #
def validate_project_structure(root: Union[str, Path]) -> ProjectValidationResult:
    """Check ``root`` against the standard layout. Never raises — every
    problem found is collected and returned, not just the first one."""
    root = Path(root)
    if not root.is_dir():
        return ProjectValidationResult(valid=False,
                                       problems=[f"'{root}' is not a directory."])

    problems: List[str] = []
    for sub in _SUBDIRS:
        if not (root / sub).is_dir():
            problems.append(f"Missing required folder: {sub}/")

    meta_path = root / _METADATA_FILE
    if not meta_path.exists():
        problems.append(f"Missing {_METADATA_FILE}")
    else:
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                problems.append(f"{_METADATA_FILE} must contain a JSON object.")
        except (json.JSONDecodeError, OSError) as exc:
            problems.append(f"{_METADATA_FILE} is not valid JSON: {exc}")

    return ProjectValidationResult(valid=not problems, problems=problems)


# --------------------------------------------------------------------------- #
# Create / open
# --------------------------------------------------------------------------- #
def create_project(root: Union[str, Path], name: str, description: str = "",
                   tags: Optional[List[str]] = None) -> ProjectMetadata:
    """Create a new project at ``root``.

    An existing *empty* directory may be adopted. An existing *non-empty*
    directory raises :class:`ProjectError` — this never silently overwrites
    something that's already there.
    """
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ProjectError(
            f"Cannot create project: '{root}' already exists and is not empty.")

    root.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)

    from . import __version__ as _slipstream_version
    now = _now_iso()
    meta = ProjectMetadata(
        name=name, description=description, created=now, last_opened=now,
        project_version=1, created_with=f"Slipstream v{_slipstream_version}",
        tags=list(tags or []))
    _write_metadata(root, meta)
    return meta


def open_project(root: Union[str, Path]) -> ProjectMetadata:
    """Open an existing project: validate its structure (raising
    :class:`ProjectError` listing every problem if invalid), load its
    metadata (tolerantly — see :meth:`ProjectMetadata.from_dict`), bump
    ``last_opened``, and persist that change."""
    root = Path(root)
    result = validate_project_structure(root)
    if not result.valid:
        raise ProjectError(
            f"'{root}' is not a valid Slipstream project:\n  - "
            + "\n  - ".join(result.problems))

    meta = _read_metadata(root)
    meta.last_opened = _now_iso()
    _write_metadata(root, meta)
    return meta


# --------------------------------------------------------------------------- #
# Recent projects
# --------------------------------------------------------------------------- #
def get_user_data_directory() -> Path:
    """Where Slipstream stores lightweight, cross-project app data (today:
    just the recent-projects list) — distinct from any specific project's
    own folder. Override with the ``SLIPSTREAM_DATA_DIR`` environment
    variable (tests use this, or pass ``store_path`` explicitly below, so
    a test run never touches a real user profile)."""
    override = os.environ.get("SLIPSTREAM_DATA_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Slipstream"
    return Path.home() / ".slipstream"


def _recents_path(store_path: Optional[Union[str, Path]]) -> Path:
    return Path(store_path) if store_path is not None else (
        get_user_data_directory() / _RECENTS_FILE)


def _resolve_or_raw(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except OSError:
        return p


def load_recent_projects(store_path: Optional[Union[str, Path]] = None) -> List[str]:
    """Most-recently-opened first. A missing or corrupt store recovers
    gracefully to an empty list rather than raising."""
    path = _recents_path(store_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, str)]


def add_recent_project(root: Union[str, Path],
                       store_path: Optional[Union[str, Path]] = None,
                       max_entries: int = _MAX_RECENTS_DEFAULT) -> List[str]:
    """Push ``root`` to the front of the recent-projects list, de-duplicated
    (an already-present entry moves to the front rather than appearing
    twice), capped at ``max_entries``, and persist it."""
    path = _recents_path(store_path)
    root_resolved = _resolve_or_raw(str(root))

    recents = load_recent_projects(store_path)
    recents = [r for r in recents if _resolve_or_raw(r) != root_resolved]
    recents.insert(0, root_resolved)
    recents = recents[:max_entries]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recents, indent=2), encoding="utf-8")
    return recents
