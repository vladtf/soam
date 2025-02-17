import React, { useEffect, useRef } from 'react';
import * as rdflib from 'rdflib';
import * as d3 from 'd3';
import { Button } from 'react-bootstrap'; // new import

interface GraphNode {
  id: string;
  label: string;
  isClass: boolean; // true for class nodes, false for property nodes
}

interface GraphLink {
  source: string;
  target: string;
  label?: string;
}

const OntologyViewer: React.FC = () => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomRef = useRef<any>(null);

  useEffect(() => {
    async function loadOntologyAndRender() {
      const store = rdflib.graph();
      const fetcher = new rdflib.Fetcher(store, { fetch: window.fetch.bind(window) });
      const owlUrl = `${window.location.origin}/ontology.owl`;
      await fetcher.load(owlUrl);

      // Extract class nodes (OWL classes)
      const OWL_Class = rdflib.sym("http://www.w3.org/2002/07/owl#Class");
      const classStmts = store.statementsMatching(undefined, rdflib.sym("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), OWL_Class);
      const classNodes: GraphNode[] = classStmts.map(stmt => ({
        id: stmt.subject.value,
        label:
          store.any(stmt.subject, rdflib.sym("http://www.w3.org/2000/01/rdf-schema#label"))
            ?.value || stmt.subject.value,
        isClass: true
      }));
      // Remove duplicates
      const classNodesMap = new Map(classNodes.map(n => [n.id, n]));
      
      // Prepare maps for independent properties
      const independentPropNodesMap = new Map<string, GraphNode>();
      const links: GraphLink[] = [];
      
      // Process all property statements with domain
      const RDFS_DOMAIN = rdflib.sym("http://www.w3.org/2000/01/rdf-schema#domain");
      const RDFS_RANGE = rdflib.sym("http://www.w3.org/2000/01/rdf-schema#range");
      const allPropStmts = store.statementsMatching(undefined, RDFS_DOMAIN, undefined);
      allPropStmts.forEach(stmt => {
        const prop = stmt.subject;
        const domain = stmt.object;
        const rangeNode = store.any(prop, RDFS_RANGE);
        // Only consider if domain is not an XSD type
        if (domain.value.startsWith("http://www.w3.org/2001/XMLSchema#")) return;
        // If range exists and is not XSD, treat as connecting property.
        if (rangeNode && !rangeNode.value.startsWith("http://www.w3.org/2001/XMLSchema#")) {
          links.push({
            source: domain.value,
            target: rangeNode.value,
            label: store.any(prop, rdflib.sym("http://www.w3.org/2000/01/rdf-schema#label"))?.value || prop.value
          });
        } else if (rangeNode && rangeNode.value.startsWith("http://www.w3.org/2001/XMLSchema#")) {
          // Independent property: create a node for this property if not already created.
          if (!independentPropNodesMap.has(prop.value)) {
            const labelVal = store.any(prop, rdflib.sym("http://www.w3.org/2000/01/rdf-schema#label"))?.value || prop.value;
            independentPropNodesMap.set(prop.value, {
              id: prop.value,
              label: labelVal,
              isClass: false
            });
          }
          // Link from domain (class) to independent property node.
          links.push({
            source: domain.value,
            target: prop.value
          });
        }
      });
      
      const independentPropNodes = Array.from(independentPropNodesMap.values());
      
      // Combine class and independent property nodes.
      const nodes: GraphNode[] = [
        ...Array.from(classNodesMap.values()),
        ...independentPropNodes
      ];
      
      // Set up SVG and simulation
      const width = 800, height = 600;
      const svg = d3.select(svgRef.current)
        .attr("width", width)
        .attr("height", height);
      svg.selectAll("*").remove();
      
      // Create container group for zooming/panning
      const container = svg.append("g").attr("class", "container");
      zoomRef.current = d3.zoom().on("zoom", (event) => {
        container.attr("transform", event.transform);
      });
      svg.call(zoomRef.current);
      
      const simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(links).id((d: any) => d.id).distance(50)) // reduced distance from 150 to 80
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2));
      
      const link = container.append("g")
        .attr("class", "links")
        .selectAll("line")
        .data(links)
        .enter()
        .append("line")
        .attr("stroke-width", 1.2)
        .attr("stroke", "#999");
      
      const node = container.append("g")
        .attr("class", "nodes")
        .selectAll("circle")
        .data(nodes)
        .enter()
        .append("circle")
        .attr("r", (d: GraphNode) => d.isClass ? 15 : 5)
        .attr("fill", (d: GraphNode) => d.isClass ? "#69b3a2" : "#ffb347")
        .call(d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended))
        // Add hover and click event listeners
        .on("mouseover", function(event, d) {
          d3.select(this)
            .attr("stroke", "black")
            .attr("stroke-width", 2);
        })
        .on("mouseout", function(event, d) {
          d3.select(this)
            .attr("stroke", null)
            .attr("stroke-width", null);
        })
        .on("click", function(event, d) {
          alert("Node: " + d.label);
        });
      
      // Create edge labels for connecting properties only
      const edgeLabel = container.append("g")
        .attr("class", "edge-labels")
        .selectAll("text")
        .data(links.filter(l => l.label))
        .enter()
        .append("text")
        .attr("text-anchor", "middle")
        .attr("font-size", 10)
        .text((d: any) => d.label);
      
      const label = container.append("g")
        .attr("class", "labels")
        .selectAll("text")
        .data(nodes)
        .enter()
        .append("text")
        .attr("dy", (d: GraphNode) => d.isClass ? -20 : -8)
        .attr("text-anchor", "middle")
        .text((d: GraphNode) => d.label);
      
      simulation.on("tick", () => {
        link
          .attr("x1", (d: any) => d.source.x)
          .attr("y1", (d: any) => d.source.y)
          .attr("x2", (d: any) => d.target.x)
          .attr("y2", (d: any) => d.target.y);
        node
          .attr("cx", (d: any) => d.x)
          .attr("cy", (d: any) => d.y);
        label
          .attr("x", (d: any) => d.x)
          .attr("y", (d: any) => d.y);
        edgeLabel
          .attr("x", (d: any) => (d.source.x + d.target.x) / 2)
          .attr("y", (d: any) => (d.source.y + d.target.y) / 2);
      });
      
      function dragstarted(event: any, d: any) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      }
      function dragged(event: any, d: any) {
        d.fx = event.x;
        d.fy = event.y;
      }
      function dragended(event: any, d: any) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }
    }
    
    loadOntologyAndRender();
  }, []);
  
  // Navigation buttons
  const zoomIn = () => {
    if (zoomRef.current && svgRef.current) {
      d3.select(svgRef.current)
        .transition()
        .call(zoomRef.current.scaleBy, 1.2);
    }
  };
  const zoomOut = () => {
    if (zoomRef.current && svgRef.current) {
      d3.select(svgRef.current)
        .transition()
        .call(zoomRef.current.scaleBy, 0.8);
    }
  };
  const resetZoom = () => {
    if (zoomRef.current && svgRef.current) {
      d3.select(svgRef.current)
        .transition()
        .call(zoomRef.current.transform, d3.zoomIdentity);
    }
  };

  return (
    <div style={{ width: '100%' }}>
      <div className="mb-2">
        <Button variant="primary" onClick={zoomIn} className="me-2">Zoom In</Button>
        <Button variant="secondary" onClick={zoomOut} className="me-2">Zoom Out</Button>
        <Button variant="outline-dark" onClick={resetZoom}>Reset</Button>
      </div>
      <svg ref={svgRef} style={{ width: '100%', border: "1px solid black" }}></svg>
    </div>
  );
};

export default OntologyViewer;
