"use client";

import React, { useEffect, useState } from "react";
import { Case, WorkspaceRole } from "@/types";
import { api } from "@/lib/api";
import GraphCanvas from "@/components/GraphCanvas";
import TimelineView from "@/components/TimelineView";
import MapView from "@/components/MapView";
import EvidenceView from "@/components/EvidenceView";
import AnalysisReportView from "@/components/AnalysisReportView";
import CaseManagerModal from "@/components/CaseManagerModal";
import RoleSelector from "@/components/RoleSelector";
import DatingSafetyWizard from "@/components/DatingSafetyWizard";
import JournalismVault from "@/components/JournalismVault";
import FinanceUboView from "@/components/FinanceUboView";
import GeointView from "@/components/GeointView";
import CredentialVaultModal from "@/components/CredentialVaultModal";
import { TwoFactorSettingsModal } from "@/components/TwoFactorSettingsModal";
import { StepUpModal } from "@/components/StepUpModal";
import { TwoFactorStatus } from "@/types";
import "@/lib/i18n";
import { useTranslation } from "react-i18next";
import {
  Network,
  Clock,
  MapPin,
  Lock,
  FileText,
  FolderOpen,
  ChevronDown,
  ShieldAlert,
  ShieldCheck,
  Download,
  Key,
  Sparkles,
  LayoutDashboard,
  Globe,
} from "lucide-react";

type ActiveTab = "role_dashboard" | "graph" | "timeline" | "map" | "evidence" | "analysis";

export default function Home() {
  const { t, i18n } = useTranslation(["common", "roles", "auth"]);
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string>("");
  const [roles, setRoles] = useState<WorkspaceRole[]>([]);
  const [activeRoleId, setActiveRoleId] = useState<string>("dating_safety");
  const [activeTab, setActiveTab] = useState<ActiveTab>("role_dashboard");
  const [stats, setStats] = useState<any>(null);
  const [showCaseModal, setShowCaseModal] = useState(false);
  const [showVaultModal, setShowVaultModal] = useState(false);
  const [show2FAModal, setShow2FAModal] = useState(false);
  const [showStepUpModal, setShowStepUpModal] = useState(false);
  const [twoFactorStatus, setTwoFactorStatus] = useState<TwoFactorStatus | null>(null);
  const [loading, setLoading] = useState(true);


  const loadData = async () => {
    try {
      setLoading(true);
      const [caseList, roleList] = await Promise.all([
        api.listCases(),
        api.listRoles(),
      ]);

      setCases(caseList);
      setRoles(roleList);

      if (caseList.length > 0 && !activeCaseId) {
        setActiveCaseId(caseList[0].id);
      }
    } catch (err) {
      console.error("Kunde inte hämta initialdata:", err);
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

  const load2FAStatus = async () => {
    try {
      const st = await api.get2FAStatus();
      setTwoFactorStatus(st);
    } catch (err) {
      console.error("Kunde inte hämta 2FA-status:", err);
    }
  };

  useEffect(() => {
    loadData();
    load2FAStatus();

    const handleStepUpRequired = () => {
      setShowStepUpModal(true);
    };

    window.addEventListener("openintel:require-step-up", handleStepUpRequired);
    return () => {
      window.removeEventListener("openintel:require-step-up", handleStepUpRequired);
    };
  }, []);


  useEffect(() => {
    if (activeCaseId) {
      loadStats(activeCaseId);
    }
  }, [activeCaseId]);

  const activeCase = cases.find((c) => c.id === activeCaseId);
  const egressPolicy = activeCase?.egress_policy || "DIRECT";
  const activeRole = roles.find((r) => r.role_id === activeRoleId) || roles[0];

  const handleRoleChange = (newRoleId: string) => {
    setActiveRoleId(newRoleId);
    // Växla till rollens dashboard
    setActiveTab("role_dashboard");
  };

  const handleExportGexf = () => {
    if (!activeCaseId) return;
    window.open(`http://localhost:8000/api/graph/${activeCaseId}/export/gexf`, "_blank");
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#090d16]">
      {/* Översta Navigationsbaren */}
      <header className="h-[68px] bg-[#0c121e] border-b border-slate-800/80 px-5 flex items-center justify-between shrink-0 z-30 shadow-md">
        {/* Vänster: Logotyp, Rollväljare & Ärendeväljare */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-600 flex items-center justify-center shadow-lg shadow-sky-600/30">
              <Network className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-bold text-sm tracking-wide text-slate-100 flex items-center gap-1.5">
                IntelNexus<span className="text-sky-400">Platform</span>
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                  v3.0
                </span>
              </div>
              <div className="text-[10px] text-slate-400">Integrations- & Fusionshubb</div>
            </div>
          </div>

          <div className="h-6 w-[1px] bg-slate-800 mx-1" />

          {/* Rollväljare (Personas) */}
          {roles.length > 0 && (
            <RoleSelector
              roles={roles}
              activeRoleId={activeRoleId}
              onSelectRole={handleRoleChange}
            />
          )}

          {/* Ärendeväljare */}
          <button
            onClick={() => setShowCaseModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/80 hover:bg-slate-850 border border-slate-700/80 hover:border-slate-600 transition group max-w-[200px]"
          >
            <FolderOpen className="w-4 h-4 text-sky-400 shrink-0" />
            <div className="text-left truncate">
              <div className="text-xs font-semibold text-slate-200 truncate group-hover:text-white">
                {activeCase?.title || t("common:nav.select_case")}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                {activeCase?.priority ? `Prio: ${activeCase.priority.toUpperCase()}` : ""}
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-500 shrink-0 ml-1" />
          </button>

          {/* OpSec Egress Statusindikator */}
          <div
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold shadow-sm transition"
            title={
              egressPolicy === "TOR_STRICT"
                ? t("common:opsec.tor_desc")
                : egressPolicy === "PROXY_RESIDENTIAL"
                ? t("common:opsec.residential_desc")
                : t("common:opsec.direct_desc")
            }
            style={{
              backgroundColor:
                egressPolicy === "TOR_STRICT"
                  ? "rgba(88, 28, 135, 0.35)"
                  : egressPolicy === "PROXY_RESIDENTIAL"
                  ? "rgba(30, 58, 138, 0.35)"
                  : "rgba(15, 23, 42, 0.65)",
              borderColor:
                egressPolicy === "TOR_STRICT"
                  ? "rgba(168, 85, 247, 0.6)"
                  : egressPolicy === "PROXY_RESIDENTIAL"
                  ? "rgba(59, 130, 246, 0.6)"
                  : "rgba(71, 85, 105, 0.6)",
              color:
                egressPolicy === "TOR_STRICT"
                  ? "#d8b4fe"
                  : egressPolicy === "PROXY_RESIDENTIAL"
                  ? "#93c5fd"
                  : "#94a3b8",
            }}
          >
            <span
              className="w-2 h-2 rounded-full animate-pulse"
              style={{
                backgroundColor:
                  egressPolicy === "TOR_STRICT"
                    ? "#c084fc"
                    : egressPolicy === "PROXY_RESIDENTIAL"
                    ? "#38bdf8"
                    : "#34d399",
              }}
            />
            <span className="text-[10px] font-mono tracking-wider">
              OPSEC: {egressPolicy}
            </span>
          </div>
        </div>

        {/* Mitten: Modul- & Vyväljare */}
        <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab("role_dashboard")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "role_dashboard"
                ? "bg-sky-600 text-white shadow-sm font-bold"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5 text-sky-300" />
            {activeRole?.display_name?.split(":")[0] || t("common:nav.role_dashboard")}
          </button>

          <button
            onClick={() => setActiveTab("graph")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeTab === "graph"
                ? "bg-sky-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            {t("common:nav.graph")}
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
            {t("common:nav.timeline")}
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
            {t("common:nav.map")}
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
            {t("common:nav.evidence")}
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
            {t("common:nav.analysis")}
          </button>
        </div>

        {/* Höger: Valv (BYOAK), 2FA Säkerhet, Språkväljare, Statistik & Export */}
        <div className="flex items-center gap-2.5">
          {/* Språkväljare: EN, SV, UK */}
          <div className="flex items-center bg-slate-900/90 border border-slate-700/80 rounded-xl p-0.5 text-xs font-semibold shadow-sm">
            <Globe className="w-3.5 h-3.5 text-slate-400 ml-1.5 mr-1" />
            {(["en", "sv", "uk"] as const).map((lang) => (
              <button
                key={lang}
                onClick={() => i18n.changeLanguage(lang)}
                className={`px-2 py-1 rounded-lg transition uppercase text-[10px] font-bold ${
                  i18n.language === lang
                    ? "bg-sky-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {lang}
              </button>
            ))}
          </div>

          {/* Frivillig 2FA Säkerhetsknapp */}
          <button
            onClick={() => setShow2FAModal(true)}
            className="flex items-center gap-1.5 text-xs bg-slate-900/80 hover:bg-slate-800 text-slate-200 font-semibold px-3 py-1.5 rounded-xl border border-slate-700/80 hover:border-sky-500/50 transition shadow-sm"
            title="Konfigurera frivillig tvåfaktorsautentisering (FIDO2/WebAuthn & TOTP)"
          >
            <ShieldCheck className={`w-3.5 h-3.5 ${twoFactorStatus?.is_2fa_enabled ? "text-emerald-400" : "text-slate-400"}`} />
            <span>{t("common:nav.two_factor")}</span>
            {twoFactorStatus?.is_2fa_enabled && (
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            )}
          </button>

          {/* BYOAK Valv-knapp */}
          <button
            onClick={() => setShowVaultModal(true)}
            className="flex items-center gap-1.5 text-xs bg-amber-950/40 hover:bg-amber-900/50 text-amber-300 font-semibold px-3 py-1.5 rounded-xl border border-amber-700/60 transition shadow-sm"
          >
            <Key className="w-3.5 h-3.5 text-amber-400" />
            {t("common:nav.credentials")}
          </button>


          {stats && (
            <div className="hidden xl:flex items-center gap-2 text-xs">
              <span className="bg-slate-900 border border-slate-800 px-2 py-1 rounded-lg text-slate-300">
                <strong className="text-sky-400">{stats.entity_count}</strong> noder
              </span>
              <span className="bg-slate-900 border border-slate-800 px-2 py-1 rounded-lg text-slate-300">
                <strong className="text-amber-400">{stats.relationship_count}</strong> länkar
              </span>
              {stats.sanctions_hits > 0 && (
                <span className="bg-rose-950/80 border border-rose-800 px-2 py-1 rounded-lg text-rose-300 font-semibold flex items-center gap-1">
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
            GEXF
          </button>
        </div>
      </header>

      {/* Huvudinnehåll */}
      <main className="flex-1 w-full h-[calc(100vh-68px)] relative">
        {loading ? (
          <div className="flex items-center justify-center h-full text-slate-400 text-sm">
            Initierar IntelNexus utredningsmiljö...
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
            {/* Adaptiv Rolldashboard baserat på Persona */}
            {activeTab === "role_dashboard" && (
              <>
                {activeRoleId === "dating_safety" && (
                  <DatingSafetyWizard
                    caseId={activeCaseId}
                    onVerificationDone={() => loadStats(activeCaseId)}
                  />
                )}
                {activeRoleId === "journalism" && (
                  <JournalismVault caseId={activeCaseId} />
                )}
                {activeRoleId === "finance_aml" && (
                  <FinanceUboView caseId={activeCaseId} />
                )}
                {(activeRoleId === "geopolitical" || activeRoleId === "embassy") && (
                  <GeointView caseId={activeCaseId} />
                )}
                {(activeRoleId === "law_enforcement" || activeRoleId === "private_investigator") && (
                  <GraphCanvas
                    caseId={activeCaseId}
                    onRefreshStats={() => loadStats(activeCaseId)}
                  />
                )}
              </>
            )}

            {/* Standard Fullständiga Moduler */}
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
          onCaseCreated={() => loadData()}
        />
      )}

      {/* API-Valv (BYOAK) modal */}
      {showVaultModal && (
        <CredentialVaultModal
          onClose={() => setShowVaultModal(false)}
          onKeysChanged={() => loadStats(activeCaseId)}
        />
      )}

      {/* Frivillig 2FA Säkerhets-modal */}
      {show2FAModal && (
        <TwoFactorSettingsModal
          isOpen={show2FAModal}
          onClose={() => setShow2FAModal(false)}
          onStatusChanged={() => load2FAStatus()}
        />
      )}

      {/* Global Step-Up modal */}
      {showStepUpModal && (
        <StepUpModal
          isOpen={showStepUpModal}
          onClose={() => setShowStepUpModal(false)}
          onSuccess={() => {
            load2FAStatus();
            if (activeCaseId) loadStats(activeCaseId);
          }}
        />
      )}
    </div>
  );
}
