# rand_client_gantt.py  (revised to match new Task schema)
import random, argparse, requests, json
import matplotlib.pyplot as plt
from matplotlib import colormaps
import matplotlib.colors as mcolors
from typing import List, Dict, Any


# ---------- CLI arguments ----------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--machines", type=int, default=5)
    p.add_argument("--tasks", type=int, default=10)
    p.add_argument("--types", nargs="+", default=list("ABCD"))
    p.add_argument("--dur-min", type=int, default=1)
    p.add_argument("--dur-max", type=int, default=4)
    p.add_argument("--horizon", type=int, default=30)
    p.add_argument("--url", default="http://127.0.0.1:8000/schedule")
    p.add_argument("--seed", type=int, help="set for reproducibility")
    return p.parse_args()


# ---------- random-instance generator ----------
def rand_subset(pool: List[str]) -> List[str]:
    return random.sample(pool, random.randint(1, len(pool)))


def build_payload(a) -> Dict[str, Any]:
    workers = [{"id": i, "types": rand_subset(a.types)} for i in range(a.workers)]
    machines = [{"id": i, "types": rand_subset(a.types)} for i in range(a.machines)]
    tasks = []
    for i in range(a.tasks):
        ttype = random.choice(a.types)
        dur = random.randint(a.dur_min, a.dur_max)
        earliest = random.randint(0, a.horizon - dur)
        deadline = random.randint(earliest + dur, a.horizon)
        tasks.append(
            dict(
                id=i,
                type=ttype,
                duration=dur,
                earliest_start=earliest,
                deadline=deadline,
            )
        )
    payload = dict(workers=workers, machines=machines, tasks=tasks)

    return payload


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
    numeric_task_ids = {tid: i for i, tid in enumerate(sorted(t_lut.keys()))}
    norm = mcolors.Normalize(vmin=0, vmax=len(numeric_task_ids) - 1)
    cmap = colormaps["jet"]

    fig, ax = plt.subplots(figsize=(12, 6))

    for a in assignments:
        tid = a["task_id"]
        dur = t_lut[tid]["duration"]
        start = a["start"]
        base = cmap(norm(numeric_task_ids[tid]))
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

# 1. Feasible – single task fits easily
payload_feasible = {
    "workers": [{"id": 0, "types": ["A"]}],
    "machines": [{"id": 0, "types": ["A"]}],
    "tasks": [
        {"id": 0, "type": "A", "duration": 2, "earliest_start": 3, "deadline": 5},
    ],
}

# 2. Worker-type mismatch – no worker can handle type “B”  → unschedulable
payload_no_worker = {
    "workers": [{"id": 0, "types": ["A"]}],
    "machines": [{"id": 0, "types": ["A", "B"]}],
    "tasks": [
        {"id": 0, "type": "B", "duration": 1, "earliest_start": 0, "deadline": 3},
    ],
}

# 3. Machine-type mismatch – worker is valid but no machine supports type “C”
payload_no_machine = {
    "workers": [{"id": 0, "types": ["C"]}],
    "machines": [{"id": 0, "types": ["A", "B"]}],
    "tasks": [
        {"id": 0, "type": "C", "duration": 1, "earliest_start": 0, "deadline": 4},
    ],
}

# 4. Time-window impossible – duration exceeds [earliest_start, deadline]
payload_window_too_tight = {
    "workers": [{"id": 0, "types": ["A"]}],
    "machines": [{"id": 0, "types": ["A"]}],
    "tasks": [
        {
            "id": 0,
            "type": "A",
            "duration": 3,
            "earliest_start": 1,
            "deadline": 3,
        },  # needs 3 slots but only 2 available
    ],
}

# 5. Overlap clash – two tasks share same type but only one worker/machine
payload_overlap = {
    "workers": [{"id": 0, "types": ["A"]}],
    "machines": [{"id": 0, "types": ["A"]}],
    "tasks": [
        {"id": 0, "type": "A", "duration": 2, "earliest_start": 0, "deadline": 4},
        {"id": 1, "type": "A", "duration": 2, "earliest_start": 1, "deadline": 4},
    ],
}

payload_deadline_race_ok = {
    "workers": [
        {"id": 0, "types": ["A", "B"]},
        {"id": 1, "types": ["A", "B"]},  # extra worker makes plan feasible
    ],
    "machines": [
        {"id": 0, "types": ["A", "B"]},
        {"id": 1, "types": ["A", "B"]},  # extra machine for parallelism
    ],
    "tasks": [
        # Three tasks all due by 5.  Total work = 6 time-units.
        # With 2 worker-machine pairs they can run in parallel.
        {"id": 0, "type": "A", "duration": 2, "earliest_start": 0, "deadline": 5},
        {"id": 1, "type": "A", "duration": 2, "earliest_start": 0, "deadline": 5},
        {"id": 2, "type": "B", "duration": 2, "earliest_start": 1, "deadline": 5},
    ],
}

# API-ready payload
payload_test = {
    "workers": [
        {"id": "w101", "types": ["A"]},
        {"id": "w102", "types": ["C"]},
        {"id": "w103", "types": ["E", "H"]},
        {"id": "w104", "types": ["G"]},
        {"id": "w105", "types": ["B"]},
        {"id": "w106", "types": ["D", "F"]},
    ],
    "machines": [
        {"id": "m201", "types": ["A"]},
        {"id": "m202", "types": ["C", "F", "H", "D"]},
        {"id": "m203", "types": ["E"]},
        {"id": "m204", "types": ["G"]},
        {"id": "m205", "types": ["B"]},
    ],
    "tasks": [
        {"id": "t1", "type": "A", "duration": 4, "earliest_start": 0, "deadline": 100},
        {"id": "t2", "type": "B", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": "t3", "type": "C", "duration": 5, "earliest_start": 0, "deadline": 100},
        {"id": "t4", "type": "D", "duration": 2, "earliest_start": 0, "deadline": 100},
        {"id": "t5", "type": "E", "duration": 6, "earliest_start": 0, "deadline": 100},
        {"id": "t6", "type": "F", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": "t7", "type": "G", "duration": 4, "earliest_start": 0, "deadline": 100},
        {"id": "t8", "type": "H", "duration": 2, "earliest_start": 0, "deadline": 100},
        {"id": "t9", "type": "A", "duration": 5, "earliest_start": 0, "deadline": 100},
        {"id": "t10", "type": "B", "duration": 1, "earliest_start": 0, "deadline": 100},
        {"id": "t11", "type": "C", "duration": 4, "earliest_start": 0, "deadline": 100},
        {"id": "t12", "type": "D", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": "t13", "type": "E", "duration": 2, "earliest_start": 0, "deadline": 100},
        {"id": "t14", "type": "F", "duration": 6, "earliest_start": 0, "deadline": 100},
        {"id": "t15", "type": "G", "duration": 3, "earliest_start": 0, "deadline": 100},
        {"id": "t16", "type": "H", "duration": 4, "earliest_start": 0, "deadline": 100},
    ],
}


# ---------- main ----------
def main():
    a = parse_args()
    if a.seed is not None:
        random.seed(a.seed)
    else:
        seed = random.randint(0, 2**8 - 1)
        random.seed(seed)
        print(f"Random seed: {seed}")
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
