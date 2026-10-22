"use client";

import React from "react";
import { useTranslation } from "react-i18next";
import { TransformInfo, TransformDryRunEstimate } from "@/types";
import {
  Play,
  X,
  DollarSign,
  Clock,
  Coins,
  ShieldCheck,
  AlertTriangle,
  Database,
  Key,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";

interface TransformDryRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  transformInfo: TransformInfo | null;
  targetNode: any;
  estimate: TransformDryRunEstimate | null;
  loading: boolean;
  executing: boolean;
  errorMessage?: string | null;
}

export default function TransformDryRunModal({
  isOpen,
  onClose,
  onConfirm,
  transformInfo,
  targetNode,
  estimate,
  loading,
  executing,
  errorMessage,
}: TransformDryRunModalProps) {
  const { t } = useTranslation(["finops", "common"]);

  if (!isOpen || !transformInfo) return null;

  const cost = estimate?.estimated_cost_usd ?? 0.0;
  const isFree = cost === 0;
  const isCached = estimate?.will_use_cache ?? false;
  const quotaAvailable = estimate?.quota_available ?? true;
  const tokensRequired = estimate?.tokens_required ?? 1;
  const tokensRemaining = estimate?.rate_limit_info?.tokens_remaining ?? 0;
  const duration = estimate?.estimated_duration_seconds ?? 3;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-[#0f172a] border border-slate-700/80 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-start justify-between bg-slate-900/40">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
              <Play className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">
                {t("finops:dry_run_modal_title")}
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {t("finops:dry_run_modal_subtitle")}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={executing}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Target & Transform info */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium">Transform:</span>
              <span className="font-semibold text-sky-400">{transformInfo.display_name}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium">Målobjekt:</span>
              <span className="font-medium text-slate-200 truncate max-w-[260px]">
                {targetNode?.name || targetNode?.label || targetNode?.id}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium">Entitetstyp:</span>
              <span className="text-slate-300 font-mono text-[11px] uppercase bg-slate-800 px-2 py-0.5 rounded">
                {targetNode?.type || "unknown"}
              </span>
            </div>
          </div>

          {/* Estimates Card */}
          {loading ? (
            <div className="py-10 flex flex-col items-center justify-center space-y-2 text-slate-400 text-xs">
              <RefreshCw className="w-6 h-6 text-sky-400 animate-spin" />
              <span>Beräknar tokenkvoter och API-kostnader...</span>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {/* Cost card */}
              <div className="bg-slate-900/90 border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between">
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  <span>{t("finops:estimated_cost")}</span>
                </div>
                <div className="mt-2">
                  <div className="text-lg font-bold text-slate-100">
                    {isCached ? (
                      <span className="text-emerald-400 flex items-center gap-1 text-sm font-semibold">
                        <Database className="w-4 h-4" /> 0.00 USD (Cachat)
                      </span>
                    ) : isFree ? (
                      <span className="text-emerald-400 text-base">Gratis (Community)</span>
                    ) : (
                      <span className="text-amber-400">${cost.toFixed(4)} USD</span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {transformInfo.is_byoak ? t("finops:byoak_mode") : t("finops:free_tier")}
                  </div>
                </div>
              </div>

              {/* Duration card */}
              <div className="bg-slate-900/90 border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between">
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <Clock className="w-4 h-4 text-sky-400" />
                  <span>{t("finops:estimated_duration")}</span>
                </div>
                <div className="mt-2">
                  <div className="text-lg font-bold text-slate-100">
                    ~{duration} sekunder
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    Asynkron exekvering
                  </div>
                </div>
              </div>

              {/* Token Bucket Info */}
              <div className="col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Coins className="w-4 h-4 text-amber-400" />
                    {t("finops:tokens_required")}:
                  </span>
                  <span className="font-semibold text-slate-200">
                    {tokensRequired} token{tokensRequired > 1 ? "s" : ""}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">{t("finops:quota_status")}:</span>
                  {quotaAvailable ? (
                    <span className="text-emerald-400 font-semibold flex items-center gap-1 text-[11px]">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {t("finops:quota_available")} ({tokensRemaining.toFixed(1)} kvar)
                    </span>
                  ) : (
                    <span className="text-rose-400 font-semibold flex items-center gap-1 text-[11px]">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {t("finops:quota_exceeded")}
                    </span>
                  )}
                </div>

                {isCached && (
                  <div className="pt-1 text-[11px] text-emerald-400/90 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{t("finops:cached_result")}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Quota warning */}
          {!quotaAvailable && (
            <div className="p-3 bg-rose-950/40 border border-rose-800/70 rounded-xl text-rose-300 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Kvotvarning: </span>
                {t("finops:warnings.insufficient_quota")}
              </div>
            </div>
          )}

          {/* Execution error */}
          {errorMessage && (
            <div className="p-3 bg-rose-950/60 border border-rose-800 rounded-xl text-rose-300 text-xs">
              {errorMessage}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/60 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={executing}
            className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition"
          >
            {t("common:buttons.cancel")}
          </button>

          <button
            onClick={onConfirm}
            disabled={loading || executing || !quotaAvailable}
            className={`px-5 py-2 text-xs font-semibold rounded-xl transition flex items-center gap-2 shadow-lg ${
              !quotaAvailable
                ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                : executing
                ? "bg-sky-700 text-white cursor-wait"
                : "bg-sky-600 hover:bg-sky-500 text-white shadow-sky-900/30"
            }`}
          >
            {executing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Kör transform...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>{t("finops:confirm_execute")}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
