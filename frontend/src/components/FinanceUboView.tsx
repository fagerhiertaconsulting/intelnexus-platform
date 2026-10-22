"use client";

import React, { useEffect, useState } from "react";
import { Entity, Relationship } from "@/types";
import { api } from "@/lib/api";
import {
  Landmark,
  ShieldAlert,
  GitBranch,
  Coins,
  Building2,
  CheckCircle2,
  AlertOctagon,
  Search,
  ExternalLink,
} from "lucide-react";

interface FinanceUboViewProps {
  caseId: string;
}

export default function FinanceUboView({ caseId }: FinanceUboViewProps) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [ents, rels] = await Promise.all([
          api.listEntities(caseId),
          api.listRelationships(caseId),
        ]);
        setEntities(ents);
        setRelationships(rels);
      } catch (err) {
        console.error("Kunde inte hämta finansdata:", err);
      } finally {
        setLoading(false);
      }
    }

    if (caseId) {
      loadData();
    }
  }, [caseId]);

  const uboEntities = entities.filter((e) => e.attributes?.is_ubo === true);
  const offshoreEntities = entities.filter((e) => e.attributes?.is_offshore === true);
  const sanctionedEntities = entities.filter((e) => e.attributes?.sanctioned === true);
  const cryptoWallets = entities.filter((e) => e.type === "crypto_wallet");

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] p-6 overflow-y-auto">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Landmark className="w-5 h-5 text-yellow-400" /> Finansbrott, AML & UBO-analys
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Anti-Money Laundering (AML), upplösning av verklig huvudman (UBO), ägarkedjor och blockkedjespårning.
            </p>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-yellow-950/80 border border-yellow-700 text-yellow-400 px-3 py-1 rounded-full">
            AML & UBO Profil
          </span>
        </div>

        {/* 1. Översiktssiffror */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Verkliga Huvudmän (UBO)</span>
            <div className="text-2xl font-bold text-slate-100 mt-1">{uboEntities.length} st</div>
          </div>
          <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Offshore-enheter</span>
            <div className="text-2xl font-bold text-amber-400 mt-1">{offshoreEntities.length} st</div>
          </div>
          <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Sanktionsträffar</span>
            <div className="text-2xl font-bold text-rose-400 mt-1">{sanctionedEntities.length} st</div>
          </div>
          <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
            <span className="text-xs text-slate-400">Kryptoplånböcker</span>
            <div className="text-2xl font-bold text-sky-400 mt-1">{cryptoWallets.length} st</div>
          </div>
        </div>

        {/* 2. UBO Unwrapper: Ägarkedjor & Verklig Huvudman */}
        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl">
          <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 mb-3">
            <GitBranch className="w-4 h-4 text-sky-400" /> UBO Unwrapper: Kartlagda Ägarträd
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Rekursiv upplösning av holdingbolag och beräkning av indirekta ägarandelar för att identifiera
            fysiska personer med minst 25% bestämmande inflytande.
          </p>

          {entities.filter((e) => e.attributes?.effective_share_pct).length > 0 ? (
            <div className="space-y-2 text-xs">
              {entities
                .filter((e) => e.attributes?.effective_share_pct)
                .map((e) => (
                  <div
                    key={e.id}
                    className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl flex items-center justify-between"
                  >
                    <div>
                      <div className="font-bold text-slate-200 flex items-center gap-2">
                        <span>{e.name}</span>
                        {e.attributes?.is_ubo && (
                          <span className="text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded font-bold uppercase">
                            Verifierad UBO
                          </span>
                        )}
                        {e.attributes?.is_offshore && (
                          <span className="text-[10px] bg-amber-950 text-amber-400 border border-amber-800 px-2 py-0.5 rounded font-bold uppercase">
                            Offshore ({e.attributes?.jurisdiction})
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        Jurisdiktion: {e.attributes?.jurisdiction} | Kedjedjup: Nivå {e.attributes?.chain_depth || 1}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-base font-extrabold text-sky-400">
                        {e.attributes?.effective_share_pct}%
                      </span>
                      <div className="text-[10px] text-slate-500">effektivt ägande</div>
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-500">
              Inga UBO-ägarkedjor upplösta ännu. Välj ett bolag i grafen och kör &quot;UBO Unwrapper &amp; Beneficial Ownership&quot;.
            </div>
          )}
        </div>

        {/* 3. Krypto- & Blockkedjespårning */}
        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl">
          <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 mb-3">
            <Coins className="w-4 h-4 text-amber-400" /> Krypto- & Blockchain-transaktioner
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Spårar transaktioner, adresser och kluster på Bitcoin-, Ethereum- och Tron-blockkedjor.
          </p>

          {cryptoWallets.length > 0 ? (
            <div className="space-y-2">
              {cryptoWallets.map((cw) => (
                <div key={cw.id} className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl text-xs flex justify-between items-center">
                  <div>
                    <div className="font-mono text-slate-200 font-semibold">{cw.name}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">Nätverk: {cw.attributes?.blockchain || "Kryptovaluta"}</div>
                  </div>
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-1 rounded">Spårning aktiv</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-slate-500">Inga kryptoplånböcker registrerade i ärendet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
