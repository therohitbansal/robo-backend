import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlmodel import Session

from ..db import engine
from ..models import RobotRun, RobotPreset
from ..services.robot_runner import run_robot_suite


router = APIRouter()

# Store running tasks status
running_tasks = {}

class RobotRunRequest(BaseModel):
    suite_path: str
    variables: Optional[Dict[str, str]] = None
    output_subdir: Optional[str] = None
    extra_args: Optional[List[str]] = None  # e.g., ["-i", "homeal"]


@router.post("/run")
async def trigger_robot_run(body: RobotRunRequest, background_tasks: BackgroundTasks) -> dict:
    normalized_path = os.path.abspath(os.path.expanduser(body.suite_path.strip()))
    if not os.path.exists(normalized_path):
        raise HTTPException(
            status_code=400,
            detail=f"suite_path does not exist on server: {normalized_path}",
        )

    # Pre-create run to get sequential ID and folder per run
    with Session(engine) as session:
        run = RobotRun(suite_path=normalized_path, output_dir="", return_code=None, ok=False)
        session.add(run)
        session.commit()
        session.refresh(run)

    # Store initial running status
    running_tasks[run.id] = {
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "suite_path": normalized_path
    }

    # Run in background
    background_tasks.add_task(
        execute_robot_suite,
        run.id,
        normalized_path,
        body.variables,
        body.extra_args
    )

    return {
        "run_id": run.id,
        "status": "running",
        "message": "Test execution started",
        "suite_path": normalized_path
    }


def execute_robot_suite(run_id: int, suite_path: str, variables: dict, extra_args: list):
    """Execute robot framework suite in background and update status"""
    try:
        out_dir = os.path.abspath(os.path.join("./data/robot_runs", str(run_id)))
        
        # Update status to show execution started
        running_tasks[run_id]["status"] = "executing"
        running_tasks[run_id]["message"] = "Running test cases..."
        
        rc = run_robot_suite(
            suite_path,
            out_dir,
            variables=variables,
            extra_args=extra_args,
        )

        # Update the run in database
        with Session(engine) as session:
            run = session.get(RobotRun, run_id)
            run.output_dir = out_dir
            run.return_code = rc
            run.ok = rc == 0
            session.add(run)
            session.commit()

        # Update running tasks with completion
        running_tasks[run_id] = {
            "status": "completed",
            "return_code": rc,
            "ok": rc == 0,
            "suite_path": suite_path,
            "output_dir": out_dir,
            "completion_time": datetime.now().isoformat()
        }

    except Exception as e:
        # Update running tasks with error
        running_tasks[run_id] = {
            "status": "error",
            "error": str(e),
            "suite_path": suite_path
        }


@router.get("/run-status/{run_id}")
def get_run_status(run_id: int) -> dict:
    """Get current status of a running test"""
    # Check if run is in running tasks
    if run_id in running_tasks:
        return running_tasks[run_id]
    
    # Check if run exists in database (completed)
    with Session(engine) as session:
        run = session.get(RobotRun, run_id)
        if run:
            return {
                "status": "completed",
                "return_code": run.return_code,
                "ok": run.ok,
                "suite_path": run.suite_path,
                "output_dir": run.output_dir,
                "created_at": run.created_at.isoformat()
            }
    
    raise HTTPException(status_code=404, detail="Run not found")


@router.get("/runs")
def list_runs() -> list[dict]:
    runs: list[RobotRun]
    with Session(engine) as session:
        runs = session.query(RobotRun).order_by(RobotRun.id.desc()).limit(100).all()
    out: list[dict] = []
    for r in runs:
        out.append({
            "id": r.id,
            "ok": r.ok,
            "return_code": r.return_code,
            "suite_path": r.suite_path,
            "created_at": r.created_at.isoformat(),
            "allure_index": f"/files/robot_runs/{r.id}/allure-report/index.html",
            "log_html": f"/files/robot_runs/{r.id}/log.html",
            "report_html": f"/files/robot_runs/{r.id}/report.html",
        })
    return out


# Presets
class RobotPresetBody(BaseModel):
    name: str
    suite_path: str
    variables: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None  # convenience, converted to ["-i", tag]
    extra_args: Optional[List[str]] = None


@router.get("/presets")
def list_presets() -> list[RobotPreset]:
    with Session(engine) as session:
        return session.query(RobotPreset).order_by(RobotPreset.id.desc()).all()


@router.post("/presets")
def create_preset(body: RobotPresetBody) -> RobotPreset:
    normalized_path = os.path.abspath(os.path.expanduser(body.suite_path.strip()))
    extras: list[str] = []
    if body.tags:
        for t in body.tags:
            if t:
                extras.extend(["-i", t])
    if body.extra_args:
        extras.extend(body.extra_args)
    preset = RobotPreset(
        name=body.name,
        suite_path=normalized_path,
        variables_json=(None if body.variables is None else __import__('json').dumps(body.variables)),
        extra_args_json=(__import__('json').dumps(extras) if extras else None),
    )
    with Session(engine) as session:
        session.add(preset)
        session.commit()
        session.refresh(preset)
        return preset


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: int) -> dict:
    with Session(engine) as session:
        preset = session.get(RobotPreset, preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        session.delete(preset)
        session.commit()
        return {"deleted": True}


@router.post("/run-preset/{preset_id}")
async def run_preset(preset_id: int, background_tasks: BackgroundTasks) -> dict:
    import json
    with Session(engine) as session:
        preset = session.get(RobotPreset, preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
    
    variables = json.loads(preset.variables_json) if preset.variables_json else None
    extra_args = json.loads(preset.extra_args_json) if preset.extra_args_json else None
    
    # Create run record
    with Session(engine) as session:
        run = RobotRun(suite_path=preset.suite_path, output_dir="", return_code=None, ok=False)
        session.add(run)
        session.commit()
        session.refresh(run)

    # Store initial running status
    running_tasks[run.id] = {
        "status": "running", 
        "start_time": datetime.now().isoformat(),
        "suite_path": preset.suite_path,
        "preset_name": preset.name
    }

    # Run in background
    background_tasks.add_task(
        execute_robot_suite,
        run.id,
        preset.suite_path,
        variables,
        extra_args
    )

    return {
        "run_id": run.id,
        "status": "running",
        "message": f"Preset '{preset.name}' execution started",
        "suite_path": preset.suite_path
    }