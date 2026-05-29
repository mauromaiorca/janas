"""
Tests for janas.janas_progress: progress.html generator.

Run::

    python tests/test_janas_progress.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
import types
from pathlib import Path
from typing import Callable, List, Tuple


HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
if os.path.isdir(SRC) and SRC not in sys.path:
    sys.path.insert(0, SRC)

if "janas.janas_core" not in sys.modules:
    sys.modules["janas.janas_core"] = types.ModuleType("janas.janas_core")

from janas import janas_progress as P  # noqa: E402


# ---------------------------------------------------------------------------
# Tiny session-dir factory
# ---------------------------------------------------------------------------


def _make_status(text_kwargs):
    lines = [
        "========================================",
        " JANAS Session Status",
        "========================================",
    ]
    for k, v in text_kwargs.items():
        lines.append(f" {k.capitalize()} : {v}")
    lines.append("========================================")
    return "\n".join(lines) + "\n"


def _make_session(tmp: Path, kind: str = "selection",
                  events=None, timings=None, status=None,
                  overview=None) -> Path:
    sd = tmp / "session_x"
    sd.mkdir(parents=True, exist_ok=True)
    if kind == "selection":
        (sd / "session_settings.toml").write_text("# settings\n", encoding="utf-8")
    elif kind == "classification":
        (sd / "session_classification_settings.txt").write_text(
            "# settings\n", encoding="utf-8"
        )
    if overview is not None:
        (sd / "overview.txt").write_text(overview, encoding="utf-8")
    rt = sd / "runtime"
    rt.mkdir(parents=True, exist_ok=True)
    if status is not None:
        (rt / "status.txt").write_text(_make_status(status), encoding="utf-8")
    if events is not None:
        with (rt / "events.ndjson").open("w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")
    if timings is not None:
        with (rt / "step_timings.csv").open("w", encoding="utf-8") as f:
            f.write("iteration,step,t_start,t_end,elapsed_s,rc\n")
            for r in timings:
                f.write(",".join(r) + "\n")
    return sd


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_step_to_phase_known_steps() -> None:
    assert P._step_to_phase("01_randomize_halves") == 1
    assert P._step_to_phase("02_bootstrap_reconstruct") == 1
    assert P._step_to_phase("03_score_particles") == 2
    assert P._step_to_phase("04_subsets") == 3
    assert P._step_to_phase("05_subset_reconstructions") == 3
    assert P._step_to_phase("06_locres") == 4
    assert P._step_to_phase("06_locres_bulk") == 4
    assert P._step_to_phase("07_locres_stats") == 4
    assert P._step_to_phase("08_get_num_particles") == 4


def test_step_to_phase_unknown() -> None:
    assert P._step_to_phase("99_unknown") is None
    assert P._step_to_phase("") is None


def test_pick_stage_unstarted() -> None:
    stage = P._pick_stage(events=[], status={}, session_kind="selection")
    assert stage["state"] == "unstarted"
    assert stage["image"] == "selection_unstarted.png"


def test_pick_stage_session_started_no_step_yet_uses_step1_image() -> None:
    # Only session_start has been emitted (script has been launched but the
    # first step_start has not been written yet). The dashboard must show
    # the preprocessing image, not the unstarted one.
    events = [
        {"event": "session_start", "iteration": "0", "status": "started"},
    ]
    stage = P._pick_stage(events, status={}, session_kind="selection")
    assert stage["state"] == "running"
    assert stage["image"] == "selection_step1.png"


def test_pick_stage_status_only_no_events_uses_step1_image() -> None:
    # status.txt has been written (init_runtime_logging called) but the
    # events file has not been flushed yet from the caller's point of
    # view. Treat as preprocessing, not unstarted.
    status = {"iteration": "0", "step": "init", "status": "starting"}
    stage = P._pick_stage(events=[], status=status, session_kind="selection")
    assert stage["state"] == "running"
    assert stage["image"] == "selection_step1.png"


def test_pick_stage_running_maps_step_to_image() -> None:
    events = [
        {"event": "session_start", "iteration": "0", "status": "started"},
        {"event": "step_start", "iteration": "1", "step": "03_score_particles",
         "status": "running", "t_start": "2026-05-28T02:00:00Z"},
    ]
    stage = P._pick_stage(events, status={}, session_kind="selection")
    assert stage["state"] == "running"
    assert stage["image"] == "selection_step2.png"
    assert stage["current_step"] == "03_score_particles"
    assert stage["current_iter"] == "1"


def test_pick_stage_finished() -> None:
    events = [
        {"event": "session_end", "status": "finished",
         "t_end": "2026-05-28T03:00:00Z"},
    ]
    stage = P._pick_stage(events, status={}, session_kind="selection")
    assert stage["state"] == "finished"
    assert stage["image"] == "selection_finished.png"


def test_pick_stage_aborted_uses_finished_image_with_aborted_state() -> None:
    events = [
        {"event": "session_end", "status": "aborted",
         "t_end": "2026-05-28T03:00:00Z"},
    ]
    stage = P._pick_stage(events, status={}, session_kind="selection")
    assert stage["state"] == "aborted"
    # Same picture but the badge state differentiates aborted from finished
    assert stage["image"] == "selection_finished.png"


def test_pick_stage_classification_has_no_image() -> None:
    events = [
        {"event": "step_start", "iteration": "1", "step": "03_score_particles",
         "status": "running", "t_start": "2026-05-28T02:00:00Z"},
    ]
    stage = P._pick_stage(events, status={}, session_kind="classification")
    assert stage["image"] == ""
    assert stage["state"] == "running"


def test_parse_status_txt() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = _make_session(
            Path(tmp), status={"Iteration": "3", "Step": "03_score_particles",
                               "Status": "running"},
        )
        st = P._parse_status_txt(sd / "runtime" / "status.txt")
        assert st["iteration"] == "3"
        assert st["step"] == "03_score_particles"
        assert st["status"] == "running"


def test_iter_events_skips_malformed_lines() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp) / "s"
        rt = sd / "runtime"
        rt.mkdir(parents=True, exist_ok=True)
        (rt / "events.ndjson").write_text(
            '{"event": "session_start"}\n'
            'this is not json\n'
            '{"event": "step_start", "step": "01_randomize_halves"}\n'
            '{"event": "step_end", "incomplete...\n',
            encoding="utf-8",
        )
        evs = P._iter_events(rt / "events.ndjson")
        assert len(evs) == 2
        assert evs[0]["event"] == "session_start"
        assert evs[1]["step"] == "01_randomize_halves"


def test_write_progress_html_creates_file_and_copies_images() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = _make_session(
            Path(tmp),
            kind="selection",
            status={"Iteration": "2", "Step": "03_score_particles",
                    "Status": "running", "Host": "test-host"},
            events=[
                {"event": "session_start", "iteration": "0",
                 "status": "started", "hostname": "test-host"},
                {"event": "step_start", "iteration": "2",
                 "step": "03_score_particles", "status": "running",
                 "t_start": "2026-05-28T02:00:00Z",
                 "hostname": "test-host", "slurm_job_id": "12345"},
            ],
            timings=[
                ("1", "01_randomize_halves",
                 "2026-05-28T01:00:00Z", "2026-05-28T01:00:05Z", "5", "0"),
                ("1", "02_bootstrap_reconstruct",
                 "2026-05-28T01:00:05Z", "2026-05-28T01:01:00Z", "55", "0"),
            ],
            overview="iter sigma nParticles meanResolution\n1 1.00 100000 3.5\n",
        )
        out = P.write_progress_html(sd, refresh_seconds=10, max_events=50)
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        # Sanity checks on the rendered HTML
        assert '<meta http-equiv="refresh" content="10">' in text
        assert "JANAS — session_x" in text or "session_x" in text
        assert "03_score_particles" in text
        assert "test-host" in text
        assert "12345" in text  # SLURM job
        assert "Scoring particles" in text
        assert "selection_step2.png" in text
        assert "01_randomize_halves" in text  # in timings table
        # Stage images were copied to runtime/imgs/
        imgs_dir = sd / "runtime" / "imgs"
        if P._PKG_IMAGES_DIR.is_dir():
            # In the dev tree the images ARE present; verify the copy
            assert (imgs_dir / "selection_step2.png").exists()


def test_write_progress_html_classification_session_text_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = _make_session(
            Path(tmp),
            kind="classification",
            events=[
                {"event": "session_start", "iteration": "0",
                 "status": "started"},
            ],
        )
        out = P.write_progress_html(sd)
        text = out.read_text(encoding="utf-8")
        assert "Type: classification" in text
        # No image filename should appear in the page for classification
        assert "selection_step" not in text
        assert "selection_unstarted.png" not in text
        assert "selection_finished.png" not in text


def test_atomic_write() -> None:
    """Re-writing must not leave a stray progress.html.tmp."""
    with tempfile.TemporaryDirectory() as tmp:
        sd = _make_session(Path(tmp))
        P.write_progress_html(sd)
        P.write_progress_html(sd)  # second call overwrites
        assert (sd / "progress.html").exists()
        assert not (sd / "progress.html.tmp").exists()


def test_html_is_escaped() -> None:
    """An injected '<' in events must not break the page."""
    with tempfile.TemporaryDirectory() as tmp:
        sd = _make_session(
            Path(tmp),
            events=[
                {"event": "step_start", "iteration": "1",
                 "step": "<script>alert('x')</script>",
                 "status": "running"},
            ],
        )
        out = P.write_progress_html(sd)
        text = out.read_text(encoding="utf-8")
        # The malicious step name must NOT appear verbatim as a tag
        assert "<script>alert('x')</script>" not in text
        # But its HTML-escaped form should
        assert "&lt;script&gt;" in text


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS: List[Tuple[str, Callable[[], None]]] = [
    ("step → phase: known steps map correctly", test_step_to_phase_known_steps),
    ("step → phase: unknown steps return None", test_step_to_phase_unknown),
    ("pick stage: unstarted by default", test_pick_stage_unstarted),
    ("pick stage: session_start only -> step1 (preprocessing)",
        test_pick_stage_session_started_no_step_yet_uses_step1_image),
    ("pick stage: status only (no events) -> step1 (preprocessing)",
        test_pick_stage_status_only_no_events_uses_step1_image),
    ("pick stage: running maps step to image", test_pick_stage_running_maps_step_to_image),
    ("pick stage: finished", test_pick_stage_finished),
    ("pick stage: aborted uses finished image with aborted badge",
        test_pick_stage_aborted_uses_finished_image_with_aborted_state),
    ("pick stage: classification has no image", test_pick_stage_classification_has_no_image),
    ("parse status.txt", test_parse_status_txt),
    ("iter_events skips malformed JSON lines", test_iter_events_skips_malformed_lines),
    ("write progress.html + copies stage images",
        test_write_progress_html_creates_file_and_copies_images),
    ("classification session: text-only HTML",
        test_write_progress_html_classification_session_text_only),
    ("atomic write leaves no .tmp file", test_atomic_write),
    ("HTML escapes injected step names", test_html_is_escaped),
]


def main() -> int:
    failed: List[str] = []
    for name, fn in TESTS:
        try:
            fn()
            print(f"[ OK ] {name}")
        except Exception as exc:  # noqa: BLE001
            failed.append(name)
            print(f"[FAIL] {name}: {exc}")
            traceback.print_exc(limit=4)
    print()
    if failed:
        print(f"{len(failed)}/{len(TESTS)} test(s) failed: {failed}")
        return 1
    print(f"All {len(TESTS)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
