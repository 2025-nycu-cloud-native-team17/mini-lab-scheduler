from typing import List, Set, Tuple
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ortools.sat.python import cp_model
from itertools import count
from copy import deepcopy


class Task(BaseModel):
    id: str
    type: str
    duration: int
    earliest_start: int
    deadline: int


class Worker(BaseModel):
    id: str
    types: Set[str]


class Machine(BaseModel):
    id: str
    types: Set[str]


class ScheduleRequest(BaseModel):
    workers: List[Worker]
    machines: List[Machine]
    tasks: List[Task]


class WorkerBW(BaseModel):
    id: str
    types: Set[str]
    busy_windows: List[Tuple[int, int]] = []  # [(start,end)]


class MachineBW(BaseModel):
    id: str
    types: Set[str]
    busy_windows: List[Tuple[int, int]] = []


class ScheduleRequestBW(BaseModel):
    workers: List[WorkerBW]
    machines: List[MachineBW]
    tasks: List[Task]


app = FastAPI()


# ---------- helper: convert busy windows → dummy tasks ----------
def inject_busy_tasks(req: ScheduleRequestBW) -> tuple[ScheduleRequest, set[int]]:
    """
    Replace every busy window with a unique dummy task that ties up BOTH
    resources. Return the converted ScheduleRequest and the set of dummy task IDs.
    """
    req2 = deepcopy(req)

    # next_task_id = 1 + max((t.id for t in req2.tasks), default=0)
    # max_worker_id = max((w.id for w in req2.workers), default=0)
    # max_machine_id = max((m.id for m in req2.machines), default=0)
    # next_dummy_worker = count(max_worker_id + 1)  # fresh IDs
    # next_dummy_machine = count(max_machine_id + 1)

    dummy_ids: set[int] = set()
    dummy_prefix = "_BW_"  # only for the *type* name

    # — worker busy → dummy task + placeholder machine —
    for w in req2.workers:
        for idx, (s, e) in enumerate(w.busy_windows):
            ttype = f"{dummy_prefix}W{w.id}_{idx}"
            w.types.add(ttype)  # lock the real worker

            # phantom machine with unique ID
            ph_mid = f"ph_m_{uuid.uuid4().hex}"
            req2.machines.append(MachineBW(id=ph_mid, types={ttype}, busy_windows=[]))

            # dummy task with unique ID
            dummy_task_id = f"dummy_{uuid.uuid4().hex}"
            req2.tasks.append(
                Task(
                    id=dummy_task_id,
                    type=ttype,
                    duration=e - s,
                    earliest_start=s,
                    deadline=e,
                )
            )
            dummy_ids.add(dummy_task_id)

    # — machine busy → dummy task + placeholder worker —
    for m in req2.machines:
        for idx, (s, e) in enumerate(m.busy_windows):
            ttype = f"{dummy_prefix}M{m.id}_{idx}"
            m.types.add(ttype)  # lock the real machine

            # phantom worker with unique ID
            ph_wid = f"ph_w_{uuid.uuid4().hex}"
            req2.workers.append(WorkerBW(id=ph_wid, types={ttype}, busy_windows=[]))

            # dummy task with unique ID
            dummy_task_id = f"dummy_{uuid.uuid4().hex}"
            req2.tasks.append(
                Task(
                    id=dummy_task_id,
                    type=ttype,
                    duration=e - s,
                    earliest_start=s,
                    deadline=e,
                )
            )
            dummy_ids.add(dummy_task_id)

    # cast back to basic models (busy_windows removed for solver)
    workers_clean = [Worker(id=w.id, types=w.types) for w in req2.workers]
    machines_clean = [Machine(id=m.id, types=m.types) for m in req2.machines]
    return (
        ScheduleRequest(
            workers=workers_clean, machines=machines_clean, tasks=req2.tasks
        ),
        dummy_ids,
    )


@app.post("/schedule_with_busy")
def schedule_with_busy(req: ScheduleRequestBW):
    converted, dummy_ids = inject_busy_tasks(req)
    result = schedule(converted)  # reuse existing solver

    real_plan = [
        a for a in result["assignments"] if a["task_id"] not in dummy_ids
    ]  # drop placeholders
    real_makespan = max((a["end"] for a in real_plan), default=0)
    return {"makespan": real_makespan, "assignments": real_plan}


@app.post("/schedule")
def schedule(req: ScheduleRequest):
    # log
    for w in req.workers:
        w.types = sorted(w.types)
        print(f"Worker {w.id} types:  {', '.join(w.types)}")
    for m in req.machines:
        m.types = sorted(m.types)
        print(f"Machine {m.id} types: {', '.join(m.types)}")
    for t in req.tasks:
        print(
            f"Task {t.id}: {t.duration} units in [{t.earliest_start}, {t.deadline}],"
            f" type {t.type}"
        )

    mdl = cp_model.CpModel()
    horizon = max(t.deadline for t in req.tasks)

    # start time per task
    start = {
        t.id: mdl.NewIntVar(t.earliest_start, t.deadline - t.duration, f"start_t{t.id}")
        for t in req.tasks
    }

    # presence booleans
    w_choose, m_choose = {}, {}
    for t in req.tasks:
        for w in req.workers:
            key = (t.id, w.id)
            w_choose[key] = mdl.NewBoolVar(f"w_t{t.id}_w{w.id}")
            if t.type not in w.types:
                mdl.Add(w_choose[key] == 0)
        for m in req.machines:
            key = (t.id, m.id)
            m_choose[key] = mdl.NewBoolVar(f"m_t{t.id}_m{m.id}")
            if t.type not in m.types:
                mdl.Add(m_choose[key] == 0)

        # exactly one worker & one machine
        mdl.Add(sum(w_choose[(t.id, w.id)] for w in req.workers) == 1)
        mdl.Add(sum(m_choose[(t.id, m.id)] for m in req.machines) == 1)

        # timing windows
        mdl.Add(start[t.id] + t.duration <= t.deadline)

    # no-overlap per worker
    for w in req.workers:
        intervals = [
            mdl.NewOptionalIntervalVar(
                start[t.id],
                t.duration,
                start[t.id] + t.duration,
                w_choose[(t.id, w.id)],
                f"int_t{t.id}_w{w.id}",
            )
            for t in req.tasks
            if t.type in w.types
        ]
        mdl.AddNoOverlap(intervals)

    # no-overlap per machine
    for m in req.machines:
        intervals = [
            mdl.NewOptionalIntervalVar(
                start[t.id],
                t.duration,
                start[t.id] + t.duration,
                m_choose[(t.id, m.id)],
                f"int_t{t.id}_m{m.id}",
            )
            for t in req.tasks
            if t.type in m.types
        ]
        mdl.AddNoOverlap(intervals)

    # minimise makespan
    makespan = mdl.NewIntVar(0, horizon, "makespan")
    mdl.AddMaxEquality(makespan, [start[t.id] + t.duration for t in req.tasks])
    mdl.Minimize(makespan)

    # solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    if solver.Solve(mdl) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise HTTPException(422, "No feasible schedule")

    plan = []
    for t in req.tasks:
        w_id = next(
            w.id for w in req.workers if solver.BooleanValue(w_choose[(t.id, w.id)])
        )
        m_id = next(
            m.id for m in req.machines if solver.BooleanValue(m_choose[(t.id, m.id)])
        )
        s = solver.Value(start[t.id])
        plan.append(
            {
                "task_id": t.id,
                "worker_id": w_id,
                "machine_id": m_id,
                "start": s,
                "end": s + t.duration,
            }
        )

    return {"makespan": solver.Value(makespan), "assignments": plan}
