from datetime import datetime, timezone
from typing import Optional


from sqlmodel import Field, SQLModel


class ApiEndpoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    method: str = Field(description="HTTP method: GET, POST, etc.")
    url: str
    headers_json: Optional[str] = Field(default=None, description="JSON string of headers")
    body_json: Optional[str] = Field(default=None, description="JSON string of body")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebsiteCheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    label: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ApiRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint_id: int = Field(foreign_key="apiendpoint.id")
    status_code: Optional[int] = None
    ok: bool = False
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WebsiteRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    website_id: int = Field(foreign_key="websitecheck.id")
    ok: bool = False
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RobotRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    suite_path: str
    output_dir: str
    return_code: Optional[int] = None
    ok: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RobotPreset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    suite_path: str
    variables_json: Optional[str] = None
    extra_args_json: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

