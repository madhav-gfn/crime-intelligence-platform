"""
Loads the synthetic seed dataset (data/seed/, see data/schemas/synthetic_fir_schema.md)
into memory and builds the co-accused network graph. This is a simple
in-memory store sized for a demo dataset (~11k persons, ~5k edges) - swap
for a real graph database (Neo4j/etc.) behind the same query methods when
this moves past prototype scale.
"""
from collections import defaultdict
from pathlib import Path

import networkx as nx
import pandas as pd

from app.config import settings
from app.schemas import PersonNode


class GraphStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.person_df: pd.DataFrame | None = None
        self.fir_df: pd.DataFrame | None = None
        self.link_df: pd.DataFrame | None = None
        self.edge_df: pd.DataFrame | None = None
        self.offender_df: pd.DataFrame | None = None
        self.graph = nx.Graph()
        self.person_roles: dict[str, set[str]] = defaultdict(set)
        self.person_fir_links: dict[str, list[dict]] = defaultdict(list)
        self._communities_cache: list[set[str]] | None = None

    def load(self):
        d = self.data_dir
        self.person_df = pd.read_csv(d / "person.csv").set_index("person_id", drop=False)
        # fir_id (real FIR CrimeNo, e.g. "103541451202000002") is all-digit and
        # pandas otherwise silently infers it as int64 - force str so lookups
        # against string fir_ids elsewhere (e.g. network_edge.csv) actually match.
        self.fir_df = pd.read_csv(d / "fir.csv", dtype={"fir_id": str}).set_index("fir_id", drop=False)
        self.link_df = pd.read_csv(d / "fir_person_link.csv", dtype={"fir_id": str})
        self.edge_df = pd.read_csv(d / "network_edge.csv")
        self.offender_df = pd.read_csv(d / "offender_profile.csv").set_index("person_id", drop=False)

        for row in self.link_df.itertuples():
            self.person_roles[row.person_id].add(row.role)
            self.person_fir_links[row.person_id].append({
                "fir_id": row.fir_id,
                "role": row.role,
                "relationship_to_victim": row.relationship_to_victim if isinstance(row.relationship_to_victim, str) else None,
            })

        for row in self.edge_df.itertuples():
            fir_ids = row.fir_ids.split("|") if isinstance(row.fir_ids, str) else []
            self.graph.add_edge(row.person_id_a, row.person_id_b, weight=int(row.shared_fir_count), fir_ids=fir_ids)

        self._communities_cache = None
        return self

    # ---- node/person helpers -------------------------------------------------

    def _person_row(self, person_id: str) -> dict | None:
        if self.person_df is None or person_id not in self.person_df.index:
            return None
        return self.person_df.loc[person_id].to_dict()

    def to_person_node(self, person_id: str) -> PersonNode | None:
        row = self._person_row(person_id)
        if row is None:
            return None
        offender_row = self.offender_df.loc[person_id].to_dict() if person_id in self.offender_df.index else None
        return PersonNode(
            person_id=person_id,
            full_name=row["full_name"],
            gender=row["gender"],
            age=int(row["age"]),
            address_district=row["address_district"],
            address_state=row["address_state"],
            roles=sorted(self.person_roles.get(person_id, set())),
            prior_case_count=int(offender_row["prior_case_count"]) if offender_row else 0,
            risk_tier=offender_row["risk_tier"] if offender_row else None,
            degree=self.graph.degree(person_id) if person_id in self.graph else 0,
        )

    # ---- graph views -----------------------------------------------------

    def graph_view(self, district: str | None = None, min_shared_cases: int = 1, limit_nodes: int | None = None):
        edges = [
            (a, b, d) for a, b, d in self.graph.edges(data=True)
            if d["weight"] >= min_shared_cases
        ]
        node_ids = set()
        for a, b, _ in edges:
            node_ids.add(a)
            node_ids.add(b)

        if district:
            district_lower = district.lower()
            node_ids = {
                pid for pid in node_ids
                if pid in self.person_df.index and district_lower in str(self.person_df.loc[pid, "address_district"]).lower()
            }
            edges = [(a, b, d) for a, b, d in edges if a in node_ids and b in node_ids]

        nodes = [self.to_person_node(pid) for pid in node_ids]
        nodes = [n for n in nodes if n is not None]
        nodes.sort(key=lambda n: -n.degree)
        if limit_nodes:
            keep_ids = {n.person_id for n in nodes[:limit_nodes]}
            nodes = nodes[:limit_nodes]
            edges = [(a, b, d) for a, b, d in edges if a in keep_ids and b in keep_ids]

        edge_out = [
            {"person_id_a": a, "person_id_b": b, "shared_fir_count": d["weight"], "fir_ids": d["fir_ids"]}
            for a, b, d in edges
        ]
        return nodes, edge_out

    def ego_network(self, person_id: str, depth: int = 1):
        if person_id not in self.graph:
            return None
        nodes_in_range = nx.single_source_shortest_path_length(self.graph, person_id, cutoff=depth).keys()
        sub = self.graph.subgraph(nodes_in_range)
        nodes = [self.to_person_node(pid) for pid in sub.nodes()]
        edges = [
            {"person_id_a": a, "person_id_b": b, "shared_fir_count": d["weight"], "fir_ids": d["fir_ids"]}
            for a, b, d in sub.edges(data=True)
        ]
        return nodes, edges

    # ---- analytics ---------------------------------------------------------

    def communities(self, min_size: int = 3):
        if self._communities_cache is None:
            self._communities_cache = nx.algorithms.community.louvain_communities(
                self.graph, weight="weight", seed=42
            )
        results = []
        for idx, members in enumerate(self._communities_cache):
            if len(members) < min_size:
                continue
            sub = self.graph.subgraph(members)
            degrees = dict(sub.degree(weight="weight"))
            core_id = max(degrees, key=degrees.get)
            core_row = self._person_row(core_id)
            crime_types = set()
            total_shared = 0
            for _, _, d in sub.edges(data=True):
                total_shared += d["weight"]
                for fir_id in d["fir_ids"]:
                    if fir_id in self.fir_df.index:
                        crime_types.add(self.fir_df.loc[fir_id, "crime_type_code"])
            results.append({
                "community_id": idx,
                "size": len(members),
                "member_ids": sorted(members),
                "core_member_id": core_id,
                "core_member_name": core_row["full_name"] if core_row else core_id,
                "internal_edge_count": sub.number_of_edges(),
                "total_shared_cases": total_shared,
                "distinct_crime_types": sorted(crime_types),
            })
        results.sort(key=lambda c: -c["size"])
        return results

    def hubs(self, top_n: int = 20):
        betweenness = nx.betweenness_centrality(self.graph, normalized=True)
        rows = []
        for pid, degree in self.graph.degree():
            offender_row = self.offender_df.loc[pid].to_dict() if pid in self.offender_df.index else None
            person_row = self._person_row(pid)
            if person_row is None:
                continue
            rows.append({
                "person_id": pid,
                "full_name": person_row["full_name"],
                "degree": degree,
                "betweenness": round(betweenness.get(pid, 0.0), 6),
                "risk_tier": offender_row["risk_tier"] if offender_row else None,
                "prior_case_count": int(offender_row["prior_case_count"]) if offender_row else 0,
            })
        rows.sort(key=lambda r: (-r["degree"], -r["betweenness"]))
        return rows[:top_n]

    def shortest_path(self, source: str, target: str):
        if source not in self.graph or target not in self.graph:
            return {"source": source, "target": target, "found": False, "path": [], "hops": []}
        try:
            path = nx.shortest_path(self.graph, source, target)
        except nx.NetworkXNoPath:
            return {"source": source, "target": target, "found": False, "path": [], "hops": []}
        hops = []
        for a, b in zip(path[:-1], path[1:]):
            d = self.graph.get_edge_data(a, b)
            hops.append({"person_id_a": a, "person_id_b": b, "shared_fir_count": d["weight"], "fir_ids": d["fir_ids"]})
        return {"source": source, "target": target, "found": True, "path": path, "hops": hops}

    def stats(self):
        communities = self.communities(min_size=1)
        degrees = [d for _, d in self.graph.degree()]
        return {
            "total_persons_in_network": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "total_communities": len(communities),
            "largest_community_size": max((c["size"] for c in communities), default=0),
            "average_degree": round(sum(degrees) / len(degrees), 2) if degrees else 0.0,
            "total_firs": len(self.fir_df),
            "total_accused_links": int((self.link_df["role"] == "ACCUSED").sum()),
        }

    def repeat_offenders(self, min_cases: int = 2, limit: int = 50):
        df = self.offender_df[self.offender_df["prior_case_count"] >= min_cases].copy()
        df = df.sort_values("prior_case_count", ascending=False).head(limit)
        rows = []
        for pid, row in df.iterrows():
            person_row = self._person_row(pid)
            if person_row is None:
                continue
            crime_types = row["distinct_crime_types"].split("|") if isinstance(row["distinct_crime_types"], str) else []
            rows.append({
                "person_id": pid,
                "full_name": person_row["full_name"],
                "address_district": person_row["address_district"],
                "prior_case_count": int(row["prior_case_count"]),
                "distinct_crime_types": crime_types,
                "used_weapon_ever": bool(row["used_weapon_ever"]),
                "risk_tier": row["risk_tier"],
                "network_degree": self.graph.degree(pid) if pid in self.graph else 0,
            })
        return rows


store = GraphStore(settings.data_seed_dir)
