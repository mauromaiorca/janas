# File: janas_progress.py
# (C) 2026 Mauro Maiorca - Leibniz Institute of Virology
#
# Generate a single ``progress.html`` page summarising the state of a JANAS
# session, from the artefacts produced by the run-script runtime-logging
# helpers (``runtime/events.ndjson``, ``runtime/status.txt``,
# ``runtime/step_timings.csv``) plus ``overview.txt`` from the iterative
# selection workflow.
#
# Invoked via ``janas_optimizer progress --session DIR`` (registered in
# ``janas_cmd_optimizer.py``) and also automatically from the run-script
# runtime-logging shell helpers, so the HTML stays fresh during the run.
#
# Design notes:
#   - Pure standard library; no JS, no external assets, works offline.
#   - Idempotent: re-running overwrites ``progress.html`` and reuses the
#     stage images already copied under ``runtime/imgs/``.
#   - Degrades gracefully when individual artefacts are missing (early in
#     the run, classification session without overview.txt, etc.).

from __future__ import annotations

import csv
import html
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Where the 6 selection stage PNGs ship inside the installed package.
_PKG_IMAGES_DIR = Path(__file__).parent / "images"

# Mapping from JANAS step name (the leading two-digit step index in the
# run-script) to the abstract phase 1..4, which selects which
# ``selection_step{N}.png`` is rendered. Order-sensitive: longer-prefix
# matches win because we evaluate prefixes in this order.
_STEP_TO_PHASE: List[Tuple[str, int]] = [
    ("01_randomize_halves", 1),
    ("02_bootstrap_reconstruct", 1),
    ("03_score_particles", 2),
    ("04_subsets", 3),
    ("04_", 3),
    ("05_subset_reconstructions", 3),
    ("05_", 3),
    ("06_locres", 4),
    ("06_", 4),
    ("07_locres_stats", 4),
    ("07_", 4),
    ("08_get_num_particles", 4),
    ("08_", 4),
]

# Image filenames bundled with the package.
_IMG_UNSTARTED = "selection_unstarted.png"
_IMG_FINISHED = "selection_finished.png"
_IMG_STEPS = {1: "selection_step1.png", 2: "selection_step2.png",
              3: "selection_step3.png", 4: "selection_step4.png"}

# Refresh cadence for the embedded <meta http-equiv="refresh">.
DEFAULT_REFRESH_SECONDS = 10

# Maximum number of recent events to render verbatim at the bottom of the
# page. Configurable from the CLI via ``--max-events``.
DEFAULT_MAX_EVENTS = 100


# ---------------------------------------------------------------------------
# Artefact parsers
# ---------------------------------------------------------------------------


def _parse_status_txt(path: Path) -> Dict[str, str]:
    """Parse the human-readable ``runtime/status.txt`` produced by
    ``write_runtime_status`` in the generated run script.

    Returns a dict with keys lowercased and stripped (e.g. ``"iteration"``,
    ``"step"``, ``"status"``, ``"started"``, ``"finished"``, ``"updated"``,
    ``"host"``). Empty dict if the file does not exist or cannot be read.
    """
    out: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return out
    except OSError:
        return out
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("=") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key and value:
            out[key] = value
    return out


def _iter_events(path: Path) -> List[Dict[str, Any]]:
    """Read ``runtime/events.ndjson`` line by line, skipping malformed lines.

    NDJSON files are append-only and may end mid-write while the run script
    is active; the last line might be partial. We tolerate that silently.
    """
    events: List[Dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    except OSError:
        return []
    return events


def _read_step_timings(path: Path) -> List[Dict[str, str]]:
    """Read ``runtime/step_timings.csv`` rows as a list of dicts (strings).

    Empty list if the file is missing or contains only the header.
    """
    rows: List[Dict[str, str]] = []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        return []
    except OSError:
        return []
    return rows


def _read_overview_text(path: Path) -> Optional[str]:
    """Return the raw text of ``overview.txt`` (or None if absent)."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError:
        return None


def _read_overview_data(path: Path) -> Dict[str, Any]:
    """
    Parse ``overview.txt`` (a TOML document) and return the bits the
    dashboard needs:

      - ``iterations``     : sorted list of iteration indices ``> 0``,
                             one entry per ``[[_janas_selection_N]]`` block
                             (the ``_janas_selection_0`` block, which
                             represents the full input dataset, is
                             excluded — it is the reference, not an
                             iteration).
      - ``target_iter``    : iteration index referenced by
                             ``selection_number`` in
                             ``[[_janas_target_selection]]`` (or None).
      - ``full_dataset_np``: ``reference_num_particles`` from
                             ``[[_janas_selection_0]]`` (or None).
      - ``target_np``      : ``reference_num_particles`` from
                             ``[[_janas_target_selection]]``, falling
                             back to the matching selection block if
                             absent (or None).

    Returns an empty dict on any read/parse error so the renderer can
    silently skip the new sections.
    """
    try:
        import toml as _toml  # noqa: WPS433 — third-party at function scope
    except ImportError:
        return {}
    try:
        data = _toml.load(str(path))
    except (FileNotFoundError, OSError):
        return {}
    except Exception:  # noqa: BLE001 — toml.TomlDecodeError + any wrapper
        return {}

    selections: Dict[int, Dict[str, Any]] = {}
    for key, val in data.items():
        m = re.match(r"_janas_selection_(\d+)$", key)
        if not m:
            continue
        idx = int(m.group(1))
        if isinstance(val, list) and val:
            row = val[0]
        elif isinstance(val, dict):
            row = val
        else:
            continue
        if isinstance(row, dict):
            selections[idx] = row

    iter_indices = sorted(i for i in selections if i > 0)

    target_block = data.get("_janas_target_selection")
    target: Optional[Dict[str, Any]] = None
    if isinstance(target_block, list) and target_block:
        if isinstance(target_block[0], dict):
            target = target_block[0]
    elif isinstance(target_block, dict):
        target = target_block

    target_iter: Optional[int] = None
    if target is not None:
        raw = target.get("selection_number")
        try:
            target_iter = int(raw)
        except (TypeError, ValueError):
            target_iter = None

    def _get_np(row: Optional[Dict[str, Any]]) -> Optional[int]:
        if not isinstance(row, dict):
            return None
        v = row.get("reference_num_particles")
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    full_dataset_np = _get_np(selections.get(0))
    target_np = _get_np(target) if target else None
    if target_np is None and target_iter is not None:
        target_np = _get_np(selections.get(target_iter))

    return {
        "iterations": iter_indices,
        "target_iter": target_iter,
        "full_dataset_np": full_dataset_np,
        "target_np": target_np,
    }


# ---------------------------------------------------------------------------
# Session-type detection + stage image selection
# ---------------------------------------------------------------------------


def _detect_session_kind(session_dir: Path) -> str:
    """Return ``"selection"``, ``"classification"`` or ``"unknown"``.

    Detection is purely file-based, so it works even when the session has
    only just started.
    """
    if (session_dir / "session_settings.toml").exists():
        return "selection"
    if (session_dir / "session_classification_settings.txt").exists():
        return "classification"
    # Selection sessions are the primary use case and the only ones that
    # currently produce overview.txt; treat that as a stronger hint.
    if (session_dir / "overview.txt").exists():
        return "selection"
    return "unknown"


def _step_to_phase(step_name: str) -> Optional[int]:
    """Map a JANAS step name to its phase number 1..4, or None on unknown."""
    if not step_name:
        return None
    s = str(step_name)
    for prefix, phase in _STEP_TO_PHASE:
        if s.startswith(prefix):
            return phase
    return None


def _pick_stage(
    events: List[Dict[str, Any]],
    status: Dict[str, str],
    session_kind: str,
) -> Dict[str, Any]:
    """Return a description of the current "stage" of the session.

    Keys returned:
      - ``image``     : filename under ``runtime/imgs/`` (or empty string
                        for classification, which has no images)
      - ``label``     : short human label, e.g. ``"Scoring particles"``
      - ``state``     : one of ``"unstarted" | "running" | "finished" |
                        "aborted"``
      - ``current_step`` : the most recent step name (best effort)
      - ``current_iter`` : iteration number as string
      - ``step_started`` : ISO timestamp of last step_start (or empty)
      - ``step_elapsed_s`` : seconds since step_started (int or None)
    """
    # Classification: text-only header, no image.
    image_for_phase = (lambda phase: "") if session_kind == "classification" \
        else (lambda phase: _IMG_STEPS.get(phase, _IMG_STEPS[1]))

    state = "unstarted"
    label = "Session not started"
    image = "" if session_kind == "classification" else _IMG_UNSTARTED
    current_step = ""
    current_iter = ""
    step_started = ""
    step_elapsed: Optional[int] = None

    if not events:
        # Fall back to status.txt if events are empty (very early in run).
        # Any signal that the session has actually started counts as
        # "preprocessing" (phase 1) — keeping the dashboard on the
        # 'unstarted' picture once the user has launched the script would
        # be misleading.
        if status:
            state = "running"
            label = _phase_label(1, "")
            image = image_for_phase(1)
            current_step = status.get("step", "")
            current_iter = status.get("iteration", "")
        return {
            "image": image,
            "label": label,
            "state": state,
            "current_step": current_step,
            "current_iter": current_iter,
            "step_started": step_started,
            "step_elapsed_s": step_elapsed,
        }

    last = events[-1]
    etype = last.get("event")
    estat = (last.get("status") or "").lower()

    if etype == "session_end":
        if estat == "finished":
            state = "finished"
            label = "Session finished"
            image = "" if session_kind == "classification" else _IMG_FINISHED
        else:
            state = "aborted"
            label = "Session aborted"
            image = "" if session_kind == "classification" else _IMG_FINISHED
    else:
        # Find the latest step_start for "currently running"
        last_step_start = next(
            (e for e in reversed(events) if e.get("event") == "step_start"),
            None,
        )
        state = "running"
        if last_step_start is not None:
            current_step = str(last_step_start.get("step") or "")
            current_iter = str(last_step_start.get("iteration") or "")
            step_started = str(last_step_start.get("t_start") or "")
            # If the most recent event is a step_end for this same step,
            # consider that step finished and label accordingly. Keep the
            # image of the just-completed phase: until the next step_start
            # arrives, the most informative picture is the one of the
            # last activity (otherwise the dashboard would briefly revert
            # to the unstarted picture between every step).
            if etype == "step_end" and last.get("step") == current_step:
                rc = str(last.get("rc") or "0")
                state = "running"
                label = f"Step done (rc={rc}), awaiting next"
                phase = _step_to_phase(current_step)
                if phase:
                    image = image_for_phase(phase)
            else:
                phase = _step_to_phase(current_step)
                label = _phase_label(phase, current_step)
                image = image_for_phase(phase) if phase else image

            # Compute elapsed from t_start to now (UTC)
            if step_started:
                try:
                    started_dt = datetime.fromisoformat(
                        step_started.replace("Z", "+00:00")
                    )
                    now = datetime.now(timezone.utc)
                    step_elapsed = int((now - started_dt).total_seconds())
                except (TypeError, ValueError):
                    step_elapsed = None
        else:
            # session_start has been emitted but no step_start yet: this is
            # still preprocessing (phase 1). Showing the 'unstarted'
            # picture once the user has actually launched the run would be
            # misleading.
            label = _phase_label(1, "")
            image = image_for_phase(1)

    return {
        "image": image,
        "label": label,
        "state": state,
        "current_step": current_step,
        "current_iter": current_iter,
        "step_started": step_started,
        "step_elapsed_s": step_elapsed,
    }


def _phase_label(phase: Optional[int], step_name: str) -> str:
    """Friendly label for a phase number, with fallback to the raw step name."""
    if phase == 1:
        return "Randomise + bootstrap reconstruction"
    if phase == 2:
        return "Scoring particles"
    if phase == 3:
        return "Reconstructing subsets"
    if phase == 4:
        return "Local resolution + decision"
    return f"Running step '{step_name}'" if step_name else "Running"


# ---------------------------------------------------------------------------
# Image copy
# ---------------------------------------------------------------------------


def _copy_stage_images(dest_dir: Path) -> None:
    """Copy the 6 stage PNGs from the package into ``dest_dir`` once.

    Idempotent: existing files are not re-copied (timestamps preserved).
    Silently no-op if the package images directory is missing (e.g. a
    truncated dev install).
    """
    if not _PKG_IMAGES_DIR.is_dir():
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(_PKG_IMAGES_DIR.glob("selection_*.png")):
        dest = dest_dir / src.name
        if not dest.exists():
            try:
                shutil.copyfile(src, dest)
            except OSError:
                # Best-effort: never crash the scientific run because we
                # could not refresh a status image.
                continue


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _esc(value: Any) -> str:
    """HTML-escape any value, treating None as the empty string."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _format_timing_rows(rows: List[Dict[str, str]], limit: int = 50) -> str:
    """Render the last ``limit`` step-timing rows as <tr> entries.

    Each row gets:
      - a parity class (``iter-odd``/``iter-even``) keyed off the iteration
        number, so adjacent iterations are visually banded in the table;
      - a rendered return-code cell of ``PASS (rc=0)`` (green) or
        ``FAIL (rc=N)`` (red), explained in the column header as
        "Return code".

    Non-numeric or missing iteration values are treated as even so they
    do not break the banding.
    """
    if not rows:
        return '<tr><td colspan="5" class="meta">No steps completed yet.</td></tr>'
    selected = rows[-limit:]
    out = []
    for r in selected:
        rc_raw = str(r.get("rc", "0")).strip()
        rc_ok = (rc_raw == "0")
        rc_cls = "rc-ok" if rc_ok else "rc-bad"
        rc_text = f"PASS (rc={rc_raw})" if rc_ok else f"FAIL (rc={rc_raw})"

        iter_raw = str(r.get("iteration", "")).strip()
        try:
            row_cls = "iter-odd" if (int(iter_raw) % 2 == 1) else "iter-even"
        except ValueError:
            row_cls = "iter-even"

        out.append(
            f"<tr class='{row_cls}'>"
            f"<td>{_esc(r.get('iteration', ''))}</td>"
            f"<td><code>{_esc(r.get('step', ''))}</code></td>"
            f"<td class='num'>{_esc(r.get('elapsed_s', ''))}</td>"
            f"<td class='{rc_cls}'>{_esc(rc_text)}</td>"
            f"<td class='meta'>{_esc(r.get('t_start', ''))}</td>"
            "</tr>"
        )
    return "\n".join(out)


def _format_recent_events(events: List[Dict[str, Any]], limit: int) -> str:
    """Render recent events as a fixed-pitch line list (newest at bottom)."""
    if not events:
        return "(no events yet)"
    selected = events[-limit:]
    lines: List[str] = []
    for e in selected:
        ts = str(e.get("timestamp") or "")
        etype = str(e.get("event") or "")
        ite = str(e.get("iteration") or "--")
        step = str(e.get("step") or "")
        status = str(e.get("status") or "")
        rc = e.get("rc")
        elapsed = e.get("elapsed_s")
        rc_part = f" rc={rc}" if rc is not None and rc != "" else ""
        el_part = f" elapsed={elapsed}s" if elapsed not in (None, "") else ""
        lines.append(
            f"[{ts}] {etype:<13} ite={ite} step={step} status={status}"
            f"{rc_part}{el_part}"
        )
    return _esc("\n".join(lines))


def _render_iterations_bar(overview_data: Dict[str, Any]) -> str:
    """Render the 'Iterations: 1 2 3' line under the stage image.

    Each iteration number is a <span class="iter-num">. The iteration
    indicated by ``selection_number`` in ``[[_janas_target_selection]]``
    additionally receives the ``current`` class, which the embedded CSS
    paints in green.
    """
    iterations = overview_data.get("iterations") or []
    if not iterations:
        return ""
    target_iter = overview_data.get("target_iter")
    spans = []
    for i in iterations:
        cls = "iter-num current" if i == target_iter else "iter-num"
        spans.append(f'<span class="{cls}">{int(i)}</span>')
    return (
        '<div class="iterations-line meta">'
        '<span class="iterations-label">Iterations:</span> '
        + "".join(spans)
        + "</div>"
    )


def _render_particle_counts(overview_data: Dict[str, Any]) -> str:
    """Render the 'Full dataset / Selection' particle-count line.

    Numbers are formatted with thousand separators. If neither value is
    available, returns the empty string so the calling template skips
    the block entirely.
    """
    full = overview_data.get("full_dataset_np")
    target = overview_data.get("target_np")
    parts: List[str] = []
    if full is not None:
        parts.append(f"Full dataset: <strong>{int(full):,}</strong> particles")
    if target is not None:
        parts.append(f"Selection: <strong>{int(target):,}</strong> particles")
    if not parts:
        return ""
    return (
        '<div class="meta particle-counts">'
        + " · ".join(parts)
        + "</div>"
    )


def _format_resources(events: List[Dict[str, Any]]) -> Dict[str, str]:
    """Pull resource info (host, SLURM, CUDA) from the most recent events
    that carry those keys.
    """
    out = {"hostname": "", "slurm_job_id": "", "slurm_nodelist": "",
           "cuda_devices": "", "slurm_cpus": ""}
    for e in reversed(events):
        for k in list(out.keys()):
            if not out[k]:
                v = e.get(k)
                if v:
                    out[k] = str(v)
        if all(out.values()):
            break
    return out


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
{refresh_meta}
<title>JANAS progress — {session_name}</title>
<style>
:root {{
  --fg: #1f2937; --bg: #f6f7f9; --card: #ffffff; --muted: #6b7280;
  --border: #e5e7eb; --accent: #0ea5e9; --ok: #16a34a;
  --warn: #d97706; --err: #dc2626;
}}
* {{ box-sizing: border-box; }}
body {{ font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI",
        Roboto, sans-serif; color: var(--fg); background: var(--bg);
        margin: 0; padding: 24px; }}
h1 {{ font-size: 22px; margin: 0 0 6px; }}
h2 {{ font-size: 15px; margin: 24px 0 8px; text-transform: uppercase;
       letter-spacing: 0.04em; color: var(--muted); }}
.meta {{ color: var(--muted); font-size: 12px; }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
          font-weight: 600; font-size: 12px; color: white;
          vertical-align: middle; }}
.badge.running   {{ background: var(--accent); }}
.badge.finished  {{ background: var(--ok); }}
.badge.aborted   {{ background: var(--err); }}
.badge.unstarted {{ background: var(--muted); }}
.grid {{ display: grid; gap: 16px; }}
.grid-2 {{ grid-template-columns: 1.4fr 1fr; }}
@media (max-width: 800px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
.card {{ background: var(--card); border: 1px solid var(--border);
         border-radius: 8px; padding: 16px; }}
.stage-img {{ max-width: 100%; height: auto; display: block;
              margin: 0 auto 12px; border-radius: 4px; }}
.stage-label {{ font-weight: 600; font-size: 16px; margin: 8px 0 4px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }}
th {{ background: #f9fafb; font-weight: 600; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.rc-ok {{ color: var(--ok); font-weight: 600; }}
td.rc-bad {{ color: var(--err); font-weight: 600; }}
tr.iter-odd  td {{ background: #f3f4f6; }}
tr.iter-even td {{ background: var(--card); }}
.iterations-line {{ margin: 8px 0 4px; font-variant-numeric: tabular-nums; }}
.iterations-label {{ font-weight: 600; color: var(--muted); }}
.iter-num {{ display: inline-block; min-width: 1.4em; padding: 1px 6px;
             margin: 0 2px; border-radius: 4px; text-align: center;
             color: var(--fg); background: transparent; }}
.iter-num.current {{ background: var(--ok); color: white; font-weight: 700; }}
.particle-counts {{ margin-top: 10px; padding-top: 8px;
                    border-top: 1px solid var(--border); }}
.particle-counts strong {{ color: var(--fg); }}
pre {{ background: #f3f4f6; padding: 12px; border-radius: 6px;
       overflow: auto; font-size: 12px; line-height: 1.4;
       max-height: 320px; }}
code {{ font-family: SFMono-Regular, Menlo, Consolas, monospace; }}
</style>
</head>
<body>

<h1>JANAS — {session_name} <span class="badge {state}">{state_text}</span></h1>
<p class="meta">Session directory: <code>{session_path}</code><br>
Type: {session_kind} · Generated: {generated_at}</p>

<div class="grid grid-2">
  <div class="card">
    <h2>Current stage</h2>
    {stage_image_html}
    {iterations_bar_html}
    <div class="stage-label">{stage_label}</div>
    <div class="meta">
      Iteration: <strong>{current_iter}</strong> ·
      Step: <code>{current_step}</code><br>
      Started: {step_started}{elapsed_str}
    </div>
    {particle_counts_html}
  </div>
  <div class="card">
    <h2>Runtime</h2>
    <table>
      <tr><th>Host</th><td>{host}</td></tr>
      <tr><th>SLURM job</th><td>{slurm_job}</td></tr>
      <tr><th>SLURM nodes</th><td>{slurm_nodes}</td></tr>
      <tr><th>SLURM CPUs</th><td>{slurm_cpus}</td></tr>
      <tr><th>CUDA devices</th><td>{cuda_devices}</td></tr>
    </table>
  </div>
</div>

<h2>Step timings ({n_timings} step{plural_t}, showing last {shown_t})</h2>
<div class="card">
<table>
<thead><tr>
  <th>Iter</th><th>Step</th><th class="num">Elapsed (s)</th>
  <th>Return code</th><th>Started (UTC)</th>
</tr></thead>
<tbody>
{timing_rows}
</tbody>
</table>
</div>

<h2>Iteration overview (overview.txt)</h2>
<div class="card">
{overview_block}
</div>

<h2>Recent events ({n_events_shown} of {n_events_total})</h2>
<div class="card"><pre>{recent_events}</pre></div>

<p class="meta" style="margin-top:24px">JANAS · progress.html · refreshed
every {refresh_seconds}s.</p>

</body>
</html>
"""


def _render_html(
    session_dir: Path,
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
    max_events: int = DEFAULT_MAX_EVENTS,
) -> str:
    """Render the full ``progress.html`` body for ``session_dir``."""
    runtime_dir = session_dir / "runtime"
    status = _parse_status_txt(runtime_dir / "status.txt")
    events = _iter_events(runtime_dir / "events.ndjson")
    timings = _read_step_timings(runtime_dir / "step_timings.csv")
    overview_text = _read_overview_text(session_dir / "overview.txt")
    overview_data = _read_overview_data(session_dir / "overview.txt")
    session_kind = _detect_session_kind(session_dir)

    stage = _pick_stage(events, status, session_kind)
    resources = _format_resources(events)
    iterations_bar_html = _render_iterations_bar(overview_data)
    particle_counts_html = _render_particle_counts(overview_data)

    refresh_meta = (
        f'<meta http-equiv="refresh" content="{int(refresh_seconds)}">'
        if refresh_seconds and int(refresh_seconds) > 0 else ""
    )

    if stage["image"]:
        stage_image_html = (
            f'<img class="stage-img" src="runtime/imgs/{_esc(stage["image"])}"'
            f' alt="{_esc(stage["label"])}">'
        )
    else:
        # Classification session: no image — show only the label
        stage_image_html = ""

    elapsed = stage.get("step_elapsed_s")
    elapsed_str = (
        f" · Elapsed: {int(elapsed)}s" if isinstance(elapsed, int) else ""
    )

    overview_block = (
        f"<pre>{_esc(overview_text.rstrip())}</pre>"
        if overview_text
        else '<p class="meta">No <code>overview.txt</code> in this session yet.</p>'
    )

    timing_rows = _format_timing_rows(timings, limit=50)
    n_shown = min(len(timings), 50)

    return _HTML_TEMPLATE.format(
        refresh_meta=refresh_meta,
        session_name=_esc(session_dir.name or str(session_dir)),
        state=stage["state"],
        state_text=stage["state"].upper(),
        session_path=_esc(str(session_dir.resolve())),
        session_kind=_esc(session_kind),
        generated_at=_esc(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ),
        stage_image_html=stage_image_html,
        iterations_bar_html=iterations_bar_html,
        particle_counts_html=particle_counts_html,
        stage_label=_esc(stage["label"]),
        current_iter=_esc(stage["current_iter"] or "--"),
        current_step=_esc(stage["current_step"] or "--"),
        step_started=_esc(stage["step_started"] or "--"),
        elapsed_str=_esc(elapsed_str),
        host=_esc(resources["hostname"] or "--"),
        slurm_job=_esc(resources["slurm_job_id"] or "--"),
        slurm_nodes=_esc(resources["slurm_nodelist"] or "--"),
        slurm_cpus=_esc(resources["slurm_cpus"] or "--"),
        cuda_devices=_esc(resources["cuda_devices"] or "--"),
        n_timings=len(timings),
        plural_t=("s" if len(timings) != 1 else ""),
        shown_t=n_shown,
        timing_rows=timing_rows,
        overview_block=overview_block,
        n_events_shown=min(len(events), max_events),
        n_events_total=len(events),
        recent_events=_format_recent_events(events, max_events),
        refresh_seconds=int(refresh_seconds) if refresh_seconds else 0,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_progress_html(
    session_dir: Path,
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
    max_events: int = DEFAULT_MAX_EVENTS,
) -> Path:
    """Generate ``session_dir/progress.html`` and copy stage images.

    Returns the absolute path of the written file. Best-effort: filesystem
    errors are propagated to the caller (the CLI wraps them so they cannot
    abort the scientific run script).
    """
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    # Only copy images for selection sessions to keep classification
    # output minimal. The HTML renderer also skips the image card for
    # classification, but copying here makes the page openable later
    # without a re-generation.
    if _detect_session_kind(session_dir) == "selection":
        _copy_stage_images(session_dir / "runtime" / "imgs")

    html_text = _render_html(
        session_dir,
        refresh_seconds=refresh_seconds,
        max_events=max_events,
    )
    out_path = session_dir / "progress.html"
    tmp_path = session_dir / "progress.html.tmp"
    # Write atomically so concurrent reads (from a browser auto-refresh)
    # never see a partial file.
    tmp_path.write_text(html_text, encoding="utf-8")
    os.replace(tmp_path, out_path)
    return out_path


def cmd_progress(args) -> int:
    """argparse handler for ``janas_optimizer progress``."""
    if args.session:
        session_dir = Path(args.session)
    elif args.overview:
        session_dir = Path(args.overview).parent
    else:
        session_dir = Path.cwd()

    if not session_dir.exists():
        print(
            f"janas_optimizer progress: session directory '{session_dir}' "
            "does not exist.",
            file=sys.stderr,
        )
        return 1

    try:
        out = write_progress_html(
            session_dir,
            refresh_seconds=args.refresh,
            max_events=args.max_events,
        )
    except OSError as exc:
        print(
            f"janas_optimizer progress: could not write progress.html "
            f"({exc.__class__.__name__}: {exc}).",
            file=sys.stderr,
        )
        return 1
    if args.quiet:
        return 0
    print(f"Wrote {out}")
    return 0
