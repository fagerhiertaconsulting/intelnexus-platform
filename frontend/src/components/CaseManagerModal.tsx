"use client";

import React, { useState } from "react";
import { Case } from "@/types";
import { api } from "@/lib/api";
import { FolderPlus, Trash2, Check, X, ShieldAlert, Tag } from "lucide-react";

interface CaseManagerModalProps {
  cases: Case[];
  activeCaseId: string;
  onSelectCase: (caseId: string) => void;
  onClose: () => void;
  onCaseCreated: () => void;
}

export default function CaseManagerModal({
  cases,
  activeCaseId,
  onSelectCase,
  onClose,
  onCaseCreated,
}: CaseManagerModalProps) {
  const [isCreating, setIsCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [tagsStr, setTagsStr] = useState("");
  const [investigator, setInvestigator] = useState("Chief Analyst");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    try {
      const tags = tagsStr
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      const created = await api.createCase({
        title: title.trim(),
        description: description.trim(),
        priority,
        tags,
        investigator: investigator.trim() || "Analyst",
      });

      onCaseCreated();
      onSelectCase(created.id);
      setIsCreating(false);
    } catch (err: any) {
      alert(`Kunde inte skapa ärende: ${err.message}`);
    }
  };

  const handleDelete = async (e: React.MouseEvent, caseId: string) => {
    e.stopPropagation();
    if (confirm("Är du säker på att du vill radera detta utredningsärende och all dess data?")) {
      await api.deleteCase(caseId);
      onCaseCreated();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#111827] border border-slate-700 w-full max-w-xl rounded-2xl p-6 shadow-2xl max-h-[85vh] flex flex-col">
        <div className="flex justify-between items-center pb-4 border-b border-slate-800">
          <h3 className="font-bold text-slate-100 text-base">Hantering av Utredningsärenden</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto my-4 space-y-3">
          {!isCreating ? (
            <>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                  Befintliga ärenden ({cases.length})
                </span>
                <button
                  onClick={() => setIsCreating(true)}
                  className="flex items-center gap-1.5 text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium px-3 py-1.5 rounded-lg shadow transition"
                >
                  <FolderPlus className="w-3.5 h-3.5" /> Nytt Ärende
                </button>
              </div>

              {cases.map((c) => (
                <div
                  key={c.id}
                  onClick={() => {
                    onSelectCase(c.id);
                    onClose();
                  }}
                  className={`p-3.5 rounded-xl border cursor-pointer transition flex items-start justify-between ${
                    c.id === activeCaseId
                      ? "bg-sky-950/40 border-sky-500/60"
                      : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-200">{c.title}</span>
                      {c.id === activeCaseId && (
                        <span className="text-[10px] bg-sky-900 text-sky-300 font-bold px-2 py-0.5 rounded">
                          Aktiv
                        </span>
                      )}
                    </div>
                    {c.description && (
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{c.description}</p>
                    )}
                    <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-2">
                      <span>Prioritet: {c.priority}</span>
                      <span>Utredare: {c.investigator}</span>
                      <span>{new Date(c.updated_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <button
                    onClick={(e) => handleDelete(e, c.id)}
                    className="text-slate-500 hover:text-rose-400 p-1"
                    title="Radera ärende"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </>
          ) : (
            <form onSubmit={handleCreate} className="space-y-4">
              <h4 className="text-sm font-bold text-slate-200">Skapa Nytt Utredningsärende</h4>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Ärendetitel</label>
                <input
                  type="text"
                  placeholder="t.ex. Operation BlueStar: Hotaktörsanalys"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:border-sky-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Utredningsbeskrivning och Hypotes
                </label>
                <textarea
                  rows={3}
                  placeholder="Beskrivning av utredningens mål, kända aktörer eller attackvektorer..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:border-sky-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Prioritet</label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as any)}
                    className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                  >
                    <option value="low">Låg</option>
                    <option value="medium">Medium</option>
                    <option value="high">Hög</option>
                    <option value="critical">Kritisk</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Ansvarig Utredare</label>
                  <input
                    type="text"
                    value={investigator}
                    onChange={(e) => setInvestigator(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Taggar (kommaseparerade)</label>
                <input
                  type="text"
                  placeholder="cyber, fraud, ransomware, sweden"
                  value={tagsStr}
                  onChange={(e) => setTagsStr(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white"
                >
                  Tillbaka
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg text-xs bg-sky-600 hover:bg-sky-500 text-white font-medium shadow"
                >
                  Spara & Öppna
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="pt-3 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200"
          >
            Stäng
          </button>
        </div>
      </div>
    </div>
  );
}
