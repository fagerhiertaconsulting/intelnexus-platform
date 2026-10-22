"use client";

import React, { useEffect, useState } from "react";
import { Entity } from "@/types";
import { api } from "@/lib/api";
import {
  Globe,
  Flame,
  Plane,
  Building2,
  ShieldAlert,
  AlertTriangle,
  Radio,
  MapPin,
} from "lucide-react";
import MapView from "./MapView";

interface GeointViewProps {
  caseId: string;
}

export default function GeointView({ caseId }: GeointViewProps) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const data = await api.listEntities(caseId);
        setEntities(data);
      } catch (err) {
        console.error("Kunde inte hämta geointdata:", err);
      } finally {
        setLoading(false);
      }
    }

    if (caseId) {
      loadData();
    }
  }, [caseId]);

  const transponderNodes = entities.filter((e) => e.name.startsWith("Flygtransponder"));
  const perimeterAlerts = entities.filter((e) => e.name.startsWith("Perimeterlarm"));

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] flex flex-col overflow-hidden">
      {/* Varningar & Statusfält överst */}
      <div className="bg-[#0f172a] border-b border-slate-800 px-5 py-3 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-cyan-950 border border-cyan-800 text-cyan-400">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-100 flex items-center gap-2">
              GEOINT & Kriszonsövervakning
              {perimeterAlerts.length > 0 && (
                <span className="bg-rose-950 border border-rose-700 text-rose-300 text-[10px] font-bold px-2 py-0.5 rounded-full animate-pulse flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3 text-rose-400" />
                  Perimeterlarm Aktivt
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-400">
              NASA FIRMS Satellitlager • OpenSky ADS-B Transpondrar • Ambassad Geofencing
            </div>
          </div>
        </div>

        {/* Live-mätare */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-amber-400">
            <Flame className="w-4 h-4" />
            <span>FIRMS Satellitbränder: <strong>Aktiv</strong></span>
          </div>
          <div className="flex items-center gap-1.5 text-sky-400">
            <Plane className="w-4 h-4" />
            <span>Flygtranspondrar: <strong>{transponderNodes.length} st</strong></span>
          </div>
        </div>
      </div>

      {/* Delad vy: Karta + Larmpanel */}
      <div className="flex-1 flex relative overflow-hidden">
        {/* Karta */}
        <div className="flex-1 h-full relative">
          <MapView caseId={caseId} />
        </div>

        {/* Höger sidopanel: Transpondrar & Perimeter */}
        <div className="w-80 h-full bg-[#0c121e] border-l border-slate-800 p-4 overflow-y-auto space-y-4 z-10 shadow-xl">
          <div>
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 mb-2">
              <Building2 className="w-3.5 h-3.5 text-purple-400" /> Diplomatiska Anläggningar
            </h4>
            <div className="space-y-1.5 text-xs text-slate-300">
              {perimeterAlerts.length > 0 ? (
                perimeterAlerts.map((pa) => (
                  <div key={pa.id} className="p-2.5 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-200">
                    <div className="font-bold flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                      {pa.name}
                    </div>
                    <div className="text-[11px] text-rose-300/80 mt-1">
                      Avstånd: {pa.attributes?.distance_km} km från anläggningen.
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-slate-500 italic p-3 bg-slate-900/40 rounded-lg">
                  Inga aktiva larm inom beskickningarnas säkerhetszoner.
                </div>
              )}
            </div>
          </div>

          <div>
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 mb-2">
              <Radio className="w-3.5 h-3.5 text-sky-400" /> Luftrum & Transponderradar
            </h4>
            <div className="space-y-2 text-xs">
              {transponderNodes.length > 0 ? (
                transponderNodes.map((tn) => (
                  <div key={tn.id} className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
                    <div className="font-bold text-slate-200">{tn.name}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Höjd: {tn.attributes?.altitude_m} m | ICAO: {tn.attributes?.icao24}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-slate-500 italic p-3 bg-slate-900/40 rounded-lg">
                  Kör GEOINT & Transponder-transform mot en plats för att läsa av luftrummet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
