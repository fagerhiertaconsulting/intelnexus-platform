"use client";

import React, { useEffect, useState } from "react";
import { Entity, Relationship } from "@/types";
import { api } from "@/lib/api";
import { Clock, Calendar, ArrowRight, Search, Filter } from "lucide-react";

interface TimelineViewProps {
  caseId: string;
}

interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  category: "entity" | "relationship";
  type: string;
  detail: string;
  confidence: number;
}

export default function TimelineView({ caseId }: TimelineViewProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [entities, relationships] = await Promise.all([
          api.listEntities(caseId),
          api.listRelationships(caseId),
        ]);

        const entMap = new Map(entities.map((e) => [e.id, e.name]));
        const evList: TimelineEvent[] = [];

        entities.forEach((e) => {
          evList.push({
            id: e.id,
            timestamp: e.created_at,
            title: `Entitet identifierad: ${e.name}`,
            category: "entity",
            type: e.type,
            detail: e.aliases?.length ? `Kända alias: ${e.aliases.join(", ")}` : "Ny nod i utredningen",
            confidence: e.confidence_score,
          });
        });

        relationships.forEach((r) => {
          const srcName = entMap.get(r.source_id) || r.source_id;
          const tgtName = entMap.get(r.target_id) || r.target_id;
          evList.push({
            id: r.id,
            timestamp: r.created_at,
            title: `Koppling: ${srcName} → ${tgtName}`,
            category: "relationship",
            type: r.relation_type,
            detail: `Relationstyp: ${r.relation_type}`,
            confidence: r.confidence_score,
          });
        });

        evList.sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        setEvents(evList);
      } catch (err) {
        console.error("Kunde inte hämta tidslinjedata:", err);
      } finally {
        setLoading(false);
      }
    }

    if (caseId) {
      loadData();
    }
  }, [caseId]);

  const filtered = events.filter((e) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      e.title.toLowerCase().includes(q) ||
      e.detail.toLowerCase().includes(q) ||
      e.type.toLowerCase().includes(q)
    );
  });

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] p-6 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Clock className="w-5 h-5 text-sky-400" /> Utredningens Tidslinje
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Kronologisk sekvens av identifierade noder, certifikat, transaktioner och relationer.
            </p>
          </div>

          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Sök händelser..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-slate-900 text-xs text-slate-200 pl-9 pr-3 py-2 rounded-lg border border-slate-700 w-64 focus:outline-none focus:border-sky-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-slate-400 text-sm">Laddar tidslinje...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-slate-500 text-sm">
            Inga händelser matchade sökningen.
          </div>
        ) : (
          <div className="relative mt-8 pl-6 border-l-2 border-slate-800 space-y-6">
            {filtered.map((item) => (
              <div key={item.id} className="relative group">
                {/* Punkt på linjen */}
                <div className="absolute -left-[31px] top-1.5 w-3.5 h-3.5 rounded-full bg-slate-900 border-2 border-sky-500 group-hover:scale-125 transition" />

                <div className="bg-[#111827] border border-slate-800 hover:border-slate-700 p-4 rounded-xl transition shadow-sm">
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                    <span className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
                      <Calendar className="w-3.5 h-3.5 text-slate-500" />
                      {new Date(item.timestamp).toLocaleString()}
                    </span>
                    <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-[10px] font-semibold uppercase">
                      {item.type}
                    </span>
                  </div>

                  <h4 className="text-sm font-semibold text-slate-200 mt-1">{item.title}</h4>
                  <p className="text-xs text-slate-400 mt-1">{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
