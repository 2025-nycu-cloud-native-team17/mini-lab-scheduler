# rand_client_gantt.py  (revised to match new Task schema)
import random, argparse, requests, json
import matplotlib.pyplot as plt
from matplotlib import colormaps
import matplotlib.colors as mcolors
from typing import List, Dict, Any


# ---------- CLI arguments ----------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/schedule_with_busy")
    return p.parse_args()


# ---------- Gantt plot ----------
def lighten_color(color, amount=0.5):
    r, g, b, a = color
    white = (1.0, 1.0, 1.0)
    return tuple((1 - amount) * c + amount * w for c, w in zip((r, g, b), white)) + (a,)


def draw_gantt(assignments: List[Dict[str, int]], tasks: List[Dict[str, Any]]) -> None:
    # lookup and sets
    t_lut = {t["id"]: t for t in tasks}
    w_ids = sorted({a["worker_id"] for a in assignments})
    m_ids = sorted({a["machine_id"] for a in assignments})
    w_pos = {wid: i for i, wid in enumerate(w_ids)}
    m_pos = {mid: i + len(w_ids) + 1 for i, mid in enumerate(m_ids)}

    # jet-based colour map per *task*, then lightened
    norm = mcolors.Normalize(vmin=min(t_lut.keys()), vmax=max(t_lut.keys()))
    cmap = colormaps["jet"]

    fig, ax = plt.subplots(figsize=(12, 6))

    for a in assignments:
        tid = a["task_id"]
        dur = t_lut[tid]["duration"]
        start = a["start"]
        base = cmap(norm(tid))
        color = lighten_color(base, amount=0.5)

        # bars
        ax.barh(w_pos[a["worker_id"]], dur, left=start, height=0.4, color=color)
        ax.barh(m_pos[a["machine_id"]], dur, left=start, height=0.4, color=color)

        # labels
        ax.text(
            start + dur / 2,
            w_pos[a["worker_id"]],
            f"T{tid}",
            ha="center",
            va="center",
            fontsize=8,
            color="black",
        )
        ax.text(
            start + dur / 2,
            m_pos[a["machine_id"]],
            f"T{tid}",
            ha="center",
            va="center",
            fontsize=8,
            color="black",
        )

    # axis formatting
    yticks = list(w_pos.values()) + list(m_pos.values())
    ylabels = [f"W{w}" for w in w_ids] + [f"M{m}" for m in m_ids]
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.set_xlabel("Time")
    ax.set_title("Gantt chart – Workers & Machines")
    plt.tight_layout()
    plt.savefig("gantt.png", dpi=300)


# ---------- test case ----------
# API-ready payload
payload_test = {
    "workers": [
        {"id": 101, "types": ["A"]},
        {"id": 102, "types": ["C"]},
        {"id": 103, "types": ["E", "H"], "busy_windows": [(20, 60)]},
        {"id": 104, "types": ["G"]},
        {"id": 105, "types": ["B"]},
        {"id": 106, "types": ["D", "F"]},
    ],
    "machines": [
        {"id": 201, "types": ["A"]},
        {
            "id": 202,
            "types": ["C", "F", "H", "D"],
            "busy_windows": [(0, 5), (10, 15), (30, 50)],
        },
        {"id": 203, "types": ["E"]},
        {"id": 204, "types": ["G"]},
        {"id": 205, "types": ["B"]},
    ],
    "tasks": [
        {"id": 1, "type": "A", "duration": 4, "earliest_start": 0, "deadline": 100},
        {"id": 2, "type": "B", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": 3, "type": "C", "duration": 5, "earliest_start": 0, "deadline": 100},
        {"id": 4, "type": "D", "duration": 2, "earliest_start": 0, "deadline": 100},
        {"id": 5, "type": "E", "duration": 6, "earliest_start": 0, "deadline": 100},
        {"id": 6, "type": "F", "duration": 3, "earliest_start": 0, "deadline": 10},
        {"id": 7, "type": "G", "duration": 4, "earliest_start": 0, "deadline": 100},
        {"id": 8, "type": "H", "duration": 2, "earliest_start": 0, "deadline": 100},
        {"id": 9, "type": "A", "duration": 5, "earliest_start": 0, "deadline": 100},
        {"id": 10, "type": "B", "duration": 1, "earliest_start": 0, "deadline": 100},
        {"id": 11, "type": "C", "duration": 4, "earliest_start": 0, "deadline": 30},
        {"id": 12, "type": "D", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": 13, "type": "E", "duration": 2, "earliest_start": 0, "deadline": 100},
        {"id": 14, "type": "F", "duration": 6, "earliest_start": 0, "deadline": 25},
        {"id": 15, "type": "G", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": 16, "type": "H", "duration": 4, "earliest_start": 0, "deadline": 100},
    ],
}


# ---------- main ----------
def main():
    a = parse_args()
    # payload = build_payload(a)
    # payload = payload_feasible
    # payload = payload_no_worker
    # payload = payload_no_machine
    # payload = payload_window_too_tight
    # payload = payload_overlap
    # payload = payload_deadline_race_ok
    payload = payload_test

    for w in payload["workers"]:
        w["types"] = sorted(w["types"])
        print(f"Worker {w['id']} types:  {', '.join(w['types'])}")
    for m in payload["machines"]:
        m["types"] = sorted(m["types"])
        print(f"Machine {m['id']} types: {', '.join(m['types'])}")
    for t in payload["tasks"]:
        print(
            f"Task {t['id']}: {t['duration']} units in [{t['earliest_start']}, {t['deadline']}],"
            f" type {t['type']}"
        )

    r = requests.post(a.url, json=payload, timeout=30)
    if not r.ok:
        raise SystemExit(f"API error {r.status_code}: {r.text}")

    sol = r.json()
    print(f"=== Total duration: {sol['makespan']}")
    for assignment in sol["assignments"]:
        print(
            f"Task {assignment['task_id']}: Worker {assignment['worker_id']}"
            f" and Machine {assignment['machine_id']} at time {assignment['start']}"
        )
    draw_gantt(sol["assignments"], payload["tasks"])


if __name__ == "__main__":
    main()
