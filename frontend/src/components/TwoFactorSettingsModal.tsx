"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  KeyRound,
  Smartphone,
  Trash2,
  Plus,
  RefreshCw,
  Copy,
  Check,
  Loader2,
  Lock,
  Unlock,
  X,
  AlertTriangle,
  FileKey,
} from "lucide-react";
import { startRegistration } from "@simplewebauthn/browser";
import { api } from "@/lib/api";
import { TwoFactorStatus, SecurityKeyItem, TOTPGenerateData } from "@/types";
import { BackupCodesModal } from "./BackupCodesModal";

interface TwoFactorSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStatusChanged?: () => void;
}

export const TwoFactorSettingsModal: React.FC<TwoFactorSettingsModalProps> = ({
  isOpen,
  onClose,
  onStatusChanged,
}) => {
  const [status, setStatus] = useState<TwoFactorStatus | null>(null);
  const [keys, setKeys] = useState<SecurityKeyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // TOTP Konfigurationstillstånd
  const [totpSetupData, setTotpSetupData] = useState<TOTPGenerateData | null>(null);
  const [totpInputCode, setTotpInputCode] = useState("");
  const [totpCopied, setTotpCopied] = useState(false);
  const [totpLoading, setTotpLoading] = useState(false);

  // WebAuthn Registreringstillstånd
  const [isRegisteringKey, setIsRegisteringKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState("YubiKey 5C NFC");
  const [showKeyNamePrompt, setShowKeyNamePrompt] = useState(false);

  // Nödkoder som visas vid första aktivering eller omgenerering
  const [newBackupCodes, setNewBackupCodes] = useState<string[] | null>(null);

  const fetchStatusAndKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const [st, kList] = await Promise.all([
        api.get2FAStatus(),
        api.listSecurityKeys(),
      ]);
      setStatus(st);
      setKeys(kList);
    } catch (err: any) {
      setError(err.message || "Kunde inte hämta 2FA-inställningar");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatusAndKeys();
      setTotpSetupData(null);
      setError(null);
      setSuccessMsg(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // --- WEBAUTHN FIDO2 REGISTRERING ---
  const handleStartWebAuthnRegistration = async () => {
    setIsRegisteringKey(true);
    setError(null);
    setSuccessMsg(null);
    try {
      // 1. Hämta registration options
      const options = await api.getWebAuthnRegOptions();

      // 2. Öppna webbläsarens / operativsystemets prompt
      const attResp = await startRegistration(options);

      // 3. Verifiera och spara nyckel i backend
      const res = await api.verifyWebAuthnRegistration({
        key_name: newKeyName.trim() || "Säkerhetsnyckel",
        credential: attResp,
      });

      setSuccessMsg(res.message);
      setShowKeyNamePrompt(false);
      setNewKeyName("YubiKey 5C NFC");

      if (res.backup_codes && res.backup_codes.length > 0) {
        setNewBackupCodes(res.backup_codes);
      }

      await fetchStatusAndKeys();
      onStatusChanged?.();
    } catch (err: any) {
      console.error("WebAuthn error:", err);
      if (err.name === "NotAllowedError") {
        setError("Registreringen avbröts av användaren eller tog för lång tid.");
      } else {
        setError(err.message || "Kunde inte registrera säkerhetsnyckel.");
      }
    } finally {
      setIsRegisteringKey(false);
    }
  };

  const handleDeleteKey = async (keyId: string, keyName: string) => {
    if (!confirm(`Är du säker på att du vill ta bort säkerhetsnyckeln "${keyName}"?`)) return;
    try {
      await api.deleteSecurityKey(keyId);
      setSuccessMsg(`Nyckeln "${keyName}" raderades.`);
      await fetchStatusAndKeys();
      onStatusChanged?.();
    } catch (err: any) {
      setError(err.message || "Kunde inte radera nyckel.");
    }
  };

  // --- TOTP AKTIVERING ---
  const handleStartTotpSetup = async () => {
    setTotpLoading(true);
    setError(null);
    try {
      const data = await api.generateTOTPSecret();
      setTotpSetupData(data);
      setTotpInputCode("");
    } catch (err: any) {
      setError(err.message || "Kunde inte initiera TOTP-konfiguration.");
    } finally {
      setTotpLoading(false);
    }
  };

  const handleVerifyTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!totpInputCode || totpInputCode.trim().length !== 6) {
      setError("Ange den 6-siffriga koden från din app.");
      return;
    }

    setTotpLoading(true);
    setError(null);
    try {
      const res = await api.enableTOTP(totpInputCode.trim());
      setSuccessMsg(res.message);
      setTotpSetupData(null);
      setTotpInputCode("");

      if (res.backup_codes && res.backup_codes.length > 0) {
        setNewBackupCodes(res.backup_codes);
      }

      await fetchStatusAndKeys();
      onStatusChanged?.();
    } catch (err: any) {
      setError(err.message || "Felaktig kod. Försök igen.");
    } finally {
      setTotpLoading(false);
    }
  };

  const handleDisableTotp = async () => {
    if (!confirm("Vill du koppla bort din autentiseringsapp från kontot?")) return;
    try {
      await api.disableTOTP();
      setSuccessMsg("Autentiseringsapp har kopplats bort.");
      await fetchStatusAndKeys();
      onStatusChanged?.();
    } catch (err: any) {
      setError(err.message || "Kunde inte avaktivera TOTP.");
    }
  };

  // --- STEP-UP TOGGLE ---
  const handleToggleStepUpVault = async (checked: boolean) => {
    try {
      await api.toggleStepUpVault(checked);
      await fetchStatusAndKeys();
      onStatusChanged?.();
    } catch (err: any) {
      setError(err.message || "Kunde inte ändra valvinställning.");
    }
  };

  // --- REGENERATE BACKUP CODES ---
  const handleRegenerateBackupCodes = async () => {
    if (!confirm("Detta kommer att ogiltigförklara eventuella gamla nödkoder och skapa 8 nya. Fortsätt?")) return;
    try {
      const res = await api.regenerateBackupCodes();
      setNewBackupCodes(res.backup_codes);
      await fetchStatusAndKeys();
    } catch (err: any) {
      setError(err.message || "Kunde inte generera nya nödkoder.");
    }
  };

  // --- FULLSTÄNDIG AVAKTIVERING ---
  const handleDisableAll2FA = async () => {
    if (!confirm("Är du helt säker på att du vill stänga av 2FA? Alla registrerade hårdvarunycklar och nödkoder kommer att raderas.")) return;
    try {
      await api.disableAll2FA();
      setSuccessMsg("Tvåfaktorsautentisering har stängts av helt.");
      await fetchStatusAndKeys();
      onStatusChanged?.();
    } catch (err: any) {
      setError(err.message || "Kunde inte avaktivera 2FA.");
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
        <div className="w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl p-6 flex flex-col gap-6 text-slate-100 my-8 animate-in fade-in zoom-in-95 duration-200">
          
          {/* Header */}
          <div className="flex items-start justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                <Shield className="w-7 h-7" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  Tvåfaktorsautentisering (2FA)
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-normal">
                    Frivilligt skydd
                  </span>
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Kryptografiskt skydd med FIDO2/WebAuthn hårdvarunycklar och TOTP-appar för myndigheter och visselblåsare.
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Statusbanner */}
          {status && (
            <div
              className={`p-4 rounded-xl border flex items-center justify-between gap-4 ${
                status.is_2fa_enabled
                  ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                  : "bg-slate-950/50 border-slate-800 text-slate-300"
              }`}
            >
              <div className="flex items-center gap-3">
                {status.is_2fa_enabled ? (
                  <ShieldCheck className="w-6 h-6 text-emerald-400 shrink-0" />
                ) : (
                  <Shield className="w-6 h-6 text-slate-500 shrink-0" />
                )}
                <div>
                  <div className="text-sm font-semibold flex items-center gap-2">
                    {status.is_2fa_enabled ? (
                      <span className="text-emerald-400">Aktivt 2FA-skydd</span>
                    ) : (
                      <span className="text-slate-300">Inaktivt (Standard)</span>
                    )}
                    {status.is_elevated && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/30">
                        Valv upplåst
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {status.is_2fa_enabled
                      ? `Skyddas av ${status.security_keys_count} hårdvarunyckel/nycklar ${
                          status.totp_verified ? "och TOTP-app" : ""
                        }.`
                      : "Inget krav på 2FA. Systemet fungerar helt utan hårdvarunycklar eller appar tills du väljer att aktivera det."}
                  </p>
                </div>
              </div>

              {status.is_2fa_enabled && (
                <button
                  onClick={handleDisableAll2FA}
                  className="text-xs text-rose-400 hover:text-rose-300 underline font-medium shrink-0"
                >
                  Avaktivera 2FA
                </button>
              )}
            </div>
          )}

          {/* Meddelanden */}
          {error && (
            <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {successMsg && (
            <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
              <Check className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Huvudsektioner */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* KORT 1: HÅRDVARUNYCKLAR (FIDO2 / WEBAUTHN) */}
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-white font-semibold text-sm">
                    <KeyRound className="w-4 h-4 text-sky-400" />
                    Hårdvarunycklar (FIDO2)
                  </div>
                  <span className="text-[11px] text-slate-400">YubiKey / Nitrokey</span>
                </div>
                <p className="text-xs text-slate-400 mb-3">
                  W3C WebAuthn Level 3. Fysisk beröring krävs, immun mot nätfiske och MITM.
                </p>

                {/* Lista över registrerade nycklar */}
                <div className="space-y-2 mb-3">
                  {keys.length === 0 ? (
                    <div className="text-xs text-slate-500 italic p-2 bg-slate-900/50 rounded border border-slate-800/80 text-center">
                      Inga säkerhetsnycklar registrerade.
                    </div>
                  ) : (
                    keys.map((k) => (
                      <div
                        key={k.id}
                        className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800 text-xs"
                      >
                        <div>
                          <div className="text-slate-200 font-medium">{k.key_name}</div>
                          <div className="text-[10px] text-slate-500 font-mono">
                            Räknare: {k.sign_count} • Skapad: {k.created_at.slice(0, 10)}
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteKey(k.id, k.key_name)}
                          className="p-1 text-slate-500 hover:text-rose-400 transition"
                          title="Radera nyckel"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Registreringsprompt / knapp */}
              <div>
                {showKeyNamePrompt ? (
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-700 flex flex-col gap-2">
                    <label className="text-[11px] text-slate-300 font-medium">Namn på säkerhetsnyckel:</label>
                    <input
                      type="text"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      placeholder="t.ex. YubiKey 5C NFC"
                      className="px-2.5 py-1.5 bg-slate-950 border border-slate-700 rounded text-xs text-white focus:outline-none focus:border-sky-500"
                    />
                    <div className="flex gap-2 justify-end mt-1">
                      <button
                        onClick={() => setShowKeyNamePrompt(false)}
                        className="px-2.5 py-1 text-xs text-slate-400 hover:text-white"
                      >
                        Avbryt
                      </button>
                      <button
                        onClick={handleStartWebAuthnRegistration}
                        disabled={isRegisteringKey}
                        className="px-3 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-semibold flex items-center gap-1.5"
                      >
                        {isRegisteringKey ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                        Berör nyckel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowKeyNamePrompt(true)}
                    className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition"
                  >
                    <Plus className="w-4 h-4 text-sky-400" />
                    Registrera ny hårdvarunyckel
                  </button>
                )}
              </div>
            </div>

            {/* KORT 2: TOTP APPAR */}
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-white font-semibold text-sm">
                    <Smartphone className="w-4 h-4 text-emerald-400" />
                    Autentiseringsapp (TOTP)
                  </div>
                  <span className="text-[11px] text-slate-400">RFC 6238</span>
                </div>
                <p className="text-xs text-slate-400 mb-3">
                  Fungerar offline med Aegis, YubiKey Authenticator, 1Password eller Google Authenticator.
                </p>

                {status?.totp_verified ? (
                  <div className="p-3 bg-emerald-950/30 border border-emerald-500/20 rounded-lg flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
                      <Check className="w-4 h-4" />
                      Kopplad och aktiv
                    </div>
                    <button
                      onClick={handleDisableTotp}
                      className="text-[11px] text-slate-400 hover:text-rose-400 transition underline"
                    >
                      Koppla bort
                    </button>
                  </div>
                ) : totpSetupData ? (
                  <div className="p-3 bg-slate-900 border border-slate-700 rounded-lg flex flex-col gap-3">
                    <div className="flex justify-center bg-white p-2 rounded">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={totpSetupData.qr_code_svg}
                        alt="TOTP QR Code"
                        className="w-36 h-36"
                      />
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-400 mb-1">Manuell hemlig nyckel:</div>
                      <div className="flex items-center justify-between bg-slate-950 p-1.5 rounded font-mono text-[11px] text-amber-400">
                        <span>{totpSetupData.secret}</span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(totpSetupData.secret);
                            setTotpCopied(true);
                            setTimeout(() => setTotpCopied(false), 2000);
                          }}
                          className="text-slate-400 hover:text-white p-1"
                        >
                          {totpCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        </button>
                      </div>
                    </div>
                    <form onSubmit={handleVerifyTotp} className="flex gap-2">
                      <input
                        type="text"
                        maxLength={6}
                        placeholder="000 000"
                        value={totpInputCode}
                        onChange={(e) => setTotpInputCode(e.target.value.replace(/\D/g, ""))}
                        className="w-full px-2 py-1.5 bg-slate-950 border border-slate-700 rounded text-center font-mono text-sm tracking-wider text-white focus:outline-none focus:border-emerald-500"
                      />
                      <button
                        type="submit"
                        disabled={totpLoading || totpInputCode.length !== 6}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-xs font-semibold shrink-0"
                      >
                        {totpLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Verifiera"}
                      </button>
                    </form>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic p-3 bg-slate-900/50 rounded border border-slate-800/80 text-center">
                    Ingen autentiseringsapp är konfigurerad ännu.
                  </div>
                )}
              </div>

              {!status?.totp_verified && !totpSetupData && (
                <button
                  onClick={handleStartTotpSetup}
                  disabled={totpLoading}
                  className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition mt-3"
                >
                  <Plus className="w-4 h-4 text-emerald-400" />
                  Konfigurera TOTP-app
                </button>
              )}
            </div>
          </div>

          {/* STEP-UP & NÖDKODER INSTÄLLNINGAR */}
          <div className="border-t border-slate-800 pt-4 flex flex-col gap-4">
            
            {/* Step-Up Valv-toggle */}
            <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-800 rounded-xl">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0 mt-0.5">
                  <Lock className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">
                    Kräv 2FA vid åtkomst till API-valvet (Step-Up)
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    När aktiverat krävs fysisk beröring av din säkerhetsnyckel eller TOTP-kod varje gång valvet öppnas. Valvet förblir upplåst i 15 minuter.
                  </p>
                </div>
              </div>

              <label className="relative inline-flex items-center cursor-pointer shrink-0 ml-4">
                <input
                  type="checkbox"
                  checked={status?.step_up_vault_required || false}
                  disabled={!status?.is_2fa_enabled}
                  onChange={(e) => handleToggleStepUpVault(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600 disabled:opacity-30"></div>
              </label>
            </div>

            {/* Nödkoder info */}
            {status?.is_2fa_enabled && (
              <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-800 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
                    <FileKey className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">
                      Engångskoder för återställning
                    </div>
                    <p className="text-xs text-slate-400">
                      {status.unused_backup_codes_count} av 8 oanvända nödkoder kvar.
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleRegenerateBackupCodes}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded text-xs font-medium transition"
                >
                  Generera nya nödkoder
                </button>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-slate-800 pt-3 flex items-center justify-between">
            <span className="text-[11px] text-slate-500">
              OpenIntel Security • FIDO2 WebAuthn & RFC 6238
            </span>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
            >
              Stäng
            </button>
          </div>
        </div>
      </div>

      {/* Modal som visar nya engångskoder om sådana genererats */}
      {newBackupCodes && (
        <BackupCodesModal
          codes={newBackupCodes}
          onClose={() => setNewBackupCodes(null)}
        />
      )}
    </>
  );
};
