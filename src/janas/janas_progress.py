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

# Refresh cadence for the embedded <meta http-equiv="refresh">. 15s is a
# good compromise: long enough to be cheap on the run-script hooks,
# short enough that the browser feels responsive. When the session has
# finished the meta tag is dropped entirely (see _render_html).
DEFAULT_REFRESH_SECONDS = 15

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

    def _get_starfile(row: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(row, dict):
            return None
        v = row.get("reference_starFile")
        return str(v) if v else None

    target_star = _get_starfile(target)
    if target_star is None and target_iter is not None:
        target_star = _get_starfile(selections.get(target_iter))

    return {
        "iterations": iter_indices,
        "target_iter": target_iter,
        "full_dataset_np": full_dataset_np,
        "target_np": target_np,
        "target_starfile": target_star,
        # Full contents of the [[_janas_target_selection]] block (or {} if
        # missing). The right-hand "Session info" card renders this as a
        # scrollable key/value table so the user can inspect everything
        # the optimiser is currently treating as the best selection.
        "target_block": target if isinstance(target, dict) else {},
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


def _format_elapsed_time(value: Any) -> str:
    """Render an elapsed-second count as ``X days, Y hours, Z mins, W secs``.

    The numeric portion of each unit is wrapped in an aligned <span> so
    successive rows visually line up: the digits are right-aligned within
    a fixed-width inline-block of tabular-numeral text, and the unit
    labels follow immediately. Missing or non-integer values render as
    the literal ``--``.
    """
    try:
        total = int(float(str(value)))
    except (TypeError, ValueError):
        return '<span class="meta">--</span>'
    if total < 0:
        total = 0
    days, rem = divmod(total, 86_400)
    hours, rem = divmod(rem, 3_600)
    mins, secs = divmod(rem, 60)
    return (
        f'<span class="elapsed-num">{days}</span> days, '
        f'<span class="elapsed-num">{hours}</span> hours, '
        f'<span class="elapsed-num">{mins}</span> mins, '
        f'<span class="elapsed-num">{secs}</span> secs'
    )


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
            f"<td class='elapsed-cell'>"
            f"{_format_elapsed_time(r.get('elapsed_s', ''))}</td>"
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


def _starfile_relative_to_session(
    reference_star: Optional[str],
    session_dir: Path,
) -> Optional[str]:
    """
    Convert a ``reference_starFile`` value as found in ``overview.txt``
    into a path relative to the directory of ``progress.html`` itself
    (so the rendered ``<a href>`` works equally well over file:// and
    over ``python -m http.server``).

    overview.txt is written from one level above the session directory
    by the run script (see ``janas_cmd_session_manager``), so paths in
    ``reference_starFile`` typically start with the session-dir name:

        janas_selection_example/<tag>/best.star

    progress.html lives at ``janas_selection_example/progress.html``,
    so the leading ``janas_selection_example/`` must be stripped to
    obtain a usable relative href: ``<tag>/best.star``.

    Backslashes are normalised to forward slashes. Absolute paths and
    paths that do not start with the session name are returned
    unchanged. Returns None for empty/None inputs.
    """
    if not reference_star:
        return None
    s = str(reference_star).replace("\\", "/").strip()
    if not s:
        return None
    # Absolute paths are taken at face value
    if s.startswith("/"):
        return s
    name = session_dir.name
    if name and s.startswith(name + "/"):
        return s[len(name) + 1:]
    return s


def _render_particle_counts(
    overview_data: Dict[str, Any],
    session_dir: Path,
) -> str:
    """Render the 'Full dataset / Selection' particle-count block.

    When the target selection carries a ``reference_starFile``, append
    a clickable link below the counts. The link path is made relative
    to the directory of ``progress.html`` (see
    :func:`_starfile_relative_to_session`); the link text is the
    basename only, to keep the line compact.

    Numbers are rendered with thousand separators. If neither count
    nor link is available, returns the empty string so the calling
    template skips the block entirely.
    """
    full = overview_data.get("full_dataset_np")
    target = overview_data.get("target_np")
    star_rel = _starfile_relative_to_session(
        overview_data.get("target_starfile"), session_dir
    )

    parts: List[str] = []
    if full is not None:
        parts.append(f"Full dataset: <strong>{int(full):,}</strong> particles")
    if target is not None:
        parts.append(f"Selection: <strong>{int(target):,}</strong> particles")

    if not parts and not star_rel:
        return ""

    out = '<div class="meta particle-counts">'
    if parts:
        out += " · ".join(parts)
    if star_rel:
        basename = star_rel.rsplit("/", 1)[-1] or star_rel
        link = (
            f'<a class="star-link" href="{_esc(star_rel)}" '
            f'title="{_esc(star_rel)}">{_esc(basename)}</a>'
        )
        if parts:
            out += '<br><span class="star-link-row">Selection STAR file: ' + link + "</span>"
        else:
            out += '<span class="star-link-row">Selection STAR file: ' + link + "</span>"
    out += "</div>"
    return out


def _render_target_selection_table(target_block: Dict[str, Any]) -> str:
    """Render the contents of ``[[_janas_target_selection]]`` as a small
    key/value table. Long string values (paths) word-break to keep the
    layout from blowing up; the whole table is wrapped in a scrollable
    container by the calling template so a tall selection record does
    not push the rest of the right-hand card off-screen.
    """
    if not target_block:
        return '<p class="meta">No <code>[[_janas_target_selection]]</code> block yet.</p>'
    rows: List[str] = []
    for key in sorted(target_block.keys()):
        rows.append(
            "<tr>"
            f'<th class="k">{_esc(key)}</th>'
            f'<td class="v">{_format_settings_value(target_block[key])}</td>'
            "</tr>"
        )
    return (
        '<div class="scroll-area"><table class="kv-table"><tbody>'
        + "\n".join(rows)
        + "</tbody></table></div>"
    )


def _extract_hostname(events: List[Dict[str, Any]]) -> str:
    """Pull the hostname from the most recent event that carries it.

    SLURM (job/nodes/CPUs) and CUDA_VISIBLE_DEVICES values used to be
    surfaced too, but JANAS does not currently integrate with the
    cluster scheduler, so they were silently empty on most installs and
    were removed from the dashboard. They are still written to
    ``events.ndjson`` and can be read by external tools if needed.
    """
    for e in reversed(events):
        v = e.get("hostname")
        if v:
            return str(v)
    return ""


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
.stage-img {{ max-width: 360px; width: 100%; height: auto; display: block;
              margin: 0 auto 12px; border-radius: 4px; }}
.card-subhead {{ font-size: 13px; margin: 12px 0 6px; color: var(--muted);
                 text-transform: uppercase; letter-spacing: 0.04em;
                 font-weight: 600; }}
.scroll-area {{ max-height: 260px; overflow-y: auto;
                border: 1px solid var(--border); border-radius: 6px;
                padding: 0 8px; }}
.kv-table th.k {{ width: 42%; color: var(--muted); font-weight: 600;
                  font-family: SFMono-Regular, Menlo, Consolas, monospace; }}
.kv-table td.v {{ font-family: SFMono-Regular, Menlo, Consolas, monospace;
                  word-break: break-all; }}
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
.star-link {{ color: var(--accent); text-decoration: none;
              font-family: SFMono-Regular, Menlo, Consolas, monospace;
              font-size: 12px; word-break: break-all; }}
.star-link:hover {{ text-decoration: underline; }}
.star-link-row {{ display: inline-block; margin-top: 4px; }}
th.elapsed-col {{ text-align: center; }}
td.elapsed-cell {{ text-align: left; white-space: nowrap;
                   font-variant-numeric: tabular-nums; }}
.elapsed-num {{ display: inline-block; min-width: 1.6em;
                text-align: right; font-variant-numeric: tabular-nums; }}
pre {{ background: #f3f4f6; padding: 12px; border-radius: 6px;
       overflow: auto; font-size: 12px; line-height: 1.4;
       max-height: 320px; }}
code {{ font-family: SFMono-Regular, Menlo, Consolas, monospace; }}
</style>
</head>
<body>

<h1>JANAS — {session_name} <span class="badge {state}">{state_text}</span></h1>
<p class="meta">Session directory: <code>{session_path}</code>{settings_link_html}</p>

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
    <h2>Session info</h2>
    <p class="meta">
      Type: <strong>{session_kind}</strong> ·
      Host: <strong>{host}</strong><br>
      Generated: {generated_at}
    </p>
    <h3 class="card-subhead">Target selection (<code>[[_janas_target_selection]]</code>)</h3>
    {target_selection_html}
  </div>
</div>

<h2>Step timings ({n_timings} step{plural_t}, showing last {shown_t})</h2>
<div class="card">
<table>
<thead><tr>
  <th>Iter</th><th>Step</th><th class="elapsed-col">Elapsed time</th>
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

<p class="meta" style="margin-top:24px">JANAS · progress.html · {footer_refresh_text}</p>

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
    hostname = _extract_hostname(events)
    iterations_bar_html = _render_iterations_bar(overview_data)
    particle_counts_html = _render_particle_counts(overview_data, session_dir)
    target_selection_html = _render_target_selection_table(
        overview_data.get("target_block") or {}
    )

    # Settings link in the header — points to the user-friendly
    # settings.html when it has been generated, otherwise hidden.
    settings_link_html = ""
    if (session_dir / "settings.html").exists():
        settings_link_html = (
            '<br>Settings: <a href="settings.html">session_settings</a>'
        )
    elif (session_dir / "session_settings.toml").exists():
        # No HTML render available yet but the TOML is on disk — link to it
        # raw so the user always has something clickable.
        settings_link_html = (
            '<br>Settings: <a href="session_settings.toml">'
            'session_settings.toml</a>'
        )

    # Drop the auto-refresh once the session is finished: nothing more
    # will be appended to the runtime artefacts so there is no point in
    # making the browser reload. Aborted sessions still refresh because
    # the user might restart in place and the dashboard would then need
    # to pick up the new session_start event.
    if refresh_seconds and int(refresh_seconds) > 0 and stage["state"] != "finished":
        refresh_meta = f'<meta http-equiv="refresh" content="{int(refresh_seconds)}">'
    else:
        refresh_meta = ""

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
        settings_link_html=settings_link_html,
        target_selection_html=target_selection_html,
        stage_label=_esc(stage["label"]),
        current_iter=_esc(stage["current_iter"] or "--"),
        current_step=_esc(stage["current_step"] or "--"),
        step_started=_esc(stage["step_started"] or "--"),
        elapsed_str=_esc(elapsed_str),
        host=_esc(hostname or "--"),
        n_timings=len(timings),
        plural_t=("s" if len(timings) != 1 else ""),
        shown_t=n_shown,
        timing_rows=timing_rows,
        overview_block=overview_block,
        n_events_shown=min(len(events), max_events),
        n_events_total=len(events),
        recent_events=_format_recent_events(events, max_events),
        footer_refresh_text=(
            "session finished, auto-refresh disabled"
            if stage["state"] == "finished"
            else (
                f"refreshed every {int(refresh_seconds)}s"
                if refresh_seconds and int(refresh_seconds) > 0
                else "auto-refresh disabled"
            )
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# settings.html — once-per-session view of session_settings.toml
# ---------------------------------------------------------------------------


_SETTINGS_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>JANAS settings — {session_name}</title>
<style>
:root {{
  --fg: #1f2937; --bg: #f6f7f9; --card: #ffffff; --muted: #6b7280;
  --border: #e5e7eb; --accent: #0ea5e9;
}}
* {{ box-sizing: border-box; }}
body {{ font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI",
        Roboto, sans-serif; color: var(--fg); background: var(--bg);
        margin: 0; padding: 24px; }}
h1 {{ font-size: 22px; margin: 0 0 6px; }}
h2 {{ font-size: 14px; margin: 24px 0 8px; text-transform: uppercase;
       letter-spacing: 0.04em; color: var(--muted); }}
.meta {{ color: var(--muted); font-size: 12px; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.card {{ background: var(--card); border: 1px solid var(--border);
         border-radius: 8px; padding: 16px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ text-align: left; padding: 6px 8px;
          border-bottom: 1px solid var(--border);
          vertical-align: top; }}
th.k {{ width: 28%; color: var(--muted); font-weight: 600;
        font-family: SFMono-Regular, Menlo, Consolas, monospace; }}
td.v {{ font-family: SFMono-Regular, Menlo, Consolas, monospace;
        word-break: break-all; }}
.bool-true  {{ color: #16a34a; font-weight: 600; }}
.bool-false {{ color: #dc2626; font-weight: 600; }}
pre {{ background: #f3f4f6; padding: 12px; border-radius: 6px;
       overflow: auto; font-size: 12px; line-height: 1.4;
       max-height: 480px; }}
</style>
</head>
<body>

<h1>JANAS settings — {session_name}</h1>
<p class="meta">Settings file: <code>{settings_path}</code><br>
Generated: {generated_at} ·
<a href="progress.html">&larr; Back to progress</a></p>

<h2>Parameters</h2>
<div class="card">
<table>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<h2>Raw TOML</h2>
<div class="card"><pre>{raw_toml}</pre></div>

</body>
</html>
"""


def _format_settings_value(v: Any) -> str:
    """Format a single TOML value for display in the settings table."""
    if isinstance(v, bool):
        cls = "bool-true" if v else "bool-false"
        return f'<span class="{cls}">{str(v).lower()}</span>'
    if isinstance(v, (list, tuple)):
        if not v:
            return '<span class="meta">(empty list)</span>'
        return _esc(", ".join(str(x) for x in v))
    if isinstance(v, dict):
        # Nested table: render as a small inline key/value list
        if not v:
            return '<span class="meta">(empty table)</span>'
        items = "; ".join(f"{_esc(str(k))} = {_esc(str(val))}" for k, val in v.items())
        return items
    if v is None or v == "":
        return '<span class="meta">--</span>'
    return _esc(str(v))


def _render_settings_html(
    settings_path: Path,
    session_name: str,
) -> str:
    """Render ``settings.html`` for a single ``session_settings.toml`` file."""
    try:
        import toml as _toml  # noqa: WPS433
    except ImportError:
        return ""
    try:
        data = _toml.load(str(settings_path))
    except (FileNotFoundError, OSError):
        return ""
    except Exception:  # noqa: BLE001 — toml.TomlDecodeError + wrappers
        # Fall back to a raw <pre> rendering so the user still sees content
        try:
            raw = settings_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        rows_html = (
            '<tr><td colspan="2" class="meta">Could not parse TOML; '
            "showing raw contents only.</td></tr>"
        )
        return _SETTINGS_HTML_TEMPLATE.format(
            session_name=_esc(session_name),
            settings_path=_esc(str(settings_path.resolve())),
            generated_at=_esc(
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ),
            rows_html=rows_html,
            raw_toml=_esc(raw),
        )

    rows: List[str] = []
    for key in sorted(data.keys()):
        rows.append(
            "<tr>"
            f'<th class="k">{_esc(key)}</th>'
            f'<td class="v">{_format_settings_value(data[key])}</td>'
            "</tr>"
        )
    rows_html = "\n".join(rows) if rows else (
        '<tr><td colspan="2" class="meta">No keys in this settings file.</td></tr>'
    )

    try:
        raw = settings_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raw = ""

    return _SETTINGS_HTML_TEMPLATE.format(
        session_name=_esc(session_name),
        settings_path=_esc(str(settings_path.resolve())),
        generated_at=_esc(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ),
        rows_html=rows_html,
        raw_toml=_esc(raw),
    )


def write_settings_html(session_dir: Path, force: bool = False) -> Optional[Path]:
    """Generate ``session_dir/settings.html`` once per session.

    ``session_settings.toml`` is written once by ``janas_session_manager``
    when the session is created and never modified during the run, so by
    default this function is **idempotent**: it returns the existing path
    and does nothing if ``settings.html`` is already there. Pass
    ``force=True`` to overwrite (used by tests).

    Returns the path of the generated file, or None when there is no
    ``session_settings.toml`` to render.
    """
    session_dir = Path(session_dir)
    settings_toml = session_dir / "session_settings.toml"
    if not settings_toml.exists():
        return None

    out_path = session_dir / "settings.html"
    if out_path.exists() and not force:
        return out_path

    html_text = _render_settings_html(settings_toml, session_dir.name)
    if not html_text:
        return None

    tmp_path = session_dir / "settings.html.tmp"
    tmp_path.write_text(html_text, encoding="utf-8")
    os.replace(tmp_path, out_path)
    return out_path


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

    # Generate settings.html once per session (idempotent). Done before
    # rendering progress.html so the header can link to settings.html
    # rather than to the raw .toml on the very first invocation.
    try:
        write_settings_html(session_dir)
    except Exception:  # noqa: BLE001
        # Best-effort: never abort the dashboard generator because of a
        # secondary artefact.
        pass

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
