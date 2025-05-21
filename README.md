# mini-lab-scheduler

## Environment Setup

```
pip install -r requirements.txt
```

## Run the Application

```
uvicorn server:app --host <host> --port <port> --reload
```

## Run Tests

```
pip install -r requirements-test.txt
python test.py
python test_busy.py
npx tsx test_busy.ts
```

## API Documentation

```
POST /schedule_with_busy

request body:
{
    "workers": [
        {
            "id": 101,
            "types": ["A", "B", ...],
            "busy_windows": [[20, 36], [44, 60], ...]
        },
        { ... },
    ],
    "machines": [
        {
            "id": 201,
            "types": ["A", "B", ...],
            "busy_windows": [[20, 36], [44, 60], ...]
        },
        { ... },
    ],
    "tasks": [
        {
            "id": 1,
            "type": "A",
            "duration": 10,
            "earliest_start": 0,
            "deadline": 100,
        },
        { ... },
    ]
}

response:
{
    "makespan": 60,
    "assignments": [
        {
            "task_id": 1,
            "worker_id": 101,
            "machine_id": 201,
            "start": 0,
            "end": 4
        },
        { ... },
    ]
}
```