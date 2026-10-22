"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { MatchCandidate, Entity } from "@/types";
import {
  FileText,
  Sparkles,
  GitMerge,
  Download,
  Printer,
  Check,
  RefreshCw,
  Search,
  ArrowRight,
  ShieldAlert,
} from "lucide-react";

interface AnalysisReportViewProps {
  caseId: string;
  onDataChanged?: () => void;
}

export default function AnalysisReportView({ caseId, onDataChanged }: AnalysisReportViewProps) {
  const [activeTab, setActiveTab] = useState<"report" | "ner" | "resolution">("report");

  // Report state
  const [markdownReport, setMarkdownReport] = useState<string>("");
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportMode, setReportMode] = useState<"full" | "sanitized">("full");
  const [reportLocale, setReportLocale] = useState<"sv" | "en" | "uk">("sv");

  // NER state
  const [nerText, setNerText] = useState("");
  const [nerRunning, setNerRunning] = useState(false);
  const [extractedEntities, setExtractedEntities] = useState<Entity[]>([]);
  const [autoCommit, setAutoCommit] = useState(true);
  const [nerStatus, setNerStatus] = useState<string | null>(null);

  // Resolution state
  const [matches, setMatches] = useState<MatchCandidate[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [merging, setMerging] = useState(false);

  const loadReport = async () => {
    try {
      setLoadingReport(true);
      const res = await fetch(api.getMarkdownReportUrl(caseId, reportMode, reportLocale));
      if (res.ok) {
        const text = await res.text();
        setMarkdownReport(text);
      }
    } catch (err) {
      console.error("Kunde inte hämta rapport:", err);
    } finally {
      setLoadingReport(false);
    }
  };

  const loadResolutionMatches = async () => {
    try {
      setLoadingMatches(true);
      const data = await api.findMatches(caseId, 0.82);
      setMatches(data);
    } catch (err) {
      console.error("Kunde inte hämta entitetsmatchningar:", err);
    } finally {
      setLoadingMatches(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      if (activeTab === "report") loadReport();
      if (activeTab === "resolution") loadResolutionMatches();
    }
  }, [caseId, activeTab, reportMode, reportLocale]);

  const handleRunNer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nerText.trim()) return;

    try {
      setNerRunning(true);
      setNerStatus("Kör NLP- och mönsteranalys...");
      const res = await api.extractNer(nerText, caseId, autoCommit);
      setExtractedEntities(res.entities);
      setNerStatus(`Klart! Identifierade ${res.extracted_count} entiteter.`);
      if (autoCommit && onDataChanged) onDataChanged();
    } catch (err: any) {
      setNerStatus(`Fel: ${err.message}`);
    } finally {
      setNerRunning(false);
    }
  };

  const handleMerge = async (match: MatchCandidate) => {
    try {
      setMerging(true);
      await api.mergeEntities(match.primary_entity_id, match.secondary_entity_id, caseId);
      await loadResolutionMatches();
      if (onDataChanged) onDataChanged();
      alert(`Slog samman '${match.secondary_name}' med '${match.primary_name}'!`);
    } catch (err: any) {
      alert(`Sammanslagningsfel: ${err.message}`);
    } finally {
      setMerging(false);
    }
  };

  const downloadMarkdown = () => {
    const blob = new Blob([markdownReport], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `utredningsrapport_${caseId}_${reportMode}_${reportLocale}.md`;
    a.click();
  };

  const openPrintableReport = () => {
    window.open(api.getHtmlReportUrl(caseId, reportMode, reportLocale), "_blank");
  };

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] p-6 overflow-y-auto">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Navigationstabbar */}
        <div className="flex border-b border-slate-800 gap-2">
          <button
            onClick={() => setActiveTab("report")}
            className={`flex items-center gap-2 pb-3 px-3 text-xs font-semibold border-b-2 transition ${
              activeTab === "report"
                ? "border-sky-500 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-4 h-4" /> Utredningsrapport
          </button>
          <button
            onClick={() => setActiveTab("ner")}
            className={`flex items-center gap-2 pb-3 px-3 text-xs font-semibold border-b-2 transition ${
              activeTab === "ner"
                ? "border-sky-500 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="w-4 h-4" /> AI & NLP Textanalys (NER)
          </button>
          <button
            onClick={() => setActiveTab("resolution")}
            className={`flex items-center gap-2 pb-3 px-3 text-xs font-semibold border-b-2 transition ${
              activeTab === "resolution"
                ? "border-sky-500 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <GitMerge className="w-4 h-4" /> Entitetsupplösning & Deduplicering
          </button>
        </div>

        {/* FLIK 1: Utredningsrapport */}
        {activeTab === "report" && (
          <div className="space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-slate-100">Automatiserad Utredningsrapport</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Sammanställer automatiskt fallets hypotes, kartlagda noder, centralitetsmått, risker och beviskedja.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Exportläge (Full vs Sanitiserad) */}
                <div className="flex items-center bg-slate-900 border border-slate-700 rounded-lg p-0.5 text-xs">
                  <button
                    onClick={() => setReportMode("full")}
                    className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                      reportMode === "full"
                        ? "bg-sky-600 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Full Dossier
                  </button>
                  <button
                    onClick={() => setReportMode("sanitized")}
                    className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                      reportMode === "sanitized"
                        ? "bg-amber-600 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Sanitiserad (GDPR)
                  </button>
                </div>

                {/* Språkval */}
                <div className="flex items-center bg-slate-900 border border-slate-700 rounded-lg p-0.5 text-xs">
                  {(["sv", "en", "uk"] as const).map((l) => (
                    <button
                      key={l}
                      onClick={() => setReportLocale(l)}
                      className={`px-2 py-1 rounded text-[10px] font-bold uppercase transition ${
                        reportLocale === l
                          ? "bg-slate-700 text-white"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {l}
                    </button>
                  ))}
                </div>

                <button
                  onClick={downloadMarkdown}
                  className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition"
                >
                  <Download className="w-3.5 h-3.5" /> Ladda ner .md
                </button>
                <button
                  onClick={openPrintableReport}
                  className="flex items-center gap-1.5 text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium px-3 py-1.5 rounded-lg shadow transition"
                >
                  <Printer className="w-3.5 h-3.5" /> Skriv ut / PDF
                </button>
              </div>
            </div>

            {loadingReport ? (
              <div className="py-20 text-center text-xs text-slate-500">Genererar rapport...</div>
            ) : (
              <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-sm">
                <pre className="text-xs text-slate-200 font-mono whitespace-pre-wrap leading-relaxed">
                  {markdownReport || "Ingen rapport tillgänglig ännu."}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* FLIK 2: AI & NLP Textanalys */}
        {activeTab === "ner" && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sky-400" /> Named Entity Recognition (NER)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Klistra in ostrukturerad text från artiklar, domstolshandlingar eller e-post för att automatiskt
                extrahera personer, bolag, e-post, IP-adresser, domäner och Bitcoin/Ethereum-adresser.
              </p>
            </div>

            <form onSubmit={handleRunNer} className="space-y-3">
              <textarea
                rows={6}
                value={nerText}
                onChange={(e) => setNerText(e.target.value)}
                placeholder="Klistra in ostrukturerad utredningstext här..."
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl p-3.5 focus:border-sky-500 focus:outline-none"
                required
              />

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoCommit}
                    onChange={(e) => setAutoCommit(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0"
                  />
                  <span>Spara identifierade noder automatiskt till utredningen</span>
                </label>

                <button
                  type="submit"
                  disabled={nerRunning}
                  className="bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs px-4 py-2 rounded-lg transition shadow flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {nerRunning ? "Analyserar text..." : "Extrahera Entiteter"}
                </button>
              </div>
            </form>

            {nerStatus && (
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-300">
                {nerStatus}
              </div>
            )}

            {extractedEntities.length > 0 && (
              <div className="bg-[#111827] border border-slate-800 rounded-2xl p-5 mt-4">
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-3">
                  Identifierade Entiteter ({extractedEntities.length})
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                  {extractedEntities.map((e, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs"
                    >
                      <div className="text-[10px] uppercase font-bold text-sky-400">{e.type}</div>
                      <div className="font-semibold text-slate-200 mt-0.5 truncate">{e.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* FLIK 3: Entitetsupplösning & Deduplicering */}
        {activeTab === "resolution" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <GitMerge className="w-4 h-4 text-sky-400" /> Entitetsupplösning (Deduplicering)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Identifierar deterministiska (unika nycklar/org.nr) och probabilistiska (Jaro-Winkler namnlikhet)
                  dubbletter och slår samman noder och beviskedjor.
                </p>
              </div>
              <button
                onClick={loadResolutionMatches}
                disabled={loadingMatches}
                className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingMatches ? "animate-spin" : ""}`} />
                Sök Dubbletter
              </button>
            </div>

            {loadingMatches ? (
              <div className="py-20 text-center text-xs text-slate-500">Söker dubbletter...</div>
            ) : matches.length === 0 ? (
              <div className="bg-[#111827] border border-slate-800 rounded-2xl p-8 text-center text-xs text-slate-500">
                Inga sammanfallande eller probabilistiska dubbletter identifierades i utredningen.
              </div>
            ) : (
              <div className="space-y-3">
                {matches.map((m, idx) => (
                  <div
                    key={idx}
                    className="bg-[#111827] border border-slate-800 hover:border-slate-700 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded uppercase font-bold ${
                            m.match_type === "deterministic"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : "bg-amber-950 text-amber-400 border border-amber-800"
                          }`}
                        >
                          {m.match_type} ({Math.round(m.confidence * 100)}%)
                        </span>
                      </div>

                      <div className="flex items-center gap-2 mt-2 text-sm font-semibold text-slate-200">
                        <span>{m.primary_name}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-slate-400">{m.secondary_name}</span>
                      </div>

                      <div className="text-xs text-slate-400 mt-1 space-y-0.5">
                        {m.reasons.map((r, rIdx) => (
                          <div key={rIdx} className="text-[11px] text-slate-500">
                            • {r}
                          </div>
                        ))}
                      </div>
                    </div>

                    <button
                      onClick={() => handleMerge(m)}
                      disabled={merging}
                      className="bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs px-3.5 py-2 rounded-lg transition shrink-0 flex items-center gap-1.5 shadow"
                    >
                      <GitMerge className="w-3.5 h-3.5" />
                      Slå samman
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
