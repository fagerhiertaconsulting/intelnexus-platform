"use client";

import React, { useState } from "react";
import { WorkspaceRole } from "@/types";
import {
  HeartHandshake,
  ShieldCheck,
  Newspaper,
  UserCheck,
  Landmark,
  Globe,
  Building2,
  ChevronDown,
  Check,
  Sparkles,
} from "lucide-react";

interface RoleSelectorProps {
  roles: WorkspaceRole[];
  activeRoleId: string;
  onSelectRole: (roleId: string) => void;
}

const ROLE_ICONS: Record<string, React.ReactNode> = {
  dating_safety: <HeartHandshake className="w-4 h-4 text-pink-400" />,
  law_enforcement: <ShieldCheck className="w-4 h-4 text-sky-400" />,
  journalism: <Newspaper className="w-4 h-4 text-emerald-400" />,
  private_investigator: <UserCheck className="w-4 h-4 text-amber-400" />,
  finance_aml: <Landmark className="w-4 h-4 text-yellow-400" />,
  geopolitical: <Globe className="w-4 h-4 text-cyan-400" />,
  embassy: <Building2 className="w-4 h-4 text-purple-400" />,
};

export default function RoleSelector({
  roles,
  activeRoleId,
  onSelectRole,
}: RoleSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const activeRole = roles.find((r) => r.role_id === activeRoleId) || roles[0];

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 transition group shadow-sm"
      >
        <span className="shrink-0">{ROLE_ICONS[activeRole?.role_id] || <Sparkles className="w-4 h-4 text-sky-400" />}</span>
        <div className="text-left">
          <div className="text-xs font-bold text-slate-200 group-hover:text-white flex items-center gap-1.5">
            {activeRole?.display_name || "Välj roll..."}
          </div>
          <div className="text-[10px] text-slate-400 truncate max-w-[130px]">
            {activeRole?.target_audience || "Persona"}
          </div>
        </div>
        <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0 ml-1" />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute left-0 mt-2 w-80 bg-[#111827] border border-slate-700 rounded-2xl shadow-2xl p-2 z-50 divide-y divide-slate-800/80">
            <div className="p-2">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Välj Utredningsprofil (Persona)
              </span>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Anpassar gränssnitt, moduler, sökguider och förvalda verktyg.
              </p>
            </div>

            <div className="pt-1 space-y-1 max-h-[70vh] overflow-y-auto">
              {roles.map((r) => {
                const isSelected = r.role_id === activeRoleId;
                return (
                  <button
                    key={r.role_id}
                    onClick={() => {
                      onSelectRole(r.role_id);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left p-2.5 rounded-xl transition flex items-start gap-2.5 ${
                      isSelected
                        ? "bg-sky-950/50 border border-sky-500/60"
                        : "hover:bg-slate-800/70 border border-transparent"
                    }`}
                  >
                    <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 shrink-0 mt-0.5">
                      {ROLE_ICONS[r.role_id] || <Sparkles className="w-4 h-4 text-sky-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200 truncate">
                          {r.display_name}
                        </span>
                        {isSelected && <Check className="w-3.5 h-3.5 text-sky-400 shrink-0" />}
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">
                        {r.description}
                      </p>
                      <div className="text-[10px] text-sky-400 font-medium mt-1">
                        Målgrupp: {r.target_audience}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
