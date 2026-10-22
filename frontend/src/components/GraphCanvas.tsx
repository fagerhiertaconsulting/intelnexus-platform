"use client";

import React, { useEffect, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import {
  Entity,
  EntityType,
  GraphData,
  GraphMetrics,
  TransformInfo,
  TransformDryRunEstimate,
} from "@/types";
import { api } from "@/lib/api";
import TransformDryRunModal from "@/components/TransformDryRunModal";
import {
  Search,
  Filter,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Plus,
  Play,
  ShieldAlert,
  Link as LinkIcon,
  Activity,
  Layers,
  ChevronRight,
  X,
  FileCheck,
  MapPin,
  Trash2,
} from "lucide-react";

interface GraphCanvasProps {
  caseId: string;
  onRefreshStats?: () => void;
}

const TYPE_COLORS: Record<EntityType, string> = {
  person: "#10b981", // Emerald
  organization: "#f59e0b", // Amber
  domain: "#0284c7", // Sky blue
  ip: "#06b6d4", // Cyan
  email: "#6366f1", // Indigo
  phone: "#14b8a6", // Teal
  username: "#8b5cf6", // Violet
  crypto_wallet: "#f97316", // Orange
  location: "#ec4899", // Pink
  document: "#64748b", // Slate
  incident: "#f43f5e", // Rose
};

export default function GraphCanvas({ caseId, onRefreshStats }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [metrics, setMetrics] = useState<GraphMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [availableTransforms, setAvailableTransforms] = useState<TransformInfo[]>([]);
  const [executingTransform, setExecutingTransform] = useState(false);
  const [transformMessage, setTransformMessage] = useState<string | null>(null);

  // Dry-run modal state
  const [dryRunModalOpen, setDryRunModalOpen] = useState(false);
  const [selectedTransformForDryRun, setSelectedTransformForDryRun] = useState<TransformInfo | null>(null);
  const [dryRunEstimate, setDryRunEstimate] = useState<TransformDryRunEstimate | null>(null);
  const [loadingEstimate, setLoadingEstimate] = useState(false);
  const [dryRunError, setDryRunError] = useState<string | null>(null);

  // Filter state
  const [activeTypes, setActiveTypes] = useState<Set<string>>(
    new Set([
      "person",
      "organization",
      "domain",
      "ip",
      "email",
      "phone",
      "username",
      "crypto_wallet",
      "location",
      "document",
      "incident",
    ])
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [showMetricsModal, setShowMetricsModal] = useState(false);
  const [showAddNodeModal, setShowAddNodeModal] = useState(false);
  const [showAddEdgeModal, setShowAddEdgeModal] = useState(false);

  // Add node form
  const [newNodeName, setNewNodeName] = useState("");
  const [newNodeType, setNewNodeType] = useState<EntityType>("domain");
  const [newNodeAttrKey, setNewNodeAttrKey] = useState("");
  const [newNodeAttrVal, setNewNodeAttrVal] = useState("");

  // Add edge form
  const [edgeSourceId, setEdgeSourceId] = useState("");
  const [edgeTargetId, setEdgeTargetId] = useState("");
  const [edgeRelation, setEdgeRelation] = useState("ASSOCIATED_WITH");

  const loadGraph = async () => {
    try {
      setLoading(true);
      const data = await api.getGraph(caseId);
      setGraphData(data);
      const met = await api.getGraphMetrics(caseId);
      setMetrics(met);
    } catch (err: any) {
      console.error("Fel vid inladdning av graf:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      loadGraph();
    }
  }, [caseId]);

  // Initiera Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    // Bygg cytoscape elements
    const elements: any[] = [];

    graphData.nodes.forEach((n) => {
      const isVisible = activeTypes.has(n.data.type);
      const isSearchMatch =
        !searchQuery ||
        n.data.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.data.aliases?.some((a) => a.toLowerCase().includes(searchQuery.toLowerCase()));

      if (isVisible && isSearchMatch) {
        const isSanctioned = n.data.attributes?.sanctioned === true;
        const admCode =
          n.data.admiralty_code ||
          (n.data.source_reliability && n.data.info_credibility
            ? `${n.data.source_reliability}${n.data.info_credibility}`
            : null);
        const displayLabel = admCode ? `[${admCode}] ${n.data.label}` : n.data.label;

        elements.push({
          group: "nodes",
          data: {
            ...n.data,
            label: displayLabel,
            admiralty_code: admCode,
            color: TYPE_COLORS[n.data.type] || "#94a3b8",
            borderColor: isSanctioned ? "#ef4444" : admCode ? "#38bdf8" : "#1e293b",
            borderWidth: isSanctioned ? 4 : admCode ? 3 : 2,
          },
        });
      }
    });

    const activeNodeIds = new Set(elements.map((e) => e.data.id));

    graphData.edges.forEach((e) => {
      if (activeNodeIds.has(e.source) && activeNodeIds.has(e.target)) {
        elements.push({
          group: "edges",
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.data.label || e.data.relation_type,
          },
        });
      }
    });

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            color: "#f8fafc",
            "font-size": "11px",
            "font-family": "system-ui, sans-serif",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-background-color": "#090d16",
            "text-background-opacity": 0.8,
            "text-background-padding": "3px",
            "text-background-shape": "roundrectangle",
            width: 38,
            height: 38,
            "border-width": "data(borderWidth)",
            "border-color": "data(borderColor)",
            "overlay-padding": "4px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": "#38bdf8",
            "background-blacken": 0.2,
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#475569",
            "target-arrow-color": "#64748b",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "9px",
            color: "#94a3b8",
            "text-background-color": "#0b0f19",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
            "text-rotation": "autorotate",
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: 3,
            "line-color": "#38bdf8",
            "target-arrow-color": "#38bdf8",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        nodeRepulsion: () => 6000,
        idealEdgeLength: () => 100,
        edgeElasticity: () => 100,
      },
    });

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      setSelectedNode(node.data());
      // Hämta kompatibla transforms för denna nod
      api.getTransformsForEntity(node.data().id).then((res) => {
        setAvailableTransforms(res.available_transforms || []);
      });
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        setAvailableTransforms([]);
      }
    });

    cyRef.current = cy;

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [graphData, activeTypes, searchQuery]);

  const runLayout = (layoutName: string) => {
    if (!cyRef.current) return;
    (cyRef.current.layout as any)({ name: layoutName, animate: true, animationDuration: 500 }).run();
  };

  const handleInitiateTransform = async (transform: TransformInfo) => {
    if (!selectedNode) return;
    setSelectedTransformForDryRun(transform);
    setDryRunModalOpen(true);
    setLoadingEstimate(true);
    setDryRunError(null);
    try {
      const est = await api.dryRunTransform(transform.name, selectedNode.id);
      setDryRunEstimate(est);
    } catch (err: any) {
      setDryRunError(err.message || "Kunde inte beräkna kostnadsestimat");
    } finally {
      setLoadingEstimate(false);
    }
  };

  const handleConfirmExecuteTransform = async () => {
    if (!selectedTransformForDryRun || !selectedNode) return;
    try {
      setExecutingTransform(true);
      setTransformMessage(`Kör ${selectedTransformForDryRun.display_name}...`);
      const result = await api.executeTransform(selectedTransformForDryRun.name, selectedNode.id);
      if (result.success) {
        setTransformMessage(
          `Klart! Skapade ${result.entities?.length || 0} entiteter och ${result.relationships?.length || 0} kopplingar.`
        );
        await loadGraph();
        if (onRefreshStats) onRefreshStats();
        setDryRunModalOpen(false);
      } else {
        setDryRunError(`Fel: ${result.error_message}`);
      }
    } catch (err: any) {
      setDryRunError(`Körningsfel: ${err.message}`);
    } finally {
      setExecutingTransform(false);
      setTimeout(() => setTransformMessage(null), 6000);
    }
  };

  const handleRunTransform = async (transformName: string) => {
    if (!selectedNode) return;
    try {
      setExecutingTransform(true);
      setTransformMessage(`Kör ${transformName}...`);
      const result = await api.executeTransform(transformName, selectedNode.id);
      if (result.success) {
        setTransformMessage(
          `Klart! Skapade ${result.entities?.length || 0} entiteter och ${result.relationships?.length || 0} kopplingar.`
        );
        await loadGraph();
        if (onRefreshStats) onRefreshStats();
      } else {
        setTransformMessage(`Fel: ${result.error_message}`);
      }
    } catch (err: any) {
      setTransformMessage(`Körningsfel: ${err.message}`);
    } finally {
      setExecutingTransform(false);
      setTimeout(() => setTransformMessage(null), 6000);
    }
  };

  const handleCreateNode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNodeName.trim()) return;

    try {
      const attrs: Record<string, any> = {};
      if (newNodeAttrKey.trim() && newNodeAttrVal.trim()) {
        attrs[newNodeAttrKey.trim()] = newNodeAttrVal.trim();
      }

      await api.createEntity({
        case_id: caseId,
        type: newNodeType,
        name: newNodeName.trim(),
        attributes: attrs,
        provenance_source: "manual_entry",
        provenance_plugin: "investigator_canvas_add",
      });

      setNewNodeName("");
      setNewNodeAttrKey("");
      setNewNodeAttrVal("");
      setShowAddNodeModal(false);
      await loadGraph();
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Kunde inte skapa nod: ${err.message}`);
    }
  };

  const handleCreateEdge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!edgeSourceId || !edgeTargetId) return;

    try {
      await api.createRelationship({
        case_id: caseId,
        source_id: edgeSourceId,
        target_id: edgeTargetId,
        relation_type: edgeRelation,
        provenance_source: "manual_link",
      });

      setShowAddEdgeModal(false);
      await loadGraph();
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      alert(`Kunde inte skapa relation: ${err.message}`);
    }
  };

  const handleDeleteSelected = async () => {
    if (!selectedNode) return;
    if (confirm(`Radera entiteten '${selectedNode.label}' och dess relationer?`)) {
      await api.deleteEntity(selectedNode.id);
      setSelectedNode(null);
      await loadGraph();
      if (onRefreshStats) onRefreshStats();
    }
  };

  const toggleTypeFilter = (type: string) => {
    const next = new Set(activeTypes);
    if (next.has(type)) {
      next.delete(type);
    } else {
      next.add(type);
    }
    setActiveTypes(next);
  };

  return (
    <div className="relative w-full h-[calc(100vh-68px)] bg-[#090d16] overflow-hidden flex">
      {/* Grafens canvasyta */}
      <div className="relative flex-1 h-full">
        <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

        {/* Kontrollpanel (Verktygsfält överst) */}
        <div className="absolute top-4 left-4 z-10 flex flex-wrap items-center gap-2 bg-[#111827]/90 backdrop-blur-md p-2 rounded-xl border border-slate-800 shadow-xl">
          {/* Sökning */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Sök noder eller alias..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-900/80 text-xs text-slate-200 pl-9 pr-3 py-1.5 rounded-lg border border-slate-700 focus:outline-none focus:border-sky-500 w-48"
            />
          </div>

          <div className="h-5 w-[1px] bg-slate-700 mx-1" />

          {/* Knappar för att zooma & centrera */}
          <button
            onClick={() => cyRef.current?.fit(undefined, 30)}
            title="Centrera graf"
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.25)}
            title="Zooma in"
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
            title="Zooma ut"
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition"
          >
            <ZoomOut className="w-4 h-4" />
          </button>

          <div className="h-5 w-[1px] bg-slate-700 mx-1" />

          {/* Layout-väljare */}
          <select
            onChange={(e) => runLayout(e.target.value)}
            className="bg-slate-900/80 text-xs text-slate-300 px-2.5 py-1.5 rounded-lg border border-slate-700 focus:outline-none"
            defaultValue="cose"
          >
            <option value="cose">Force-Directed (Cose)</option>
            <option value="circle">Cirkel</option>
            <option value="concentric">Koncentrisk</option>
            <option value="breadthfirst">Hierarkisk</option>
            <option value="grid">Rutnät</option>
          </select>

          <div className="h-5 w-[1px] bg-slate-700 mx-1" />

          {/* Skapa nod / relation */}
          <button
            onClick={() => setShowAddNodeModal(true)}
            className="flex items-center gap-1 text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium px-2.5 py-1.5 rounded-lg transition shadow"
          >
            <Plus className="w-3.5 h-3.5" />
            Ny Nod
          </button>
          <button
            onClick={() => setShowAddEdgeModal(true)}
            className="flex items-center gap-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium px-2.5 py-1.5 rounded-lg transition border border-slate-700"
          >
            <LinkIcon className="w-3.5 h-3.5" />
            Koppla
          </button>

          <button
            onClick={() => setShowMetricsModal(true)}
            className="flex items-center gap-1 text-xs bg-slate-800 hover:bg-slate-700 text-amber-400 font-medium px-2.5 py-1.5 rounded-lg transition border border-slate-700"
          >
            <Activity className="w-3.5 h-3.5" />
            Grafmått
          </button>

          <button
            onClick={loadGraph}
            title="Ladda om graf"
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Filtreringsfält nertill */}
        <div className="absolute bottom-4 left-4 z-10 flex flex-wrap items-center gap-1.5 bg-[#111827]/80 backdrop-blur-md px-3 py-2 rounded-xl border border-slate-800 text-xs">
          <span className="text-slate-400 mr-1 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </span>
          {Object.entries(TYPE_COLORS).map(([type, color]) => {
            const isSelected = activeTypes.has(type);
            return (
              <button
                key={type}
                onClick={() => toggleTypeFilter(type)}
                className={`px-2 py-0.5 rounded-full flex items-center gap-1.5 transition text-[11px] ${
                  isSelected
                    ? "bg-slate-800 text-slate-200 border border-slate-600"
                    : "opacity-40 text-slate-500"
                }`}
              >
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                {type}
              </button>
            );
          })}
        </div>

        {/* Toast / Statusmeddelande vid transformkörning */}
        {transformMessage && (
          <div className="absolute top-20 left-1/2 -translate-x-1/2 z-20 bg-sky-950/90 text-sky-200 border border-sky-700/60 backdrop-blur-md px-4 py-2 rounded-lg text-xs shadow-2xl flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-sky-400" />
            {transformMessage}
          </div>
        )}
      </div>

      {/* Sidopanel: Detaljer om vald nod */}
      {selectedNode && (
        <div className="w-96 h-full bg-[#0f172a] border-l border-slate-800 p-5 overflow-y-auto flex flex-col justify-between shadow-2xl z-20">
          <div>
            {/* Header */}
            <div className="flex items-start justify-between pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: `${TYPE_COLORS[selectedNode.type as EntityType]}22`,
                      color: TYPE_COLORS[selectedNode.type as EntityType],
                    }}
                  >
                    {selectedNode.type}
                  </span>
                  {selectedNode.admiralty_code && (
                    <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-700/80 shadow-sm flex items-center gap-1">
                      <span>NATO:</span>
                      <span className="font-mono font-extrabold text-blue-200">[{selectedNode.admiralty_code}]</span>
                    </span>
                  )}
                </div>
                <h3 className="text-base font-bold text-slate-100 mt-1 break-words">
                  {selectedNode.label}
                </h3>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Konfidens & ID */}
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
              <span>Konfidens: {Math.round((selectedNode.confidence_score || 1) * 100)}%</span>
              <span className="text-[10px] font-mono text-slate-500 truncate max-w-[150px]">
                {selectedNode.id}
              </span>
            </div>

            {/* Varning om sanktionerad */}
            {selectedNode.attributes?.sanctioned && (
              <div className="mt-3 p-3 bg-rose-950/50 border border-rose-800/80 rounded-lg text-rose-300 text-xs flex items-start gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-rose-200">Sanktionsflagg Identifierad</div>
                  <div className="text-[11px] mt-0.5">
                    {selectedNode.attributes.sanctions_authority} - {selectedNode.attributes.sanctions_program}
                  </div>
                </div>
              </div>
            )}

            {/* Transforms: Datainsamling / Expansion */}
            <div className="mt-5">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1 mb-2">
                <Play className="w-3.5 h-3.5 text-sky-400" /> Kör OSINT-Transform
              </label>

              {availableTransforms.length > 0 ? (
                <div className="space-y-1.5">
                  {availableTransforms.map((t) => (
                    <button
                      key={t.name}
                      disabled={executingTransform}
                      onClick={() => handleInitiateTransform(t)}
                      className="w-full text-left p-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-sky-500/50 transition group flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-medium text-slate-200 group-hover:text-sky-400">
                          {t.display_name}
                        </div>
                        <div className="text-[10px] text-slate-400 line-clamp-1">{t.description}</div>
                      </div>
                      <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-sky-400 transition" />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-500 italic p-3 bg-slate-900/50 rounded-lg border border-slate-800">
                  Inga specifika transforms tillgängliga för nodtypen &quot;{selectedNode.type}&quot;.
                </div>
              )}
            </div>

            {/* Alias */}
            {selectedNode.aliases && selectedNode.aliases.length > 0 && (
              <div className="mt-5">
                <span className="text-xs font-semibold text-slate-400">Kända Alias</span>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {selectedNode.aliases.map((a: string, idx: number) => (
                    <span
                      key={idx}
                      className="text-[11px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded"
                    >
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Attribut */}
            <div className="mt-5">
              <span className="text-xs font-semibold text-slate-400">Attribut</span>
              <div className="mt-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800 max-h-48 overflow-y-auto">
                {Object.keys(selectedNode.attributes || {}).length > 0 ? (
                  <div className="space-y-1 text-xs">
                    {Object.entries(selectedNode.attributes).map(([k, v]) => (
                      <div key={k} className="flex justify-between border-b border-slate-900 pb-1">
                        <span className="text-slate-500 font-mono text-[11px]">{k}:</span>
                        <span className="text-slate-300 font-medium text-right max-w-[180px] truncate">
                          {typeof v === "object" ? JSON.stringify(v) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-slate-600 italic">Inga attribut registrerade</span>
                )}
              </div>
            </div>
          </div>

          {/* Åtgärder nertill */}
          <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
            <button
              onClick={handleDeleteSelected}
              className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 px-2 py-1 hover:bg-rose-950/40 rounded transition"
            >
              <Trash2 className="w-3.5 h-3.5" /> Radera
            </button>
            <span className="text-[10px] text-slate-500">
              {selectedNode.created_at ? new Date(selectedNode.created_at).toLocaleString() : ""}
            </span>
          </div>
        </div>
      )}

      {/* Modal: Skapa nod */}
      {showAddNodeModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#111827] border border-slate-700 w-full max-w-md rounded-2xl p-6 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="font-bold text-slate-100 flex items-center gap-2">
                <Plus className="w-4 h-4 text-sky-400" /> Lägg till ny utredningsnod (Seed)
              </h3>
              <button
                onClick={() => setShowAddNodeModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateNode} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Entitetstyp</label>
                <select
                  value={newNodeType}
                  onChange={(e) => setNewNodeType(e.target.value as EntityType)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:border-sky-500"
                >
                  <option value="domain">Domän (domain)</option>
                  <option value="person">Person (person)</option>
                  <option value="organization">Organisation / Företag (organization)</option>
                  <option value="ip">IP-adress (ip)</option>
                  <option value="username">Användarnamn / Alias (username)</option>
                  <option value="email">E-postadress (email)</option>
                  <option value="phone">Telefonnummer (phone)</option>
                  <option value="crypto_wallet">Kryptoplånbok (crypto_wallet)</option>
                  <option value="location">Plats / Adress (location)</option>
                  <option value="document">Dokument / Bild (document)</option>
                  <option value="incident">Incident / Varning (incident)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Namn eller Identifierare
                </label>
                <input
                  type="text"
                  placeholder="t.ex. evil-domain.com, John Doe, 192.168.1.1"
                  value={newNodeName}
                  onChange={(e) => setNewNodeName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:border-sky-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Attributnyckel</label>
                  <input
                    type="text"
                    placeholder="t.ex. country, org_number"
                    value={newNodeAttrKey}
                    onChange={(e) => setNewNodeAttrKey(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Värde</label>
                  <input
                    type="text"
                    placeholder="t.ex. SE, 556123-4567"
                    value={newNodeAttrVal}
                    onChange={(e) => setNewNodeAttrVal(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddNodeModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white"
                >
                  Avbryt
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium shadow"
                >
                  Skapa Nod
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Koppla relation */}
      {showAddEdgeModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#111827] border border-slate-700 w-full max-w-md rounded-2xl p-6 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="font-bold text-slate-100 flex items-center gap-2">
                <LinkIcon className="w-4 h-4 text-sky-400" /> Koppla relation mellan noder
              </h3>
              <button
                onClick={() => setShowAddEdgeModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateEdge} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Källnod (Från)</label>
                <select
                  value={edgeSourceId}
                  onChange={(e) => setEdgeSourceId(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                  required
                >
                  <option value="">Välj källnod...</option>
                  {graphData?.nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.data.label} ({n.data.type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Relationstyp</label>
                <select
                  value={edgeRelation}
                  onChange={(e) => setEdgeRelation(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                >
                  <option value="OWNS">OWNS (Äger)</option>
                  <option value="DIRECTOR_OF">DIRECTOR_OF (Ledamot/VD i)</option>
                  <option value="RESOLVES_TO">RESOLVES_TO (Uppslås till IP/Värd)</option>
                  <option value="SUBDOMAIN_OF">SUBDOMAIN_OF (Subdomän till)</option>
                  <option value="LOCATED_AT">LOCATED_AT (Placerad på adress/land)</option>
                  <option value="COMMUNICATES_WITH">COMMUNICATES_WITH (Kommunicerar med)</option>
                  <option value="HAS_ALIAS">HAS_ALIAS (Har alias)</option>
                  <option value="ASSOCIATED_WITH">ASSOCIATED_WITH (Associerad med)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Målnod (Till)</label>
                <select
                  value={edgeTargetId}
                  onChange={(e) => setEdgeTargetId(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                  required
                >
                  <option value="">Välj målnod...</option>
                  {graphData?.nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.data.label} ({n.data.type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddEdgeModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white"
                >
                  Avbryt
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium shadow"
                >
                  Koppla Relation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Grafmått & Centralitetsanalys */}
      {showMetricsModal && metrics && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#111827] border border-slate-700 w-full max-w-2xl rounded-2xl p-6 shadow-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="font-bold text-slate-100 flex items-center gap-2">
                <Activity className="w-5 h-5 text-amber-400" /> Nätverksanalys och Centralitetsmått
              </h3>
              <button
                onClick={() => setShowMetricsModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400 mt-2">
              Algoritmer (PageRank & Betweenness Centrality) identifierar nyckelaktörer, central
              infrastruktur och informationsflöden i nätverket.
            </p>

            <div className="mt-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Topp-aktörer (Influencers & Nyckelnoder)
              </h4>
              <div className="border border-slate-800 rounded-xl overflow-hidden text-xs">
                <table className="w-full text-left">
                  <thead className="bg-slate-900 text-slate-400">
                    <tr>
                      <th className="p-2.5">Nod</th>
                      <th className="p-2.5">Typ</th>
                      <th className="p-2.5">Nätverkspoäng</th>
                      <th className="p-2.5">PageRank</th>
                      <th className="p-2.5">Betweenness</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-slate-300">
                    {metrics.top_influencers.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-800/40">
                        <td className="p-2.5 font-medium text-slate-100">{item.name}</td>
                        <td className="p-2.5">
                          <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">
                            {item.type}
                          </span>
                        </td>
                        <td className="p-2.5 text-amber-400 font-semibold">{item.score}</td>
                        <td className="p-2.5 text-slate-400">{item.pagerank}</td>
                        <td className="p-2.5 text-slate-400">{item.betweenness}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end pt-4 mt-4 border-t border-slate-800">
              <button
                onClick={() => setShowMetricsModal(false)}
                className="px-4 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200"
              >
                Stäng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dry-Run Bekräftelse & FinOps Modal */}
      <TransformDryRunModal
        isOpen={dryRunModalOpen}
        onClose={() => setDryRunModalOpen(false)}
        onConfirm={handleConfirmExecuteTransform}
        transformInfo={selectedTransformForDryRun}
        targetNode={selectedNode}
        estimate={dryRunEstimate}
        loading={loadingEstimate}
        executing={executingTransform}
        errorMessage={dryRunError}
      />
    </div>
  );
}
