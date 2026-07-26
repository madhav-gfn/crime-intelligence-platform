import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { PersonNode, NetworkEdgeOut } from '../../types/api';

interface NetworkGraphProps {
  nodes: PersonNode[];
  edges: NetworkEdgeOut[];
  onNodeClick: (node: PersonNode) => void;
  highlightedNodes?: string[];
  pathHops?: { person_id_a: string; person_id_b: string }[];
}

export default function NetworkGraph({ nodes, edges, onNodeClick, highlightedNodes = [], pathHops = [] }: NetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!containerRef.current || !svgRef.current || !nodes.length) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous render

    const g = svg.append("g");

    // Setup zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (e) => g.attr("transform", e.transform));
    svg.call(zoom);

    // Color scale for risk tier
    const colorForTier = (tier?: string | null) => {
      switch (tier) {
        case 'HIGH': return 'var(--risk-high)';
        case 'MEDIUM': return 'var(--risk-medium)';
        case 'LOW': return 'var(--risk-low)';
        default: return 'var(--text-dim)';
      }
    };

    // Calculate path edge set for fast lookup
    const pathEdgeSet = new Set(
      pathHops.map(h => `${h.person_id_a}-${h.person_id_b}`).concat(
      pathHops.map(h => `${h.person_id_b}-${h.person_id_a}`))
    );

    const isPathEdge = (d: any) => {
      return pathEdgeSet.has(`${d.source.person_id}-${d.target.person_id}`);
    };

    // Format edges for D3
    const simEdges = edges.map((e: any) => ({ ...e, source: e.person_id_a, target: e.person_id_b }));

    // Force simulation
    const simulation = d3.forceSimulation(nodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(simEdges).id((d: any) => d.person_id).distance(50))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide().radius((d: any) => Math.sqrt(d.degree || 1) * 3 + 10));

    // Draw links
    const link = g.append("g")
      .selectAll("line")
      .data(simEdges)
      .join("line")
      .attr("stroke", (d: any) => isPathEdge(d) ? "var(--accent-cyan)" : "var(--border-bright)")
      .attr("stroke-width", (d: any) => isPathEdge(d) ? 3 : Math.sqrt(d.shared_fir_count || 1))
      .attr("stroke-opacity", 0.6);

    // Draw nodes
    const node = g.append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d: any) => Math.max(5, Math.min(25, Math.sqrt(d.degree || 1) * 3)))
      .attr("fill", (d: any) => colorForTier(d.risk_tier))
      .attr("stroke", (d: any) => {
        if (highlightedNodes.includes(d.person_id)) return "var(--accent-cyan)";
        return "var(--bg-base)";
      })
      .attr("stroke-width", (d: any) => highlightedNodes.includes(d.person_id) ? 3 : 1.5)
      .style("cursor", "pointer")
      .on("click", (_e, d: any) => onNodeClick(d));

    node.append("title").text((d: any) => `${d.full_name}\n${d.person_id}\nDegree: ${d.degree}`);

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node
        .attr("cx", (d: any) => d.x = Math.max(20, Math.min(width - 20, d.x)))
        .attr("cy", (d: any) => d.y = Math.max(20, Math.min(height - 20, d.y)));
    });

    return () => { simulation.stop(); };
  }, [nodes, edges, highlightedNodes, pathHops]);

  return (
    <div ref={containerRef} className="graph-container">
      <svg ref={svgRef} className="graph-svg" />
    </div>
  );
}
