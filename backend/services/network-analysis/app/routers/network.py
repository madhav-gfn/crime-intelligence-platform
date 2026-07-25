from fastapi import APIRouter, Depends, HTTPException, Query

from app.graph_store import store
from app.rbac import require_role
from app.schemas import (
    CommunityOut, EgoNetworkResponse, GraphResponse, GraphStats, HubOut,
    NetworkEdgeOut, PathResponse, PersonNode, RepeatOffenderOut,
)

router = APIRouter(prefix="/api/network", tags=["network-analysis"])


@router.get("/stats", response_model=GraphStats)
def get_stats(claims: dict = Depends(require_role("ANALYST"))):
    return store.stats()


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    district: str | None = Query(None, description="Filter to accused persons in this district (substring match)"),
    min_shared_cases: int = Query(1, ge=1, description="Only include edges with at least this many shared FIRs"),
    limit_nodes: int | None = Query(300, description="Cap node count for renderable payload size; None = no cap"),
    claims: dict = Depends(require_role("INVESTIGATOR")),
):
    nodes, edges = store.graph_view(district=district, min_shared_cases=min_shared_cases, limit_nodes=limit_nodes)
    return GraphResponse(
        nodes=nodes,
        edges=[NetworkEdgeOut(**e) for e in edges],
        node_count=len(nodes),
        edge_count=len(edges),
    )


@router.get("/person/{person_id}", response_model=PersonNode)
def get_person(person_id: str, claims: dict = Depends(require_role("INVESTIGATOR"))):
    node = store.to_person_node(person_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"person_id '{person_id}' not found")
    return node


@router.get("/person/{person_id}/ego", response_model=EgoNetworkResponse)
def get_ego_network(
    person_id: str, depth: int = Query(1, ge=1, le=3), claims: dict = Depends(require_role("INVESTIGATOR")),
):
    center = store.to_person_node(person_id)
    if center is None:
        raise HTTPException(status_code=404, detail=f"person_id '{person_id}' not found")
    result = store.ego_network(person_id, depth=depth)
    if result is None:
        # valid person but no co-accused links - a network of one
        return EgoNetworkResponse(center=center, depth=depth, nodes=[center], edges=[])
    nodes, edges = result
    return EgoNetworkResponse(
        center=center, depth=depth, nodes=nodes, edges=[NetworkEdgeOut(**e) for e in edges]
    )


@router.get("/communities", response_model=list[CommunityOut])
def get_communities(
    min_size: int = Query(3, ge=2, description="Minimum group size to report as an organized cluster"),
    claims: dict = Depends(require_role("INVESTIGATOR")),
):
    return store.communities(min_size=min_size)


@router.get("/hubs", response_model=list[HubOut])
def get_hubs(top_n: int = Query(20, ge=1, le=200), claims: dict = Depends(require_role("INVESTIGATOR"))):
    return store.hubs(top_n=top_n)


@router.get("/path", response_model=PathResponse)
def get_path(source: str, target: str, claims: dict = Depends(require_role("INVESTIGATOR"))):
    if store.to_person_node(source) is None:
        raise HTTPException(status_code=404, detail=f"source '{source}' not found")
    if store.to_person_node(target) is None:
        raise HTTPException(status_code=404, detail=f"target '{target}' not found")
    return store.shortest_path(source, target)


@router.get("/repeat-offenders", response_model=list[RepeatOffenderOut])
def get_repeat_offenders(
    min_cases: int = Query(2, ge=1),
    limit: int = Query(50, ge=1, le=500),
    claims: dict = Depends(require_role("INVESTIGATOR")),
):
    return store.repeat_offenders(min_cases=min_cases, limit=limit)
