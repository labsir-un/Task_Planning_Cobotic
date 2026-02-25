#!/usr/bin/env python3
"""
Analyze one experiment run folder (e.g., LogsExp/logs2) using the user's timing definitions.

Human time (from nlp.log):
  - setup time:        NLP module start -> "start" command
  - attention time:    "Robot will move..." prompt -> "go" command
  - execution time:    "Please move..." prompt -> "done" or "space" command
  - maintenance time:  "An error occurred..." prompt -> "fixed" command

Robot time (reported as agent time):
  - planning time:     planner "building PDDL problem..." -> planner "planner returned ..." (or plan_failed)
  - move-object time:  ABB "move ..." command -> ABB response
  - home time:         ABB "XXXXX" command -> ABB response

Outputs:
  - total time
  - total human time
  - total robot time
  - fan-out proxies (with and without setup time)
  - timeline graph (who is acting vs time)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


LOG_LINE_RE = re.compile(r"\[(INFO|ERROR|WARN)\] \[(\d+\.\d+)\] \[([^\]]+)\]: (.*)")


@dataclass
class Event:
    ts: float
    level: str
    node: str
    msg: str


@dataclass
class Interval:
    start: float
    end: float
    actor: str  # "human" | "agent"
    kind: str
    source: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def parse_log(path: Path) -> List[Event]:
    events: List[Event] = []
    if not path.exists():
        return events
    for line in path.read_text(errors="ignore").splitlines():
        m = LOG_LINE_RE.search(line)
        if not m:
            continue
        events.append(Event(ts=float(m.group(2)), level=m.group(1), node=m.group(3), msg=m.group(4)))
    return events


def find_last_index(events: Sequence[Event], pred) -> Optional[int]:
    for i in range(len(events) - 1, -1, -1):
        if pred(events[i]):
            return i
    return None


def find_next_index(events: Sequence[Event], start_idx: int, pred) -> Optional[int]:
    for i in range(start_idx, len(events)):
        if pred(events[i]):
            return i
    return None


def next_matching_event(events: Sequence[Event], start_idx: int, pred) -> Tuple[Optional[int], Optional[Event]]:
    idx = find_next_index(events, start_idx, pred)
    if idx is None:
        return None, None
    return idx, events[idx]


def detect_session_bounds(nlp_events: Sequence[Event], planner_events: Sequence[Event], all_events: Sequence[Event]) -> Tuple[float, float]:
    # Session starts at the last emitted "start" command in NLP.
    start_idx = find_last_index(nlp_events, lambda e: "WRITE /nlp/out: start" in e.msg)
    if start_idx is None:
        raise RuntimeError("Could not find session start token in nlp.log (WRITE /nlp/out: start).")
    t_start = nlp_events[start_idx].ts

    # End at planner complete if available after start; otherwise last event after start across logs.
    complete_idx = find_next_index(planner_events, 0, lambda e: e.ts >= t_start and "planner/out: complete" in e.msg)
    if complete_idx is not None:
        t_end = planner_events[complete_idx].ts
    else:
        candidates = [e.ts for e in all_events if e.ts >= t_start]
        if not candidates:
            raise RuntimeError("No events found after session start.")
        t_end = max(candidates)
    return t_start, t_end


def detect_system_start_before_session(
    t_start: float,
    nlp_events: Sequence[Event],
    planner_events: Sequence[Event],
    abb_events: Sequence[Event],
) -> float:
    candidates: List[float] = []

    idx = find_last_index(nlp_events, lambda e: e.ts <= t_start and "NLP module started." in e.msg)
    if idx is not None:
        candidates.append(nlp_events[idx].ts)

    idx = find_last_index(planner_events, lambda e: e.ts <= t_start and "Planner module started." in e.msg)
    if idx is not None:
        candidates.append(planner_events[idx].ts)

    idx = find_last_index(abb_events, lambda e: e.ts <= t_start and "ABB module started." in e.msg)
    if idx is not None:
        candidates.append(abb_events[idx].ts)

    return min(candidates) if candidates else t_start


def clip_events(events: Sequence[Event], t0: float, t1: float) -> List[Event]:
    return [e for e in events if t0 <= e.ts <= t1]


def pair_intervals(
    events: Sequence[Event],
    start_pred,
    end_pred,
    actor: str,
    kind: str,
    source: str,
) -> List[Interval]:
    intervals: List[Interval] = []
    i = 0
    while i < len(events):
        if not start_pred(events[i]):
            i += 1
            continue
        start_event = events[i]
        j, end_event = next_matching_event(events, i + 1, end_pred)
        if end_event is None:
            i += 1
            continue
        intervals.append(Interval(start=start_event.ts, end=end_event.ts, actor=actor, kind=kind, source=source))
        i = (j or i) + 1
    return intervals


def pair_abb_intervals(abb_events: Sequence[Event]) -> Tuple[List[Interval], List[Interval]]:
    move_intervals: List[Interval] = []
    home_intervals: List[Interval] = []
    i = 0
    while i < len(abb_events):
        e = abb_events[i]
        if "READ /abb/in:" not in e.msg:
            i += 1
            continue
        cmd = e.msg.split("READ /abb/in: ", 1)[1].strip()
        j, out_e = next_matching_event(
            abb_events,
            i + 1,
            lambda x: "WRITE /abb/out:" in x.msg,
        )
        if out_e is None:
            i += 1
            continue
        if cmd == "XXXXX":
            home_intervals.append(Interval(e.ts, out_e.ts, "agent", "home", "abb.log"))
        elif cmd.startswith("move "):
            move_intervals.append(Interval(e.ts, out_e.ts, "agent", "move", "abb.log"))
        i = (j or i) + 1
    return move_intervals, home_intervals


def pair_planning_intervals(planner_events: Sequence[Event]) -> List[Interval]:
    intervals: List[Interval] = []
    i = 0
    while i < len(planner_events):
        e = planner_events[i]
        if "PROCESS building PDDL problem and requesting plan." not in e.msg:
            i += 1
            continue
        j, end_e = next_matching_event(
            planner_events,
            i + 1,
            lambda x: ("PROCESS planner returned" in x.msg) or ("planner/out: plan_failed" in x.msg),
        )
        if end_e is None:
            i += 1
            continue
        intervals.append(Interval(e.ts, end_e.ts, "agent", "planning", "planner.log"))
        i = (j or i) + 1
    return intervals


def summarize(intervals: Iterable[Interval]) -> float:
    return sum(iv.duration for iv in intervals)


def mean_duration(intervals: Iterable[Interval]) -> Optional[float]:
    vals = [iv.duration for iv in intervals]
    if not vals:
        return None
    return sum(vals) / len(vals)


def format_seconds(s: float) -> str:
    return f"{s:.3f} s"


def pair_prompt_speech_intervals(nlp_events: Sequence[Event]) -> List[Interval]:
    """
    Approximate prompt speech duration.

    For actionable prompts (those expecting user response), use:
      READ /nlp/in: <prompt> -> next "PROCESS listening for user input..."

    For non-actionable prompts, fallback to:
      READ /nlp/in: <prompt> -> next NLP event

    This is assigned to the agent.
    """
    intervals: List[Interval] = []
    i = 0
    while i < len(nlp_events):
        e = nlp_events[i]
        if "READ /nlp/in:" not in e.msg:
            i += 1
            continue
        prompt_text = e.msg.split("READ /nlp/in: ", 1)[1]
        actionable = (
            prompt_text.startswith("Robot will move ")
            or prompt_text.startswith("Please move ")
            or prompt_text.startswith("An error occurred")
        )
        if actionable:
            j, end_e = next_matching_event(
                nlp_events,
                i + 1,
                lambda x: "PROCESS listening for user input..." in x.msg,
            )
        else:
            j, end_e = next_matching_event(nlp_events, i + 1, lambda x: True)
        if end_e is None:
            i += 1
            continue
        intervals.append(Interval(e.ts, end_e.ts, "agent", "prompt_speech", "nlp.log"))
        i = (j or i) + 1
    return intervals


def pair_human_response_after_prompt_speech(
    nlp_events: Sequence[Event],
    prompt_prefix: str,
    valid_outputs: Tuple[str, ...],
    kind: str,
) -> List[Interval]:
    """
    Human interval starts after the prompt speech, approximated by the next
    "PROCESS listening for user input..." after the prompt,
    and ends at the matching user token emission (WRITE /nlp/out: ...).
    """
    intervals: List[Interval] = []
    i = 0
    while i < len(nlp_events):
        e = nlp_events[i]
        if prompt_prefix not in e.msg:
            i += 1
            continue
        # End of prompt speech approximation = start of listening window
        j, prompt_end = next_matching_event(
            nlp_events,
            i + 1,
            lambda x: "PROCESS listening for user input..." in x.msg,
        )
        if prompt_end is None:
            i += 1
            continue
        k, user_out = next_matching_event(
            nlp_events,
            (j or i) + 1,
            lambda x: any(f"WRITE /nlp/out: {tok}" in x.msg for tok in valid_outputs),
        )
        if user_out is None:
            i += 1
            continue
        if user_out.ts > prompt_end.ts:
            intervals.append(Interval(prompt_end.ts, user_out.ts, "human", kind, "nlp.log"))
        i = (k or i) + 1
    return intervals


def merge_intervals(intervals: Sequence[Interval], actor: str, kind: str, source: str) -> List[Interval]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda iv: (iv.start, iv.end))
    merged: List[Interval] = [Interval(ordered[0].start, ordered[0].end, actor, kind, source)]
    for iv in ordered[1:]:
        last = merged[-1]
        if iv.start <= last.end:
            last.end = max(last.end, iv.end)
        else:
            merged.append(Interval(iv.start, iv.end, actor, kind, source))
    return merged


def fill_gaps_as_agent(
    human_intervals: Sequence[Interval],
    agent_intervals: Sequence[Interval],
    t0: float,
    t1: float,
) -> List[Interval]:
    """
    Assign every uncovered time segment to the agent (sync/idle/support).
    """
    spans = [(max(t0, iv.start), min(t1, iv.end)) for iv in [*human_intervals, *agent_intervals] if iv.end > t0 and iv.start < t1]
    spans = [(s, e) for s, e in spans if e > s]
    if not spans:
        return [Interval(t0, t1, "agent", "sync_idle", "derived")]
    spans.sort()
    merged: List[Tuple[float, float]] = []
    cs, ce = spans[0]
    for s, e in spans[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            merged.append((cs, ce))
            cs, ce = s, e
    merged.append((cs, ce))

    gaps: List[Interval] = []
    cur = t0
    for s, e in merged:
        if s > cur:
            gaps.append(Interval(cur, s, "agent", "sync_idle", "derived"))
        cur = max(cur, e)
    if cur < t1:
        gaps.append(Interval(cur, t1, "agent", "sync_idle", "derived"))
    return gaps


def build_timeline_plot(intervals: List[Interval], t0: float, t1: float, out_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"matplotlib is required to generate the graph: {e}") from e

    human_y = 20
    robot_y = 5
    lane_h = 10
    colors = {
        ("human", "setup"): "#1f77b4",
        ("human", "attention"): "#17becf",
        ("human", "execution"): "#2ca02c",
        ("human", "maintenance"): "#d62728",
        ("agent", "planning"): "#9467bd",
        ("agent", "move"): "#ff7f0e",
        ("agent", "home"): "#8c564b",
        ("agent", "prompt_speech"): "#bcbd22",
        ("agent", "sync_idle"): "#7f7f7f",
    }

    fig, ax = plt.subplots(figsize=(12, 4.5))
    draw_order = {
        ("agent", "sync_idle"): 0,
        ("human", "setup"): 1,
        ("agent", "prompt_speech"): 2,
        ("agent", "planning"): 3,
        ("agent", "home"): 4,
        ("agent", "move"): 5,
        ("human", "attention"): 6,
        ("human", "execution"): 7,
        ("human", "maintenance"): 8,
    }
    for iv in sorted(intervals, key=lambda x: (draw_order.get((x.actor, x.kind), 99), x.start, x.end)):
        y = human_y if iv.actor == "human" else robot_y
        start = iv.start - t0
        width = iv.duration
        alpha = 0.45 if (iv.actor, iv.kind) == ("agent", "sync_idle") else 0.95
        ax.broken_barh(
            [(start, width)],
            (y, lane_h),
            facecolors=colors.get((iv.actor, iv.kind), "#7f7f7f"),
            alpha=alpha,
        )

    ax.set_ylim(0, 35)
    ax.set_xlim(0, max(1.0, t1 - t0))
    ax.set_xlabel("Time since system start [s]")
    ax.set_yticks([robot_y + lane_h / 2, human_y + lane_h / 2])
    ax.set_yticklabels(["Agent", "Human"])
    ax.set_title("Experiment timeline: who is acting over time")
    ax.grid(axis="x", linestyle="--", alpha=0.3)

    legend_items = [
        Patch(color=colors[("human", "setup")], label="Human setup"),
        Patch(color=colors[("human", "attention")], label="Human attention (robot prompt->go)"),
        Patch(color=colors[("human", "execution")], label="Human execution (please move->done/space)"),
        Patch(color=colors[("human", "maintenance")], label="Human maintenance (error->fixed)"),
        Patch(color=colors[("agent", "planning")], label="Agent planning (incl. PDDL build)"),
        Patch(color=colors[("agent", "move")], label="Agent move object"),
        Patch(color=colors[("agent", "home")], label="Agent move home (XXXXX)"),
        Patch(color=colors[("agent", "prompt_speech")], label="Agent prompt speech"),
        Patch(color=colors[("agent", "sync_idle")], label="Agent sync/idle/support"),
    ]
    ax.legend(handles=legend_items, ncol=2, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze one experiment log folder.")
    ap.add_argument("run_folder", type=Path, help="Path to one run folder (e.g., LogsExp/logs2)")
    ap.add_argument("--plot", type=Path, default=None, help="Output PNG path for the timeline graph")
    args = ap.parse_args()

    run_folder: Path = args.run_folder
    if not run_folder.exists():
        print(f"Run folder not found: {run_folder}", file=sys.stderr)
        return 2

    nlp_events = parse_log(run_folder / "nlp.log")
    planner_events = parse_log(run_folder / "planner.log")
    abb_events = parse_log(run_folder / "abb.log")
    all_events = sorted([*nlp_events, *planner_events, *abb_events], key=lambda e: e.ts)

    if not nlp_events:
        print("Missing or empty nlp.log", file=sys.stderr)
        return 2

    t_start, t_end = detect_session_bounds(nlp_events, planner_events, all_events)
    t_system_start = detect_system_start_before_session(t_start, nlp_events, planner_events, abb_events)

    nlp_s = clip_events(nlp_events, t_system_start, t_end)
    planner_s = clip_events(planner_events, t_start, t_end)
    abb_s = clip_events(abb_events, t_start, t_end)

    # Human setup interval: all time from system start to the valid start command.
    human_setup: List[Interval] = [Interval(t_system_start, t_start, "human", "setup", "derived")] if t_start > t_system_start else []

    # Agent prompt speech intervals (all prompts spoken by NLP module).
    agent_prompt_speech = pair_prompt_speech_intervals(nlp_s)

    # Human intervals (restore original working definition).
    # These are the metrics intervals you were using before:
    # prompt receipt -> user spoken response.
    human_attention = pair_intervals(
        nlp_s,
        lambda e: 'READ /nlp/in: Robot will move ' in e.msg,
        lambda e: 'WRITE /nlp/out: go' in e.msg,
        actor="human",
        kind="attention",
        source="nlp.log",
    )
    human_execution = pair_intervals(
        nlp_s,
        lambda e: 'READ /nlp/in: Please move ' in e.msg,
        lambda e: ('WRITE /nlp/out: done' in e.msg) or ('WRITE /nlp/out: space' in e.msg),
        actor="human",
        kind="execution",
        source="nlp.log",
    )
    human_maintenance = pair_intervals(
        nlp_s,
        lambda e: 'READ /nlp/in: An error occurred' in e.msg,
        lambda e: 'WRITE /nlp/out: fixed' in e.msg,
        actor="human",
        kind="maintenance",
        source="nlp.log",
    )

    robot_planning = pair_planning_intervals(planner_s)
    robot_move, robot_home = pair_abb_intervals(abb_s)

    human_intervals = [*human_setup, *human_attention, *human_execution, *human_maintenance]
    # Core agent activity (kept separate from gap-fill so reported totals remain useful)
    agent_core_intervals = [*robot_planning, *robot_move, *robot_home, *agent_prompt_speech]
    agent_intervals = list(agent_core_intervals)

    # Add all uncovered time to the agent (sync/idle/support).
    agent_gap_fill = fill_gaps_as_agent(human_intervals, agent_intervals, t_system_start, t_end)
    agent_intervals = [*agent_intervals, *agent_gap_fill]

    all_intervals = sorted([*human_intervals, *agent_intervals], key=lambda iv: (iv.start, iv.actor))

    total_time = t_end - t_system_start
    total_experiment_time = t_end - t_start
    total_human = summarize(human_intervals)
    total_robot = summarize(agent_core_intervals)

    # Fan-out proxies with classical formula FO = 1 + NT / IE
    # NT proxy: TOTAL agent autonomous move time (object moves + home moves)
    # IE proxy (execution only): TOTAL human attention time (Robot will move... -> go)
    # IE proxy (including setup): setup + attention
    nt_vals = [iv.duration for iv in [*robot_move, *robot_home]]
    ie_attention_vals = [iv.duration for iv in human_attention]
    setup_total = summarize(human_setup)
    nt = sum(nt_vals) if nt_vals else None
    ie_no_setup = sum(ie_attention_vals) if ie_attention_vals else None
    ie_with_setup = (setup_total + ie_no_setup) if ie_no_setup is not None else None
    fo_no_setup = (1.0 + nt / ie_no_setup) if (nt is not None and ie_no_setup and ie_no_setup > 0) else None
    fo_with_setup = (1.0 + nt / ie_with_setup) if (nt is not None and ie_with_setup and ie_with_setup > 0) else None

    print(f"Run folder: {run_folder}")
    print(f"Session window (for Total time): start='WRITE /nlp/out: start' at {t_start:.6f}, end at {t_end:.6f}")
    print(f"Timeline origin (system start): {t_system_start:.6f}")
    print()
    print("Formulas used")
    print("  Human setup time        = system_start -> NLP 'WRITE /nlp/out: start'")
    print("  Agent prompt speech     = sum( NLP 'READ /nlp/in: actionable prompt' -> next 'PROCESS listening for user input...' ; fallback non-actionable -> next NLP event )")
    print("  Human attention time    = sum( NLP 'Robot will move...' -> NLP 'WRITE /nlp/out: go' )")
    print("  Human execution time    = sum( NLP 'Please move...' -> NLP 'WRITE /nlp/out: done|space' )")
    print("  Human maintenance time  = sum( NLP 'An error occurred...' -> NLP 'WRITE /nlp/out: fixed' )")
    print("  Total human time        = setup + attention + execution + maintenance")
    print("  Agent planning time     = sum( planner 'PROCESS building PDDL problem...' -> planner 'PROCESS planner returned...'|plan_failed )")
    print("  Agent moving objects    = sum( ABB 'READ /abb/in: move ...' -> ABB 'WRITE /abb/out: ok|fail' )")
    print("  Agent moving home       = sum( ABB 'READ /abb/in: XXXXX' -> ABB 'WRITE /abb/out: ok|fail' )")
    print("  Agent sync/idle time    = all remaining uncovered time in [system_start, end] (timeline fill only)")
    print("  Total agent time        = planning + moving objects + moving home + prompt speech")
    print("  Fan-out (proxy)         = 1 + NT/IE")
    print("     NT (proxy)           = total(agent move+home intervals)")
    print("     IE (no setup)        = total(human attention intervals)")
    print("     IE (with setup)      = human setup + human attention")
    print()
    print("Summary")
    print(f"  Total time (system):    {format_seconds(total_time)} ({total_time/60:.3f} min)")
    print(f"  Total time (start->end):{format_seconds(total_experiment_time)} ({total_experiment_time/60:.3f} min)")
    print(f"  Total human time:       {format_seconds(total_human)}")
    print(f"    setup:                {format_seconds(summarize(human_setup))}  (n={len(human_setup)})")
    print(f"    attention:            {format_seconds(summarize(human_attention))}  (n={len(human_attention)})")
    print(f"    execution:            {format_seconds(summarize(human_execution))}  (n={len(human_execution)})")
    print(f"    maintenance:          {format_seconds(summarize(human_maintenance))}  (n={len(human_maintenance)})")
    print(f"  Total agent time:       {format_seconds(total_robot)}")
    print(f"    planning:             {format_seconds(summarize(robot_planning))}  (n={len(robot_planning)})")
    print(f"    moving objects:       {format_seconds(summarize(robot_move))}  (n={len(robot_move)})")
    print(f"    moving home:          {format_seconds(summarize(robot_home))}  (n={len(robot_home)})")
    print(f"    prompt speech:        {format_seconds(summarize(agent_prompt_speech))}  (n={len(agent_prompt_speech)})")
    print(f"    sync/idle/support:    {format_seconds(summarize(agent_gap_fill))}  (n={len(agent_gap_fill)}) [timeline fill]")
    if nt is not None:
        print(f"  NT (proxy):             {format_seconds(nt)}")
    else:
        print("  NT (proxy):             NA")
    if ie_no_setup is not None:
        print(f"  IE (proxy, no setup):   {format_seconds(ie_no_setup)}")
    else:
        print("  IE (proxy, no setup):   NA")
    if ie_with_setup is not None:
        print(f"  IE (proxy, with setup): {format_seconds(ie_with_setup)}")
    else:
        print("  IE (proxy, with setup): NA")
    if fo_no_setup is not None:
        print(f"  Fan-out (no setup):     {fo_no_setup:.3f}")
    else:
        print("  Fan-out (no setup):     NA")
    if fo_with_setup is not None:
        print(f"  Fan-out (with setup):   {fo_with_setup:.3f}")
    else:
        print("  Fan-out (with setup):   NA")

    plot_path = args.plot if args.plot else (run_folder / "time_actor_timeline.png")
    try:
        build_timeline_plot(all_intervals, t_system_start, t_end, plot_path)
        print(f"  Timeline graph:         {plot_path}")
    except RuntimeError as e:
        print(f"  Timeline graph:         NOT GENERATED ({e})")
        print("  Install dependency:     pip install matplotlib")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

