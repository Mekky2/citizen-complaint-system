from typing import TypedDict, List, Optional


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
    severity: Optional[str]
    recommendations: List[str]
    tool_calls: int
    error: Optional[str]
    assigned_department: Optional[str]