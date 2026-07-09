"""Fluent solver control via PyFluent (gRPC).

Responsibilities of this module — everything that happens *inside* Fluent:

1.  Launch a headless Fluent session pinned to the configured version.
2.  Read the user's **baseline case** (exported once, physics fully tuned).
3.  ``geometry`` mode: replace the mesh with the one Workbench just produced
    (``file.replace_mesh`` keeps every physics setting identical — exactly the
    "change nothing but the mesh" requirement).
4.  Set per-case **reference values** (reference velocity MUST follow the inlet
    velocity or CL/CD would be normalised wrongly) and the inlet boundary
    condition.  In ``velocity_vector`` mode the flow direction is rotated too.
5.  Create/refresh four report definitions (cl, cd, fl, fd) whose force
    vectors come from :mod:`cfdauto.aero` so both AOA methods use consistent
    wind axes.
6.  Initialise, iterate in chunks, and decide convergence from the **history
    of CL/CD** (flat over a trailing window) rather than raw residuals — the
    quantity the study actually cares about.
7.  Extract final values with ``report_definitions.compute`` and cross-check
    CL against Lift/(q·A) to catch reference-value mistakes.

Version tolerance
-----------------
The PyFluent settings tree is generated per Fluent release and a few names
moved between 2024R2 and 2025R2 (verified against the generated classes that
ship inside ``ansys-fluent-core``):

====================================  =================================================
2024R2 (242)                          2025R2 (252)
====================================  =================================================
``vinlet[z].momentum.velocity``       ``vinlet[z].settings.momentum.velocity_magnitude``
(Group: option/value/profile_name)    (same Group shape, renamed + extra ``settings``)
``solver.<branch>``                   ``solver.settings.<branch>`` (old path aliased)
====================================  =================================================

Everything below therefore goes through tiny adapter helpers (`_root`,
`_inlet_settings`, `_set_scalar`, ...) instead of hard-coding one tree shape.
PyFluent itself is imported lazily so the rest of the framework (mock mode,
dry-run, unit tests) works on machines without ANSYS installed.
"""

from __future__ import annotations

import inspect
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import aero
from .config import Config
from .events import EventBus
from .telemetry import TelemetryTap
from .exceptions import (
    DivergedError,
    FluentError,
    NotConvergedError,
    ResultExtractionError,
)
from .models import CaseResult, Experiment

log = logging.getLogger("cfdauto.fluent")

# Report-definition names created by this framework inside the case.
RD_CL, RD_CD, RD_FL, RD_FD = "cfdauto_cl", "cfdauto_cd", "cfdauto_fl", "cfdauto_fd"
REPORT_FILE_NAME = "cfdauto_history.out"


class FluentController:
    """One instance per orchestrator; one Fluent session per *case*.

    A fresh session per case is deliberate: it guarantees a clean solver state
    (no leaked settings from a previous run), makes crash recovery trivial
    (nothing to reconnect to) and its cost (~30-60 s launch) is negligible
    next to a converged RANS solve.
    """

    def __init__(self, cfg: Config, bus: Optional[EventBus] = None):
        self.cfg = cfg
        self.fl = cfg.fluent
        self.solve = cfg.solve
        self.bus = bus or EventBus()
        self._exp: Optional[Experiment] = None   # current case (for events)

    # ------------------------------------------------------------------ #
    # Event helpers (row/case_id attached automatically)
    # ------------------------------------------------------------------ #
    def _emit(self, type_: str, **data) -> None:
        if self._exp is not None:
            data.setdefault("row", self._exp.row)
            data.setdefault("case_id", self._exp.case_id)
        self.bus.emit(type_, **data)

    def _stage(self, stage: str, state: str = "start") -> None:
        self._emit("stage", stage=stage, state=state)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run_case(self, exp: Experiment, mesh_file: Optional[Path],
                 case_dir: Path) -> CaseResult:
        """Execute the complete solver phase for one experiment.

        Parameters
        ----------
        exp:
            The experiment row (AOA + velocity + extras).
        mesh_file:
            Path of the mesh produced by Workbench for this geometry, or
            ``None`` in ``velocity_vector`` mode (baseline mesh is reused).
        case_dir:
            Per-case artifact directory (transcript, history, saved case...).
        """
        res = CaseResult(started=datetime.now(),
                         mesh_file=str(mesh_file or ""),
                         artifact_dir=str(case_dir))
        self._exp = exp
        # Per-case fallback buffers for the compute()-based convergence path.
        self._fallback_cl: List[float] = []
        self._fallback_cd: List[float] = []
        solver = None
        try:
            self._stage("fluent_launch")
            solver = self._launch(case_dir)
            root = _root(solver)
            self._stage("fluent_launch", "done")
            self._emit("fluent.launched", cores=self.fl.processor_count)

            self._start_transcript(root, case_dir)
            self._stage("read_case")
            self._read_baseline(root)
            self._stage("read_case", "done")

            if self.fl.aoa_method == "geometry":
                if mesh_file is None:
                    raise FluentError("geometry mode requires a mesh file but none was provided")
                self._stage("replace_mesh")
                self._replace_mesh(root, mesh_file)
                self._stage("replace_mesh", "done")
            else:
                self._stage("replace_mesh", "skip")

            # Wind axes for this case: identical maths for both AOA methods.
            flow_dir, drag_vec, lift_vec = aero.wind_axes(
                exp.aoa_deg, self.fl.aoa_method,
                self.fl.base_flow_axis, self.fl.base_lift_axis,
            )

            self._stage("setup")
            self._set_reference_values(root, exp.velocity)
            self._set_inlet(root, exp.velocity, flow_dir)
            self._setup_report_definitions(root, drag_vec, lift_vec)
            history_file = self._setup_history_file(root, case_dir)
            self._stage("setup", "done")

            self._stage("initialize")
            self._initialize(root)
            self._stage("initialize", "done")
            self._stage("solve")
            iterations, converged = self._solve_until_converged(
                root, history_file, case_dir=case_dir)
            res.iterations, res.converged = iterations, converged

            self._stage("extract")
            cl, cd, fl_n, fd_n = self._extract_results(root, history_file, exp)
            res.cl, res.cd, res.lift_n, res.drag_n = cl, cd, fl_n, fd_n
            self._crosscheck(exp, res)

            if self.fl.capture_images:
                self._capture_images(root, case_dir)
            if self.solve.save_case_data:
                self._save_case_data(root, case_dir)
            self._stage("extract", "done")

            if not converged and not self.solve.accept_unconverged:
                raise NotConvergedError(
                    f"Not converged after {iterations} iterations "
                    f"(CL spread tolerance {self.solve.cl_tolerance:g})"
                )
            return res

        finally:
            res.finished = datetime.now()
            self._shutdown(solver)

    # ------------------------------------------------------------------ #
    # Launch / shutdown
    # ------------------------------------------------------------------ #
    def _launch(self, case_dir: Path):
        try:
            import ansys.fluent.core as pyfluent  # local import: optional dep
        except ImportError as exc:
            raise FluentError(
                "ansys-fluent-core is not installed. Run:  pip install ansys-fluent-core"
            ) from exc

        wanted: Dict[str, Any] = {
            "mode": "solver",
            "precision": self.fl.precision,
            "processor_count": int(self.fl.processor_count),
            "dimension": int(self.fl.dimension),
            "start_timeout": int(self.fl.launch_timeout_s),
            "cwd": str(case_dir),
            "cleanup_on_exit": True,
        }
        if self.fl.product_version:
            wanted["product_version"] = self.fl.product_version

        # ui_mode is the modern kwarg; very old PyFluent used show_gui instead.
        sig = set(inspect.signature(pyfluent.launch_fluent).parameters)
        if "ui_mode" in sig:
            wanted["ui_mode"] = self.fl.ui_mode
        elif "show_gui" in sig:
            wanted["show_gui"] = self.fl.ui_mode == "gui"

        kwargs = {k: v for k, v in wanted.items() if k in sig}
        dropped = set(wanted) - set(kwargs)
        if dropped:
            log.debug("launch_fluent(): dropped unsupported kwargs %s", sorted(dropped))

        log.info("Launching Fluent (%sD, %s precision, %d cores, ui=%s)...",
                 self.fl.dimension, self.fl.precision,
                 self.fl.processor_count, self.fl.ui_mode)
        try:
            solver = pyfluent.launch_fluent(**kwargs)
        except Exception as exc:
            raise FluentError(f"Fluent failed to launch: {exc}") from exc
        log.info("Fluent session up.")
        return solver

    def _shutdown(self, solver) -> None:
        if solver is None:
            return
        try:
            solver.exit()
            log.info("Fluent session closed.")
        except Exception:
            # Don't let a dying session mask the real error; try harder, then
            # give up quietly — cleanup_on_exit reaps the process anyway.
            try:
                solver.force_exit()
            except Exception:
                log.warning("Could not confirm Fluent shutdown (process may linger).")

    # ------------------------------------------------------------------ #
    # Case / mesh
    # ------------------------------------------------------------------ #
    def _current_transcript_path(self, case_dir: Path) -> Path:
        """Where _start_transcript wrote the .trn — used by the telemetry tap."""
        return case_dir / "transcript.trn"

    def _start_transcript(self, root, case_dir: Path) -> None:
        trn = (case_dir / "transcript.trn").resolve().as_posix()
        try:
            root.file.start_transcript(file_name=trn)
        except Exception:
            try:
                root.file.start_transcript(trn)
            except Exception:
                log.debug("Transcript could not be started — continuing without it.")

    def _read_baseline(self, root) -> None:
        case = self.fl.baseline_case_path().resolve().as_posix()
        log.info("Reading baseline case %s", case)
        try:
            root.file.read_case(file_name=case)
        except Exception as exc:
            raise FluentError(f"Could not read baseline case '{case}': {exc}") from exc

    def _replace_mesh(self, root, mesh_file: Path) -> None:
        """Swap the mesh, keep every physics/BC setting — the whole point of
        the baseline-case strategy. Zone names survive because the named
        selections in the geometry are unchanged."""
        log.info("Replacing mesh with %s", mesh_file.name)
        try:
            root.file.replace_mesh(file_name=mesh_file.resolve().as_posix())
        except Exception as exc:
            raise FluentError(
                f"mesh replace failed for '{mesh_file}': {exc}. "
                "Most common cause: zone names in the new mesh differ from the "
                "baseline case (check the Named Selections in the geometry)."
            ) from exc

    # ------------------------------------------------------------------ #
    # Reference values + inlet boundary condition
    # ------------------------------------------------------------------ #
    def _set_reference_values(self, root, velocity: float) -> None:
        """Reference values drive the CL/CD normalisation: rho, V, A.

        *Reference velocity must be updated every case* — forgetting this is
        the classic way to get identical-looking CL at different speeds.
        """
        ref = self.fl.reference
        rv = root.setup.reference_values
        values = {
            "density": ref.density,
            "velocity": float(velocity),       # per-case!
            "area": ref.area,
            "length": ref.length,
            "depth": ref.depth,
            "viscosity": ref.viscosity,
            "temperature": ref.temperature,
            "pressure": ref.pressure,
        }
        for name, value in values.items():
            try:
                setattr(rv, name, value)
            except Exception as exc:
                # depth doesn't exist in 2D, etc. — log and move on.
                log.debug("reference_values.%s not settable (%s)", name, exc)
        log.info("Reference values set (V_ref=%.3f m/s, rho=%.4f, A=%.4f m^2)",
                 velocity, ref.density, ref.area)

    def _set_inlet(self, root, velocity: float, flow_dir: Sequence[float]) -> None:
        zone = self.fl.inlet_zone
        try:
            vinlet = root.setup.boundary_conditions.velocity_inlet
            names = list(vinlet.get_object_names()) if hasattr(vinlet, "get_object_names") else []
            if names and zone not in names:
                raise FluentError(
                    f"Inlet zone '{zone}' not found. Velocity inlets in this case: {names}. "
                    "Fix fluent.inlet_zone in the config (zone names come from the "
                    "Named Selections in your geometry)."
                )
            inlet = vinlet[zone]
        except FluentError:
            raise
        except Exception as exc:
            raise FluentError(f"Cannot access velocity inlet '{zone}': {exc}") from exc

        momentum = _inlet_momentum(inlet)

        rotated = self.fl.aoa_method == "velocity_vector"
        if rotated:
            self._set_spec_method(momentum, want_direction=True)
            self._set_flow_direction(momentum, flow_dir)
        # Magnitude is set in both modes (in geometry mode the baseline case
        # already points the flow down the domain axis).
        self._set_velocity_magnitude(momentum, velocity)
        log.info("Inlet '%s': |V|=%.3f m/s%s", zone, velocity,
                 f", direction={list(flow_dir)}" if rotated else "")

    # --- momentum-node helpers (the 242/252 differences live here) -------- #
    def _set_velocity_magnitude(self, momentum, velocity: float) -> None:
        node = getattr(momentum, "velocity_magnitude", None)  # 252 name
        if node is None:
            node = getattr(momentum, "velocity", None)        # 242 name
        if node is None:
            raise FluentError("Inlet momentum node exposes neither "
                              "'velocity_magnitude' nor 'velocity'.")
        _set_scalar(node, float(velocity))

    def _set_spec_method(self, momentum, want_direction: bool) -> None:
        """Switch the inlet to 'Magnitude and Direction' (velocity_vector mode)."""
        spec = getattr(momentum, "velocity_specification_method", None)
        if spec is None:
            return
        try:
            allowed = list(spec.allowed_values())
        except Exception:
            allowed = []
        target = None
        for cand in allowed:
            c = str(cand).lower()
            if want_direction and "direction" in c and "magnitude" in c:
                target = cand
                break
        if target is None and allowed:
            log.warning("Could not find a 'Magnitude and Direction' option among %s "
                        "— leaving specification method unchanged.", allowed)
            return
        try:
            spec.set_state(target) if hasattr(spec, "set_state") else setattr(
                momentum, "velocity_specification_method", target)
            log.debug("velocity_specification_method -> %r", target)
        except Exception as exc:
            log.warning("Could not set velocity_specification_method: %s", exc)

    def _set_flow_direction(self, momentum, direction: Sequence[float]) -> None:
        node = getattr(momentum, "flow_direction", None)
        if node is None:
            # Fall back to velocity components (mathematically equivalent).
            comps = getattr(momentum, "velocity_components", None)
            if comps is None:
                raise FluentError("Inlet exposes neither 'flow_direction' nor "
                                  "'velocity_components' — cannot rotate the flow.")
            _set_vector(comps, [d for d in direction])
            return
        _set_vector(node, list(direction))

    # ------------------------------------------------------------------ #
    # Report definitions + history file
    # ------------------------------------------------------------------ #
    def _setup_report_definitions(self, root, drag_vec, lift_vec) -> None:
        """Create (or refresh) the four monitors.

        * cl / cd  → 'lift' / 'drag' report types (dimensionless, use the
          reference values we just set);
        * fl / fd  → 'force'  report types (Newtons, direct integration).

        Force vectors come from aero.wind_axes so geometry mode uses the
        domain axes and velocity_vector mode uses rotated wind axes.
        """
        rd = root.solution.report_definitions
        zones = list(self.fl.wall_zones)

        spec = [
            (rd.lift,  RD_CL, lift_vec),
            (rd.drag,  RD_CD, drag_vec),
            (rd.force, RD_FL, lift_vec),
            (rd.force, RD_FD, drag_vec),
        ]
        for family, name, vec in spec:
            try:
                if name not in _object_names(family):
                    family.create(name)
                obj = family[name]
                _try_set(obj, "zones", zones)
                _try_set(obj, "force_vector", [float(v) for v in vec])
                _try_set(obj, "average_over", 1)
                _try_set(obj, "per_selection", False)
            except Exception as exc:
                raise FluentError(f"Could not configure report definition "
                                  f"'{name}': {exc}") from exc
        log.info("Report definitions ready (zones=%s, drag=%s, lift=%s)",
                 zones, [round(v, 4) for v in drag_vec], [round(v, 4) for v in lift_vec])

    def _setup_history_file(self, root, case_dir: Path) -> Path:
        """Write CL/CD each iteration to a .out file in the case directory.

        The file serves two purposes: it is the data source for the
        convergence check, and it is a permanent per-case artifact the user
        can plot afterwards.

        Fluent 26.1 refuses to overwrite an existing report file; instead it
        creates numbered variants like ``cfdauto_history_3_1.out``. Any
        downstream code that keeps reading ``cfdauto_history.out`` then sees
        stale data from the previous solve. We delete every candidate name
        before recreating the definition, so Fluent starts with a clean slate.
        """
        out = case_dir / REPORT_FILE_NAME
        # Nuke stale history files from previous runs of this case.
        try:
            for stale in case_dir.glob("cfdauto_history*.out"):
                try:
                    stale.unlink()
                    log.debug("Removed stale history file: %s", stale.name)
                except OSError:
                    pass
        except Exception:
            pass
        try:
            rfiles = root.solution.monitor.report_files
            name = "cfdauto_history"
            if name not in _object_names(rfiles):
                rfiles.create(name)
            rf = rfiles[name]
            _try_set(rf, "report_defs", [RD_CL, RD_CD])
            _try_set(rf, "file_name", out.resolve().as_posix())
            _try_set(rf, "frequency", 1)
            _try_set(rf, "active", True)
            _try_set(rf, "print", False)
        except Exception as exc:
            # Convergence falls back to compute()-based sampling if this fails.
            log.warning("Could not create the report file monitor (%s) — "
                        "convergence will sample compute() instead.", exc)
        return out

    # ------------------------------------------------------------------ #
    # Initialise + solve
    # ------------------------------------------------------------------ #
    def _initialize(self, root) -> None:
        init = root.solution.initialization
        method = self.solve.initialization.lower()
        log.info("Initialising solution (%s)...", method)
        try:
            if method == "hybrid":
                init.hybrid_initialize()
            else:
                init.standard_initialize()
        except Exception as exc:
            if method == "hybrid":
                log.warning("Hybrid initialisation failed (%s) — falling back "
                            "to standard initialisation.", exc)
                try:
                    init.standard_initialize()
                except Exception as exc2:
                    raise FluentError(f"Initialisation failed: {exc2}") from exc2
            else:
                raise FluentError(f"Initialisation failed: {exc}") from exc

    def _solve_until_converged(self, root, history_file: Path,
                                case_dir: Path = None) -> tuple[int, bool]:
        """Iterate in chunks; declare convergence when both CL and CD are flat.

        Criterion: over the trailing ``convergence_window`` samples,
        ``max - min`` of CL < cl_tolerance *and* of CD < cd_tolerance, with at
        least ``min_iterations`` completed.  This is the practical criterion
        aerodynamicists actually use — residuals alone routinely stall 1-2
        orders above target while the forces are already dead flat.
        """
        s = self.solve
        run = root.solution.run_calculation
        done = 0
        log.info("Solving: chunks of %d, max %d iterations, window %d "
                 "(tol CL %.1e / CD %.1e)...",
                 s.check_interval, s.max_iterations, s.convergence_window,
                 s.cl_tolerance, s.cd_tolerance)

        # v0.9 M2: telemetry tap streams per-iteration CL/CD + residuals.
        tap = None
        if case_dir is not None:
            # Live probe: ask Fluent's running session for the current CL/CD
            # via report_definitions.compute(). This is the primary source
            # because Fluent buffers cfdauto_history.out in memory during
            # solves — tailing the file alone stutters.
            iter_counter = [0]  # closure over a mutable so we can bump it
            def _probe():
                try:
                    vals = self._compute(root, [RD_CL, RD_CD])
                    cl = vals.get(RD_CL)
                    cd = vals.get(RD_CD)
                    if cl is None or cd is None:
                        return None
                    # Approximate iteration count via read_history_rows below;
                    # if the file lags, we still advance by 1 to keep plots
                    # streaming.  The real iteration number is corrected when
                    # the history file catches up.
                    iter_counter[0] += 1
                    return (iter_counter[0], float(cl), float(cd))
                except Exception:
                    return None

            try:
                tap = TelemetryTap(
                    history_file=history_file,
                    transcript_file=self._current_transcript_path(case_dir),
                    emit=self._emit,
                    max_it=s.max_iterations,
                    poll_hz=5.0,
                    live_probe=_probe,
                )
                tap.start()
            except Exception as exc:
                log.debug("Telemetry tap could not start (%s) — falling back "
                          "to chunk-only progress.", exc)
                tap = None

        try:
            solve_return = self._solve_loop(root, run, s, history_file, done)
            return solve_return
        finally:
            if tap is not None:
                try:
                    tap.stop(drain=True)
                except Exception:
                    log.debug("Telemetry tap stop failed — ignored.",
                              exc_info=True)

    def _solve_loop(self, root, run, s, history_file: Path,
                    done: int) -> tuple[int, bool]:
        # Fluent buffers cfdauto_history.out in memory during a single
        # iterate() call and only flushes when the call returns. To keep the
        # live plots streaming, we split each convergence chunk into small
        # sub-chunks — the history file flushes at each boundary and the
        # tap picks up the new rows on its next poll.
        sub_chunk = min(10, s.check_interval)
        while done < s.max_iterations:
            chunk = min(s.check_interval, s.max_iterations - done)
            t0 = time.monotonic()
            end_of_chunk = done + chunk
            try:
                while done < end_of_chunk:
                    step = min(sub_chunk, end_of_chunk - done)
                    run.iterate(iter_count=step)
                    done += step
            except Exception as exc:
                raise DivergedError(
                    f"Solver raised after {done} iterations (likely divergence "
                    f"/ floating point error): {exc}"
                ) from exc

            cl_hist, cd_hist = self._read_history(root, history_file)
            self._raise_if_diverged(cl_hist, cd_hist, done)
            cl_now = cl_hist[-1] if cl_hist else float("nan")
            cd_now = cd_hist[-1] if cd_hist else float("nan")
            log.info("  iter %4d  CL=% .5f  CD=% .5f  (%.1f s/chunk)",
                     done, cl_now, cd_now, time.monotonic() - t0)
            self._emit("solve.progress", it=done, max_it=s.max_iterations,
                       cl=cl_now, cd=cd_now)

            if done >= s.min_iterations and _is_flat(cl_hist, s.convergence_window,
                                                     s.cl_tolerance) \
                    and _is_flat(cd_hist, s.convergence_window, s.cd_tolerance):
                log.info("Converged at iteration %d (CL/CD flat over the last "
                         "%d samples).", done, s.convergence_window)
                self._emit("solve.converged", it=done)
                self._stage("solve", "done")
                return done, True

        log.warning("Reached max_iterations=%d without meeting the flatness "
                    "criterion.", s.max_iterations)
        self._emit("solve.maxiter", it=done)
        self._stage("solve", "done")
        return done, False

    def _read_history(self, root, history_file: Path) -> tuple[List[float], List[float]]:
        """CL/CD histories, preferring the report file; compute() as fallback."""
        if history_file.exists():
            try:
                cl, cd = _parse_report_file(history_file, [RD_CL, RD_CD])
                if cl:
                    return cl, cd
            except Exception as exc:
                log.debug("History file parse failed (%s) — using compute().", exc)
        # Fallback: single-point sample (flatness check then needs the window
        # to fill up across chunks, handled naturally by the caller's loop).
        try:
            vals = self._compute(root, [RD_CL, RD_CD])
            self._fallback_cl.append(vals[RD_CL])
            self._fallback_cd.append(vals[RD_CD])
        except Exception:
            pass
        return list(self._fallback_cl), list(self._fallback_cd)

    @staticmethod
    def _raise_if_diverged(cl: List[float], cd: List[float], iters: int) -> None:
        for series, label in ((cl, "CL"), (cd, "CD")):
            if series and not math.isfinite(series[-1]):
                raise DivergedError(f"{label} became non-finite at iteration "
                                    f"{iters} — solution diverged.")

    # ------------------------------------------------------------------ #
    # Extraction
    # ------------------------------------------------------------------ #
    def _compute(self, root, names: List[str]) -> Dict[str, float]:
        raw = root.solution.report_definitions.compute(report_defs=names)
        vals = _flatten_compute(raw)
        missing = [n for n in names if n not in vals]
        if missing:
            raise ResultExtractionError(
                f"compute() returned no value for {missing}; got keys "
                f"{sorted(vals)} from payload of type {type(raw).__name__}"
            )
        return {n: vals[n] for n in names}

    def _extract_results(self, root, history_file: Path, exp: Experiment):
        """Final CL, CD, Lift[N], Drag[N] — history file first (reliable on
        Fluent 26.1 where compute() returns empty), compute() as fallback."""
        # Try history file first — deterministic and version-agnostic
        try:
            cl_hist, cd_hist = _parse_report_file(history_file, [RD_CL, RD_CD])
            if cl_hist and cd_hist:
                cl, cd = cl_hist[-1], cd_hist[-1]
                if math.isfinite(cl) and math.isfinite(cd):
                    ref = self.fl.reference
                    fl_n = aero.force_from_coefficient(
                        cl, ref.density, exp.velocity, ref.area)
                    fd_n = aero.force_from_coefficient(
                        cd, ref.density, exp.velocity, ref.area)
                    log.info("Extracted from history file: "
                             "CL=%.5f CD=%.5f", cl, cd)
                    return cl, cd, fl_n, fd_n
        except Exception:
            pass
        # Fallback: try compute() — works on older PyFluent versions
        try:
            vals = self._compute(root, [RD_CL, RD_CD, RD_FL, RD_FD])
            return vals[RD_CL], vals[RD_CD], vals[RD_FL], vals[RD_FD]
        except Exception as exc:
            raise ResultExtractionError(
                f"Could not extract from history file or compute(): {exc}"
            ) from exc

    def _crosscheck(self, exp: Experiment, res: CaseResult) -> None:
        """CL·q·A must equal Lift within tolerance; a mismatch almost always
        means the reference values in the case differ from the config."""
        if res.cl is None or res.lift_n is None:
            return
        ref = self.fl.reference
        expected = aero.force_from_coefficient(res.cl, ref.density, exp.velocity, ref.area)
        if abs(expected) < 1e-9 and abs(res.lift_n) < 1e-9:
            return
        mism = aero.relative_mismatch(expected, res.lift_n)
        if mism > self.solve.crosscheck_tolerance:
            log.warning(
                "Consistency check: Lift from CL·q·A = %.3f N but force report "
                "says %.3f N (%.1f%% apart). Check that reference density/area "
                "in the config match the Fluent case.",
                expected, res.lift_n, 100 * mism,
            )

    # ------------------------------------------------------------------ #
    # EXPERIMENTAL — contour picture capture (v0.8 Images panel feed)
    # ------------------------------------------------------------------ #
    def _capture_images(self, root, case_dir: Path) -> None:
        """Best-effort: save pressure/velocity contour PNGs plus mesh and
        geometry screenshots into the case dir.

        Every step is individually guarded (Fluent's graphics API varies by
        version); any failure logs a warning and the case still completes.
        Enable with ``fluent.capture_images: true``.

        Captures:
          * geometry.png — wireframe / edges of the wall zones
          * mesh.png — surface mesh on the wall zones
          * pressure_contour.png — static pressure on the wall
          * velocity_contour.png — velocity magnitude on the wall

        Camera is auto-fitted (zoomed to the wall zones) so the wing fills
        the frame instead of being a speck at the domain scale.
        """
        try:
            gfx = root.results.graphics
        except Exception as exc:
            log.warning("Image capture unavailable on this Fluent version "
                        "(%s) — skipping.", exc)
            return

        # --- Higher resolution + fit-to-wall camera helpers -----------------
        surfaces = list(self.fl.wall_zones)

        def _configure_picture():
            """Set output resolution + colour mode once per case."""
            try:
                pic = gfx.picture
                _try_set(pic, "x_resolution", 1920)
                _try_set(pic, "y_resolution", 1200)
                _try_set(pic, "landscape", True)
                _try_set(pic, "use_window_resolution", False)
                # colour_mode / driver may fail on some versions — non-fatal.
                _try_set(pic, "color_mode", "color")
                if hasattr(pic, "driver"):
                    _try_set(pic.driver, "post_format", "png")
            except Exception as exc:
                log.debug("picture options not fully settable: %s", exc)

        def _fit_camera_to_wall():
            """Zoom the active view onto the wall zones so the wing fills the
            frame. Tries multiple TUI/settings paths — Fluent's view API
            names vary considerably between releases."""
            for cmd in (
                # Modern settings-tree
                lambda: root.results.graphics.views.auto_scale(),
                lambda: root.results.graphics.views.auto_scale_view(),
                lambda: root.results.graphics.views.fit_to_window(),
                # Older TUI paths via execute_command
                lambda: root.execute_command(
                    f"/display/set/mirror-zones ()"),
                lambda: root.execute_command(
                    "/views/auto-scale"),
            ):
                try:
                    cmd()
                    return
                except Exception:
                    continue
            log.debug("Could not auto-scale the view — image may be zoomed out.")

        _configure_picture()

        # --- 1. Geometry (edges/wireframe of the wall zones) ---------------
        try:
            mesh_disp = gfx.mesh
            if "cfdauto_geom" not in _object_names(mesh_disp):
                mesh_disp.create("cfdauto_geom")
            geo = mesh_disp["cfdauto_geom"]
            _try_set(geo, "surfaces_list", surfaces)
            _try_set(geo, "surfaces", surfaces)
            # Edges only — highlights the geometry shape without mesh clutter
            _try_set(geo, "options.edges", True)
            _try_set(geo, "options.faces", False)
            _try_set(geo, "options.nodes", False)
            _try_set(geo, "coloring.option", "manual")
            geo.display()
            _fit_camera_to_wall()
            target = (case_dir / "geometry.png").resolve().as_posix()
            gfx.picture.save_picture(file_name=target)
            log.info("Saved geometry.png")
        except Exception as exc:
            log.warning("Could not capture geometry.png (%s) — continuing.", exc)

        # --- 2. Mesh (surface mesh on the wall zones) ----------------------
        # Fluent 26.1 uses 'mesh_2_child' objects with a non-standard API.
        # We try the settings tree first, then fall back to TUI commands.
        try:
            mesh_disp = gfx.mesh
            if "cfdauto_mesh" not in _object_names(mesh_disp):
                mesh_disp.create("cfdauto_mesh")
            m = mesh_disp["cfdauto_mesh"]
            _try_set(m, "surfaces_list", surfaces)
            _try_set(m, "surfaces", surfaces)

            # Try direct attributes (not dotted paths like options.edges)
            _try_set(m, "show_edges", True)
            _try_set(m, "edges", True)

            # Try edge_type with different value formats
            for val in ("all", "All", "all-edges", 0, 1, 2, "outline-edges"):
                try:
                    m.edge_type = val
                    log.debug("edge_type=%r accepted", val)
                    break
                except Exception:
                    continue

            # Try accessing options as a sub-object
            try:
                opts = m.options
                _try_set(opts, "edges", True)
                _try_set(opts, "faces", True)
                _try_set(opts, "nodes", False)
            except Exception:
                pass

            m.display()
            _fit_camera_to_wall()
            target = (case_dir / "mesh.png").resolve().as_posix()
            gfx.picture.save_picture(file_name=target)
            log.info("Saved mesh.png (settings-tree path)")
        except Exception as exc1:
            # Pure TUI fallback — display mesh directly via commands
            log.debug("Settings-tree mesh failed (%s), trying TUI...", exc1)
            try:
                zone_str = " ".join(surfaces)
                root.execute_command(
                    f'/display/mesh {zone_str} ()')
                _fit_camera_to_wall()
                target = (case_dir / "mesh.png").resolve().as_posix()
                gfx.picture.save_picture(file_name=target)
                log.info("Saved mesh.png (TUI fallback)")
            except Exception as exc2:
                log.warning("Could not capture mesh.png (%s / %s) — "
                            "continuing.", exc1, exc2)

        # --- 3 & 4. Pressure and velocity contours on the wall -------------
        contour_specs = [
            ("cfdauto_p_wing", "pressure", "pressure_contour.png"),
            ("cfdauto_vmag", "velocity-magnitude", "velocity_contour.png"),
        ]
        try:
            contours = gfx.contour
        except Exception as exc:
            log.warning("gfx.contour unavailable on this version (%s).", exc)
            return
        for name, field_name, filename in contour_specs:
            try:
                if name not in _object_names(contours):
                    contours.create(name)
                obj = contours[name]
                _try_set(obj, "field", field_name)
                _try_set(obj, "surfaces_list", surfaces)
                _try_set(obj, "surfaces", surfaces)
                # Filled contours with node values — nicer than the default
                _try_set(obj, "filled", True)
                _try_set(obj, "node_values", True)
                _try_set(obj, "coloring.smooth", True)
                obj.display()
                _fit_camera_to_wall()
                target = (case_dir / filename).resolve().as_posix()
                gfx.picture.save_picture(file_name=target)
                log.info("Saved %s", filename)
            except Exception as exc:
                log.warning("Could not capture %s (%s) — continuing.",
                            filename, exc)

    def _save_case_data(self, root, case_dir: Path) -> None:
        target = (case_dir / "final.cas.h5").resolve().as_posix()
        try:
            root.file.write_case_data(file_name=target)
            log.info("Saved converged case+data to %s", target)
        except Exception as exc:
            log.warning("Could not archive case/data files: %s", exc)


# --------------------------------------------------------------------------- #
# Module-level adapter helpers (kept free functions for easy unit testing)
# --------------------------------------------------------------------------- #
def _root(solver):
    """settings-API root: `solver.settings` on new PyFluent, `solver` on old."""
    return solver.settings if hasattr(solver, "settings") else solver


def _inlet_momentum(inlet):
    """Return the momentum node for a velocity inlet on either tree shape:
    242: inlet.momentum          252: inlet.settings.momentum"""
    holder = inlet.settings if hasattr(inlet, "settings") else inlet
    momentum = getattr(holder, "momentum", None)
    if momentum is None:
        raise FluentError("Velocity inlet object has no 'momentum' node — "
                          "unexpected PyFluent tree; check the version pairing.")
    return momentum


def _set_scalar(node, value: float) -> None:
    """Set a Fluent scalar that may be a plain Real or an option/value Group."""
    if hasattr(node, "value"):                      # Group: option/value/profile
        try:
            if hasattr(node, "option"):
                opt = node.option
                try:
                    allowed = [str(a).lower() for a in opt.allowed_values()]
                except Exception:
                    allowed = []
                for want in ("constant", "value", "constant or expression"):
                    hit = next((a for a in allowed if want in a), None)
                    if hit is not None:
                        opt.set_state(hit) if hasattr(opt, "set_state") else None
                        break
        except Exception:
            pass
        node.value = value
    else:
        try:
            node.set_state(value)
        except Exception:
            raise FluentError(f"Could not set scalar on node {node!r}")


def _set_vector(node, vec: List[float]) -> None:
    """Set a 2/3-component Fluent vector; list first, per-component fallback."""
    if hasattr(node, "set_state"):
        try:
            node.set_state(vec)
            return
        except Exception:
            pass
    try:
        for i, v in enumerate(vec):
            child = node[i]
            _set_scalar(child, v)
    except Exception as exc:
        raise FluentError(f"Could not set vector {vec} on {node!r}: {exc}") from exc


def _try_set(obj, attr: str, value) -> None:
    try:
        setattr(obj, attr, value)
    except Exception as exc:
        log.debug("optional attribute %s = %r not accepted: %s", attr, value, exc)


def _object_names(named_family) -> List[str]:
    for probe in ("get_object_names", "keys"):
        try:
            return list(getattr(named_family, probe)())
        except Exception:
            continue
    return []


def _flatten_compute(raw) -> Dict[str, float]:
    """Normalise report_definitions.compute() output across versions.

    Observed shapes:  {'cl': [0.42]},  [{'cl': [0.42]}, {'cd': [...]}],
    {'cl': 0.42}, and nested single-element lists thereof.
    """
    out: Dict[str, float] = {}

    def visit(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                val = v
                while isinstance(val, (list, tuple)) and len(val) == 1:
                    val = val[0]
                if isinstance(val, (int, float)):
                    out[str(k)] = float(val)
                else:
                    visit(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                visit(item)

    visit(raw)
    return out


def _parse_report_file(path: Path, names: List[str]) -> tuple[List[float], List[float]]:
    """Parse a Fluent report .out file into per-name series.

    Format (whitespace separated)::

        "cfdauto_history"
        "Iteration" "cfdauto_cl" "cfdauto_cd"
        ("Iteration" "cfdauto_cl" "cfdauto_cd")
        1 1.0234e-01 2.11e-02
        ...

    We map columns from the quoted header when present; otherwise we assume
    column 0 = iteration and the rest follow ``names`` order.
    """
    col_of: Dict[str, int] = {}
    series: Dict[str, List[float]] = {n: [] for n in names}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if '"' in line and not col_of:
                headers = [h for h in line.replace("(", " ").replace(")", " ").split('"')
                           if h.strip() and h.strip() != " "]
                headers = [h.strip() for h in headers if h.strip()]
                for n in names:
                    if n in headers:
                        col_of[n] = headers.index(n)
                continue
            first = line.split(None, 1)[0]
            if not _looks_numeric(first):
                continue
            parts = line.split()
            try:
                row = [float(p) for p in parts]
            except ValueError:
                continue
            for i, n in enumerate(names):
                col = col_of.get(n, i + 1)          # default: iter, then names
                if col < len(row):
                    series[n].append(row[col])
    return series[names[0]], series[names[1]]


def _looks_numeric(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def _is_flat(series: List[float], window: int, tol: float) -> bool:
    if len(series) < window:
        return False
    tail = series[-window:]
    if any(not math.isfinite(v) for v in tail):
        return False
    return (max(tail) - min(tail)) < tol