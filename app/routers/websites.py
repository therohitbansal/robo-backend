from typing import List
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from ..db import engine
from ..models import WebsiteCheck, WebsiteRun
from ..services.http_check import perform_http_request

router = APIRouter()


@router.get("/checks", response_model=List[WebsiteCheck])
def list_checks() -> List[WebsiteCheck]:
    with Session(engine) as session:
        return session.exec(select(WebsiteCheck).order_by(WebsiteCheck.id.desc())).all()

# ADD THIS ENDPOINT - This provides status information for the frontend
@router.get("/checks-with-status")
def list_checks_with_status() -> List[dict]:
    with Session(engine) as session:
        checks = session.exec(select(WebsiteCheck).order_by(WebsiteCheck.id.desc())).all()
        result = []
        
        for check in checks:
            # Get the latest run for each check
            latest_run = session.exec(
                select(WebsiteRun)
                .where(WebsiteRun.website_id == check.id)
                .order_by(WebsiteRun.id.desc())
                .limit(1)
            ).first()
            
            result.append({
                "id": check.id,
                "url": check.url,
                "label": check.label,
                "last_status": latest_run.ok if latest_run else None,
                "last_checked": latest_run.created_at if latest_run else None,
                "latency_ms": latest_run.latency_ms if latest_run else None,
                "status_code": latest_run.status_code if latest_run else None
            })
        
        return result

@router.post("/checks", response_model=WebsiteCheck)
def create_check(check: WebsiteCheck) -> WebsiteCheck:
    with Session(engine) as session:
        session.add(check)
        session.commit()
        session.refresh(check)
        return check

@router.delete("/checks/{check_id}")
def delete_check(check_id: int) -> dict:
    with Session(engine) as session:
        check = session.get(WebsiteCheck, check_id)
        if not check:
            raise HTTPException(status_code=404, detail="Check not found")
        session.delete(check)
        session.commit()
        return {"deleted": True}

@router.post("/run/{check_id}")
async def run_single_check(check_id: int) -> dict:
    with Session(engine) as session:
        check = session.get(WebsiteCheck, check_id)
        if not check:
            raise HTTPException(status_code=404, detail="Check not found")
    
    # Use shorter timeout for faster response
    result = await perform_http_request("GET", check.url, timeout_s=8.0)
    
    run = WebsiteRun(
        website_id=check_id,
        ok=bool(result.get("ok")),
        latency_ms=result.get("latency_ms"),
        status_code=result.get("status_code"),
        error=result.get("error"),
    )
    
    with Session(engine) as session:
        session.add(run)
        session.commit()
    
    return result

@router.post("/run-all")
async def run_all_checks() -> List[dict]:
    with Session(engine) as session:
        checks = session.exec(select(WebsiteCheck)).all()
    
    results: List[dict] = []
    for c in checks:
        # Use shorter timeout for faster response
        result = await perform_http_request("GET", c.url, timeout_s=8.0)
        run = WebsiteRun(
            website_id=c.id,
            ok=bool(result.get("ok")),
            latency_ms=result.get("latency_ms"),
            status_code=result.get("status_code"),
            error=result.get("error"),
        )
        with Session(engine) as session:
            session.add(run)
            session.commit()
        results.append({"id": c.id, "label": c.label, "url": c.url, **result})
    
    return results