from typing import List

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from ..db import engine
from ..models import ApiEndpoint, ApiRun
from ..services.http_check import perform_http_request


router = APIRouter()


@router.get("/endpoints", response_model=List[ApiEndpoint])
def list_endpoints() -> List[ApiEndpoint]:
    with Session(engine) as session:
        return session.exec(select(ApiEndpoint).order_by(ApiEndpoint.id.desc())).all()


@router.post("/endpoints", response_model=ApiEndpoint)
def create_endpoint(endpoint: ApiEndpoint) -> ApiEndpoint:
    with Session(engine) as session:
        session.add(endpoint)
        session.commit()
        session.refresh(endpoint)
        return endpoint


@router.delete("/endpoints/{endpoint_id}")
def delete_endpoint(endpoint_id: int) -> dict:
    with Session(engine) as session:
        endpoint = session.get(ApiEndpoint, endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        session.delete(endpoint)
        session.commit()
        return {"deleted": True}


@router.post("/run/{endpoint_id}")
async def run_single_endpoint(endpoint_id: int) -> dict:
    with Session(engine) as session:
        endpoint = session.get(ApiEndpoint, endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")
    result = await perform_http_request(endpoint.method, endpoint.url, endpoint.headers_json, endpoint.body_json)
    run = ApiRun(
        endpoint_id=endpoint_id,
        status_code=result.get("status_code"),
        ok=bool(result.get("ok")),
        latency_ms=result.get("latency_ms"),
        error=result.get("error"),
    )
    with Session(engine) as session:
        session.add(run)
        session.commit()
    return result


@router.post("/run-all")
async def run_all_endpoints() -> List[dict]:
    with Session(engine) as session:
        endpoints = session.exec(select(ApiEndpoint)).all()
    results: List[dict] = []
    for ep in endpoints:
        result = await perform_http_request(ep.method, ep.url, ep.headers_json, ep.body_json)
        run = ApiRun(
            endpoint_id=ep.id,  # type: ignore[arg-type]
            status_code=result.get("status_code"),
            ok=bool(result.get("ok")),
            latency_ms=result.get("latency_ms"),
            error=result.get("error"),
        )
        with Session(engine) as session:
            session.add(run)
            session.commit()
        results.append({"id": ep.id, "name": ep.name, **result})
    return results

