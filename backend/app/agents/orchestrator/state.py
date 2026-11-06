from typing import TypedDict


class Citizen(TypedDict):
    name: str
    national_id: str


class Location(TypedDict):
    lat: float
    lon: float


class Payload(TypedDict):
    authority: str
    description: str
    location: Location
    citizen: Citizen


class OrchestratorState(TypedDict):
    ticket_id: str
    status: str
    payload: Payload
    severity: str | None
    recommendations: list[str]
    tool_calls: int
    error: str | None
    assigned_department: str | None
