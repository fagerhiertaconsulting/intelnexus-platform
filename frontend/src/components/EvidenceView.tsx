"use client";

import React, { useEffect, useState } from "react";
import { EvidenceItem, CustodyAudit } from "@/types";
import { api } from "@/lib/api";
import {
  ShieldCheck,
  ShieldAlert,
  Camera,
  FileText,
  Copy,
  Check,
  ExternalLink,
  RefreshCw,
  Search,
  Lock,
  Download,
} from "lucide-react";

interface EvidenceViewProps {
  caseId: string;
}

export default function EvidenceView({ caseId }: EvidenceViewProps) {
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [auditResult, setAuditResult] = useState<CustodyAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [search, setSearch] = useState("");

  // Snapshot form
  const [snapshotUrl, setSnapshotUrl] = useState("");
  const [snapshotTitle, setSnapshotTitle] = useState("");
  const [snapping, setSnapping] = useState(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Inspector modal
  const [viewingEvidence, setViewingEvidence] = useState<EvidenceItem | null>(null);
  const [rawContent, setRawContent] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const items = await api.listEvidence(caseId);
      setEvidenceList(items);
      const audit = await api.auditCustody(caseId);
      setAuditResult(audit);
    } catch (err) {
      console.error("Fel vid hämtning av bevis:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      loadData();
    }
  }, [caseId]);

  const handleAudit = async () => {
    try {
      setAuditing(true);
      const audit = await api.auditCustody(caseId);
      setAuditResult(audit);
    } catch (err: any) {
      alert(`Revisionsfel: ${err.message}`);
    } finally {
      setAuditing(false);
    }
  };

  const handleCaptureSnapshot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!snapshotUrl.trim()) return;

    try {
      setSnapping(true);
      await api.createWebSnapshot(
        snapshotUrl.trim(),
        caseId,
        snapshotTitle.trim() || undefined
      );
      setSnapshotUrl("");
      setSnapshotTitle("");
      await loadData();
    } catch (err: any) {
      alert(`Kunde inte arkivera webbsida: ${err.message}`);
    } finally {
      setSnapping(false);
    }
  };

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleViewContent = async (item: EvidenceItem) => {
    setViewingEvidence(item);
    try {
      const res = await fetch(`http://localhost:8000/api/evidence/${item.id}/content`);
      if (res.ok) {
        const text = await res.text();
        setRawContent(text);
      } else {
        setRawContent("Kunde inte läsa filinnehåll.");
      }
    } catch {
      setRawContent("Kunde inte ansluta till bevisarkivet.");
    }
  };

  const filtered = evidenceList.filter((ev) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      ev.title.toLowerCase().includes(q) ||
      ev.collector_plugin?.toLowerCase().includes(q) ||
      ev.sha256.toLowerCase().includes(q) ||
      ev.source_url?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header med status för beviskedjan */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Lock className="w-5 h-5 text-sky-400" /> Beviskedja & Chain of Custody
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Kryptografiskt oföränderlig lagring av samtliga inhämtade data, webbarkiv och API-svar med SHA-256.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {auditResult && (
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold ${
                  auditResult.chain_of_custody_intact
                    ? "bg-emerald-950/40 border-emerald-700/60 text-emerald-400"
                    : "bg-rose-950/40 border-rose-700/60 text-rose-400"
                }`}
              >
                {auditResult.chain_of_custody_intact ? (
                  <>
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Beviskedja Obruten ({auditResult.valid_count}/{auditResult.total_items})</span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    <span>Integritetsavvikelse upptäckt!</span>
                  </>
                )}
              </div>
            )}

            <button
              onClick={handleAudit}
              disabled={auditing}
              className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${auditing ? "animate-spin" : ""}`} />
              Kör Integritetsrevision
            </button>
          </div>
        </div>

        {/* Formulär för webbsnapshot */}
        <div className="bg-[#111827] border border-slate-800 p-5 rounded-2xl shadow-sm">
          <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 mb-3">
            <Camera className="w-4 h-4 text-sky-400" /> Arkivera Webbsida (Snapshot Engine)
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Hämtar och låser rå HTML, HTTP-headers och tidsstämpel med automatisk SHA-256 hashning.
          </p>

          <form onSubmit={handleCaptureSnapshot} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <input
                type="text"
                placeholder="https://example.com/target-page"
                value={snapshotUrl}
                onChange={(e) => setSnapshotUrl(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:border-sky-500"
                required
              />
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Valfri titel..."
                value={snapshotTitle}
                onChange={(e) => setSnapshotTitle(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:border-sky-500"
              />
              <button
                type="submit"
                disabled={snapping}
                className="bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs px-4 py-2.5 rounded-lg transition flex items-center gap-1.5 shrink-0 shadow"
              >
                <Camera className="w-3.5 h-3.5" />
                {snapping ? "Arkiverar..." : "Spara"}
              </button>
            </div>
          </form>
        </div>

        {/* Tabell över bevisposter */}
        <div className="bg-[#111827] border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <h3 className="text-sm font-bold text-slate-200">
              Registrerade bevis ({filtered.length})
            </h3>
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Sök bevis eller hash..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-slate-900 text-xs text-slate-200 pl-8 pr-3 py-1.5 rounded-lg border border-slate-700 focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">Laddar bevis...</div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Inga bevis registrerade ännu. Kör en transform eller arkivera en webbsida ovan.
            </div>
          ) : (
            <div className="overflow-x-auto text-xs">
              <table className="w-full text-left">
                <thead className="bg-slate-900/60 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="p-3">Titel</th>
                    <th className="p-3">Insamlare</th>
                    <th className="p-3">SHA-256 Kontrollsumma</th>
                    <th className="p-3">Storlek</th>
                    <th className="p-3">Arkiverad</th>
                    <th className="p-3 text-right">Åtgärd</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  {filtered.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-800/40 transition">
                      <td className="p-3 font-medium text-slate-200 max-w-xs truncate">
                        {item.title}
                        {item.source_url && (
                          <div className="text-[10px] text-slate-500 truncate mt-0.5">
                            {item.source_url}
                          </div>
                        )}
                      </td>
                      <td className="p-3">
                        <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                          {item.collector_plugin || "manual"}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-[11px] text-slate-400">
                        <div className="flex items-center gap-1.5">
                          <span>
                            {item.sha256.slice(0, 10)}...{item.sha256.slice(-8)}
                          </span>
                          <button
                            onClick={() => handleCopyHash(item.sha256)}
                            title="Kopiera full hash"
                            className="text-slate-500 hover:text-slate-300"
                          >
                            {copiedHash === item.sha256 ? (
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="p-3 text-slate-400">{(item.file_size_bytes / 1024).toFixed(1)} KB</td>
                      <td className="p-3 text-slate-400 whitespace-nowrap">
                        {new Date(item.recorded_at).toLocaleString()}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => handleViewContent(item)}
                          className="text-sky-400 hover:text-sky-300 font-medium px-2 py-1 rounded bg-sky-950/40 hover:bg-sky-900/50 transition"
                        >
                          Granska
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Granska bevisfil */}
      {viewingEvidence && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#111827] border border-slate-700 w-full max-w-4xl rounded-2xl p-6 shadow-2xl flex flex-col max-h-[85vh]">
            <div className="flex justify-between items-start pb-4 border-b border-slate-800">
              <div>
                <h3 className="font-bold text-slate-100 text-base">{viewingEvidence.title}</h3>
                <div className="text-[11px] text-slate-400 font-mono mt-1">
                  SHA-256: {viewingEvidence.sha256}
                </div>
              </div>
              <button
                onClick={() => setViewingEvidence(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-auto mt-4 bg-slate-950 p-4 rounded-xl border border-slate-800">
              <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap">
                {rawContent || "Laddar innehåll..."}
              </pre>
            </div>

            <div className="pt-4 mt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setViewingEvidence(null)}
                className="px-4 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200"
              >
                Stäng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
