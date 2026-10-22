"use client";

import React, { useState, useEffect } from "react";
import { ShieldAlert, KeyRound, Smartphone, FileKey, Loader2, CheckCircle2, X } from "lucide-react";
import { startAuthentication } from "@simplewebauthn/browser";
import { api } from "@/lib/api";

interface StepUpModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  title?: string;
  description?: string;
}

export const StepUpModal: React.FC<StepUpModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  title = "Autentisering krävs (Step-Up)",
  description = "Bekräfta din identitet med din säkerhetsnyckel eller autentiseringsapp för att låsa upp valvet.",
}) => {
  const [activeTab, setActiveTab] = useState<"webauthn" | "totp" | "backup">("webauthn");
  const [totpCode, setTotpCode] = useState("");
  const [backupCode, setBackupCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccessMsg(null);
      setTotpCode("");
      setBackupCode("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleWebAuthnTouch = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Hämta auth options från backend
      const options = await api.getWebAuthnAuthOptions();
      // 2. Anropa webbläsarens / hårdvarunyckelns dialog via SimpleWebAuthn
      const assertionResp = await startAuthentication(options);
      // 3. Verifiera assertion mot backend
      const verifyRes = await api.verifyWebAuthnAuth(assertionResp);
      
      setSuccessMsg(verifyRes.message || "Hårdvarunyckel verifierad!");
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 700);
    } catch (err: any) {
      console.error("WebAuthn error:", err);
      if (err.name === "NotAllowedError") {
        setError("Åtgärden avbröts av användaren eller tog för lång tid.");
      } else {
        setError(err.message || "Kunde inte verifiera säkerhetsnyckel.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTotpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!totpCode || totpCode.trim().length !== 6) {
      setError("Ange en giltig 6-siffrig kod.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.stepUpVerify({ method: "totp", code: totpCode.trim() });
      setSuccessMsg(res.message || "Koden bekräftad!");
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || "Felaktig kod. Försök igen.");
    } finally {
      setLoading(false);
    }
  };

  const handleBackupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!backupCode || backupCode.trim().length < 8) {
      setError("Ange din nödkod i formatet XXXX-XXXX.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.verifyBackupCode(backupCode.trim());
      setSuccessMsg(res.message || "Nödkod godkänd!");
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || "Ogiltig eller förbrukad nödkod.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl p-6 flex flex-col gap-5 text-slate-100 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">{title}</h3>
              <p className="text-xs text-slate-400 mt-1">{description}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Flikar */}
        <div className="grid grid-cols-3 gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
          <button
            onClick={() => { setActiveTab("webauthn"); setError(null); }}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded font-medium transition ${
              activeTab === "webauthn"
                ? "bg-slate-800 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <KeyRound className="w-3.5 h-3.5" />
            FIDO2 Nyckel
          </button>
          <button
            onClick={() => { setActiveTab("totp"); setError(null); }}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded font-medium transition ${
              activeTab === "totp"
                ? "bg-slate-800 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Smartphone className="w-3.5 h-3.5" />
            App (TOTP)
          </button>
          <button
            onClick={() => { setActiveTab("backup"); setError(null); }}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded font-medium transition ${
              activeTab === "backup"
                ? "bg-slate-800 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileKey className="w-3.5 h-3.5" />
            Nödkod
          </button>
        </div>

        {/* Status / Felmeddelanden */}
        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            {error}
          </div>
        )}

        {successMsg && (
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Tab 1: WebAuthn / FIDO2 */}
        {activeTab === "webauthn" && (
          <div className="flex flex-col gap-4 py-2">
            <div className="text-xs text-slate-400 text-center">
              Anslut din YubiKey, Nitrokey eller använd biometri (Touch ID / Windows Hello) och tryck på knappen nedan.
            </div>

            <button
              onClick={handleWebAuthnTouch}
              disabled={loading || !!successMsg}
              className="w-full py-3 px-4 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-2 shadow-lg shadow-sky-900/20 transition"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Väntar på säkerhetsnyckel...
                </>
              ) : (
                <>
                  <KeyRound className="w-4 h-4" />
                  Aktivera säkerhetsnyckel
                </>
              )}
            </button>
          </div>
        )}

        {/* Tab 2: TOTP */}
        {activeTab === "totp" && (
          <form onSubmit={handleTotpSubmit} className="flex flex-col gap-4 py-1">
            <div>
              <label className="text-xs text-slate-300 font-medium block mb-1.5">
                Ange 6-siffrig kod från din autentiseringsapp:
              </label>
              <input
                type="text"
                maxLength={6}
                autoFocus
                placeholder="000 000"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                className="w-full px-3 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-center font-mono text-xl tracking-widest text-white focus:outline-none focus:border-sky-500 transition"
              />
            </div>

            <button
              type="submit"
              disabled={loading || totpCode.length !== 6 || !!successMsg}
              className="w-full py-2.5 px-4 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verifiera kod"}
            </button>
          </form>
        )}

        {/* Tab 3: Backup Code */}
        {activeTab === "backup" && (
          <form onSubmit={handleBackupSubmit} className="flex flex-col gap-4 py-1">
            <div>
              <label className="text-xs text-slate-300 font-medium block mb-1.5">
                Ange en 8-teckens nödkod:
              </label>
              <input
                type="text"
                placeholder="XXXX-XXXX"
                value={backupCode}
                onChange={(e) => setBackupCode(e.target.value.toUpperCase())}
                className="w-full px-3 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-center font-mono text-lg tracking-widest text-emerald-400 focus:outline-none focus:border-emerald-500 transition"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Nödkoden förbrukas permanent efter inmatning.
              </span>
            </div>

            <button
              type="submit"
              disabled={loading || backupCode.length < 8 || !!successMsg}
              className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Lös in nödkod"}
            </button>
          </form>
        )}

        <div className="text-[11px] text-slate-500 text-center border-t border-slate-800 pt-3">
          Valvet förblir upplåst i 15 minuter efter bekräftad identitet.
        </div>
      </div>
    </div>
  );
};
