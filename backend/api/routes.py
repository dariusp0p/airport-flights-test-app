from __future__ import annotations

import json
import threading
import time
import uuid
import random
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter()


@dataclass
class Job:
    status: str                 # queued | running | done | failed
    progress: int               # 0..100
    stage: str                  # queued | validating | fetching_weather | predicting | done | failed
    created_at: float
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


_jobs: Dict[str, Job] = {}
_jobs_lock = threading.Lock()

# limit how many background threads can run at once
_MAX_CONCURRENT_JOBS = 4
_job_semaphore = threading.Semaphore(_MAX_CONCURRENT_JOBS)

# TTL cleanup to avoid memory growth
_JOB_TTL_SECONDS = 15 * 60  # 15 minutes


def _cleanup_old_jobs() -> None:
    now = time.time()
    with _jobs_lock:
        old_ids = [jid for jid, job in _jobs.items() if now - job.created_at > _JOB_TTL_SECONDS]
        for jid in old_ids:
            _jobs.pop(jid, None)


def _update_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for k, v in kwargs.items():
            setattr(job, k, v)


def _read_job(job_id: str) -> Job:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return Job(**asdict(job))



# Mock pipeline components

def _mock_fetch_weather_for_flights(flights: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Pretend we called a weather API.
    time.sleep(0.6)
    return {"source": "mock-weather", "note": "replace with real weather API"}


def _mock_predict_delays(flights: List[Dict[str, Any]], weather: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Pretend we ran an AI model.
    time.sleep(0.7)

    results = []
    for f in flights:
        # Very fake "prediction"
        results.append({
            **f,
            "estimatedDelay": random.randint(0, 120),
        })
    return results



# Process Job

def _process_job(job_id: str, flights: List[Dict[str, Any]]) -> None:
    with _job_semaphore:
        try:
            _update_job(job_id, status="running", stage="validating", progress=5)

            # Minimal validation for demo. Expand later with Pydantic per-item.
            if not flights:
                raise ValueError("No flights provided")
            if not isinstance(flights, list):
                raise ValueError("Flights payload must be a list")

            _update_job(job_id, stage="fetching_weather", progress=25)
            weather = _mock_fetch_weather_for_flights(flights)

            _update_job(job_id, stage="predicting", progress=70)
            predicted = _mock_predict_delays(flights, weather)

            _update_job(
                job_id,
                status="done",
                stage="done",
                progress=100,
                result={
                    "jobId": job_id,
                    "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "count": len(predicted),
                    "results": predicted,
                },
            )

        except Exception as e:
            _update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                error={"code": "INTERNAL", "message": str(e)},
            )



# Routes

from fastapi import Body

@router.post("/jobs")
async def create_job(data: dict = Body(...)):
    _cleanup_old_jobs()

    flights = data.get("flights")
    if not isinstance(flights, list):
        raise HTTPException(status_code=400, detail="Expected a JSON object with 'flights': [ ... ]")

    job_id = uuid.uuid4().hex
    job = Job(
        status="queued",
        progress=0,
        stage="queued",
        created_at=time.time(),
    )

    with _jobs_lock:
        _jobs[job_id] = job

    t = threading.Thread(target=_process_job, args=(job_id, flights), daemon=True)
    t.start()

    return {
        "jobId": job_id,
        "statusUrl": f"/api/jobs/{job_id}",
        "resultUrl": f"/api/jobs/{job_id}/result",
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = _read_job(job_id)
    payload = asdict(job)
    payload.pop("result", None)
    return payload


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: str):
    job = _read_job(job_id)

    if job.status == "done":
        return job.result

    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error)

    raise HTTPException(
        status_code=409,
        detail={"message": "Job not finished yet", "status": job.status, "stage": job.stage, "progress": job.progress},
    )