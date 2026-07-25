from typing import Optional

from pydantic import BaseModel


class PersonNode(BaseModel):
    person_id: str
    full_name: str
    gender: str
    age: int
    address_district: str
    address_state: str
    roles: list[str]  # e.g. ["ACCUSED"], ["ACCUSED", "VICTIM"] across different FIRs
    prior_case_count: int = 0
    risk_tier: Optional[str] = None
    degree: int = 0


class NetworkEdgeOut(BaseModel):
    person_id_a: str
    person_id_b: str
    shared_fir_count: int
    fir_ids: list[str]


class GraphResponse(BaseModel):
    nodes: list[PersonNode]
    edges: list[NetworkEdgeOut]
    node_count: int
    edge_count: int


class EgoNetworkResponse(BaseModel):
    center: PersonNode
    depth: int
    nodes: list[PersonNode]
    edges: list[NetworkEdgeOut]


class CommunityOut(BaseModel):
    community_id: int
    size: int
    member_ids: list[str]
    core_member_id: str
    core_member_name: str
    internal_edge_count: int
    total_shared_cases: int
    distinct_crime_types: list[str]


class HubOut(BaseModel):
    person_id: str
    full_name: str
    degree: int
    betweenness: float
    risk_tier: Optional[str]
    prior_case_count: int


class PathHop(BaseModel):
    person_id_a: str
    person_id_b: str
    shared_fir_count: int
    fir_ids: list[str]


class PathResponse(BaseModel):
    source: str
    target: str
    found: bool
    path: list[str] = []
    hops: list[PathHop] = []


class GraphStats(BaseModel):
    total_persons_in_network: int
    total_edges: int
    total_communities: int
    largest_community_size: int
    average_degree: float
    total_firs: int
    total_accused_links: int


class RepeatOffenderOut(BaseModel):
    person_id: str
    full_name: str
    address_district: str
    prior_case_count: int
    distinct_crime_types: list[str]
    used_weapon_ever: bool
    risk_tier: str
    network_degree: int
