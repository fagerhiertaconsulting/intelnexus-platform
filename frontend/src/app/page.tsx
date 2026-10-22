"use client";

import React, { useEffect, useState } from "react";
import { Case } from "@/types";
import { api } from "@/lib/api";
import GraphCanvas from "@/components/GraphCanvas";
import TimelineView from "@/components/TimelineView";
import MapView from "@/components/MapView";
import EvidenceView from "@/components/EvidenceView";
import AnalysisReportView from "@/components/AnalysisReportView";
import CaseManagerModal from "@/components/CaseManagerModal";
import {
  Network,
  Clock,
  MapPin,
  Lock,
  FileText,
  FolderOpen,
  ChevronDown,
  ShieldAlert,
  Download,
  Terminal,
} from "lucide-react";

type ActiveTab = "graph" | "timeline" | "map" | "evidence" | "analysis";

export default function Home() {
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("graph");
  const [stats, setStats] = useState<any>(null);
  const [showCaseModal, setShowCaseModal] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadCases = async () => {
    try {
      setLoading(true);
      const data = await api.listCases();
      setCases(data);
      if (data.length > 0 && !activeCaseId) {
        setActiveCaseId(data[0].id);
      }
    } catch (err) {
      console.error("Kunde inte hämta ärenden:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async (cid: string) => {
    try {
      const s = await api.getCaseStats(cid);
      setStats(s);
    } catch (err) {
      console.error("Kunde inte hämta statistik:", err);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  useEffect(() => {
    if (activeCaseId) {
      loadStats(activeCaseId);
    }
  }, [activeCaseId]);

  const activeCase = cases.find((c) => c.id === activeCaseId);

  const handleExportGexf = () => {
    if (!activeCaseId) return;
    window.open(`http://localhost:8000/api/graph/${activeCaseId}/export/gexf`, "_blank");
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#090d16]">
      {/* Översta Navigationsbaren */}
      <header className="h-[68px] bg-[#0c121e] border-b border-slate-800/80 px-5 flex items-center justify-between shrink-0 z-30 shadow-md">
        {/* Vänster: Logotyp & Ärendeväljare */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-600 flex items-center justify-center shadow-lg shadow-sky-600/30">
              <Network className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-bold text-sm tracking-wide text-slate-100 flex items-center gap-1.5">
                OpenIntel<span className="text-sky-400">OSINT</span>
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                  v1.0
                </span>
              </div>
              <div className="text-[10px] text-slate-400">Länk- & Grafanalysplattform</div>
            </div>
          </div>

          <div className="h-6 w-[1px] bg-slate-800" />

          {/* Ärendeväljare */}
          <button
            onClick={() => setShowCaseModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/80 hover:bg-slate-850 border border-slate-700/80 hover:border-slate-600 transition group max-w-xs"
          >
            <FolderOpen className="w-4 h-4 text-sky-400 shrink-0" />
            <div className="text-left truncate">
              <div className="text-xs font-semibold text-slate-200 truncate group-hover:text-white">
                {activeCase?.title || "Välj utredningsärende..."}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                {activeCase?.priority ? `Prioritet: ${activeCase.priority.toUpperCase()}` : ""}
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0 ml-1" />
          </button>
        </div>

        {/* Mitten: Modul- & Vyväljare */}
        <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab("graph")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "graph"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            Grafduk
          </button>

          <button
            onClick={() => setActiveTab("timeline")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "timeline"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            Tidslinje
          </button>

          <button
            onClick={() => setActiveTab("map")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "map"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <MapPin className="w-3.5 h-3.5" />
            Kartvy
          </button>

          <button
            onClick={() => setActiveTab("evidence")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "evidence"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            Beviskedja
          </button>

          <button
            onClick={() => setActiveTab("analysis")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "analysis"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Rapport & NLP
          </button>
        </div>

        {/* Höger: Statistik & Export */}
        <div className="flex items-center gap-3">
          {stats && (
            <div className="hidden lg:flex items-center gap-2 text-xs">
              <span className="bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-lg text-slate-300">
                <strong className="text-sky-400">{stats.entity_count}</strong> entiteter
              </span>
              <span className="bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-lg text-slate-300">
                <strong className="text-amber-400">{stats.relationship_count}</strong> relationer
              </span>
              <span className="bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-lg text-slate-300">
                <strong className="text-emerald-400">{stats.evidence_count}</strong> bevis
              </span>
              {stats.sanctions_hits > 0 && (
                <span className="bg-rose-950/80 border border-rose-800 px-2.5 py-1 rounded-lg text-rose-300 font-semibold flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                  {stats.sanctions_hits} Sanktion
                </span>
              )}
            </div>
          )}

          <button
            onClick={handleExportGexf}
            title="Exportera grafen som GEXF för Gephi"
            className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition"
          >
            <Download className="w-3.5 h-3.5 text-slate-400" />
            Exportera GEXF
          </button>
        </div>
      </header>

      {/* Huvudinnehåll */}
      <main className="flex-1 w-full h-[calc(100vh-68px)] relative">
        {loading ? (
          <div className="flex items-center justify-center h-full text-slate-400 text-sm">
            Initierar OpenIntel utredningsmiljö...
          </div>
        ) : !activeCaseId ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-3">
            <FolderOpen className="w-12 h-12 text-slate-600" />
            <div className="text-base font-semibold text-slate-200">Inget ärende valt</div>
            <button
              onClick={() => setShowCaseModal(true)}
              className="bg-sky-600 hover:bg-sky-500 text-white text-xs px-4 py-2 rounded-lg font-medium shadow"
            >
              Öppna eller skapa ärende
            </button>
          </div>
        ) : (
          <>
            {activeTab === "graph" && (
              <GraphCanvas
                caseId={activeCaseId}
                onRefreshStats={() => loadStats(activeCaseId)}
              />
            )}
            {activeTab === "timeline" && <TimelineView caseId={activeCaseId} />}
            {activeTab === "map" && <MapView caseId={activeCaseId} />}
            {activeTab === "evidence" && <EvidenceView caseId={activeCaseId} />}
            {activeTab === "analysis" && (
              <AnalysisReportView
                caseId={activeCaseId}
                onDataChanged={() => loadStats(activeCaseId)}
              />
            )}
          </>
        )}
      </main>

      {/* Ärendehanterings-modal */}
      {showCaseModal && (
        <CaseManagerModal
          cases={cases}
          activeCaseId={activeCaseId}
          onSelectCase={(id) => setActiveCaseId(id)}
          onClose={() => setShowCaseModal(false)}
          onCaseCreated={() => loadCases()}
        />
      )}
    </div>
  );
}
