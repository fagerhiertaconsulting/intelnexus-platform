"use client";

import React, { useEffect, useState } from "react";
import { VaultKey } from "@/types";
import { api } from "@/lib/api";
import {
  Key,
  ShieldCheck,
  Lock,
  Unlock,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  X,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
  KeyRound,
} from "lucide-react";
import { StepUpModal } from "./StepUpModal";

interface CredentialVaultModalProps {
  onClose: () => void;
  onKeysChanged?: () => void;
}

export default function CredentialVaultModal({
  onClose,
  onKeysChanged,
}: CredentialVaultModalProps) {
  const [keys, setKeys] = useState<VaultKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKeyName, setSelectedKeyName] = useState<string>("");
  const [keyValue, setKeyValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [isLockedBy2FA, setIsLockedBy2FA] = useState(false);
  const [showStepUpModal, setShowStepUpModal] = useState(false);

  const loadKeys = async () => {
    try {
      setLoading(true);
      const data = await api.listVaultKeys();
      setKeys(data);
      setIsLockedBy2FA(false);
    } catch (err: any) {
      if (err.requiresStepUp || err.status === 403) {
        setIsLockedBy2FA(true);
      }
      console.error("Kunde inte hämta valvnycklar:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleSaveKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedKeyName || !keyValue.trim()) return;

    try {
      setSaving(true);
      await api.storeVaultKey(selectedKeyName, keyValue.trim());
      setKeyValue("");
      setSelectedKeyName("");
      await loadKeys();
      if (onKeysChanged) onKeysChanged();
      alert("API-nyckeln har krypterats och sparats i det lokala AES-256-GCM valvet!");
    } catch (err: any) {
      alert(`Kunde inte spara nyckel: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (keyName: string) => {
    if (confirm(`Radera API-nyckeln för ${keyName} från det lokala valvet?`)) {
      await api.deleteVaultKey(keyName);
      await loadKeys();
      if (onKeysChanged) onKeysChanged();
    }
  };

  const handleTest = async (keyName: string) => {
    try {
      setTesting(keyName);
      const res = await api.testVaultKey(keyName);
      alert(`Nyckeln är giltig och operativ! (Längd: ${res.length} tecken)`);
    } catch (err: any) {
      alert(`Test misslyckades: ${err.message}`);
    } finally {
      setTesting(null);
    }
  };

  const configuredCount = keys.filter((k) => k.is_configured).length;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#111827] border border-slate-700 w-full max-w-2xl rounded-2xl p-6 shadow-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start pb-4 border-b border-slate-800">
          <div>
            <h3 className="font-bold text-slate-100 text-base flex items-center gap-2">
              <Key className="w-5 h-5 text-amber-400" /> Lokalt API-Valv (BYOAK Architecture)
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Alla API-nycklar krypteras lokalt på din maskin med <strong>AES-256-GCM</strong>.
              Inga nycklar skickas någonsin till någon extern server utom den avsedda tjänsten.
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Statusbar */}
        <div className="flex items-center justify-between bg-slate-900/60 p-3 rounded-xl border border-slate-800 my-4 text-xs">
          <div className="flex items-center gap-2 text-slate-300">
            {isLockedBy2FA ? (
              <Lock className="w-4 h-4 text-amber-400" />
            ) : (
              <Lock className="w-4 h-4 text-emerald-400" />
            )}
            <span>
              Krypteringsläge: <strong>AES-256-GCM (Zero-Knowledge)</strong>
              {isLockedBy2FA && <span className="text-amber-400 font-semibold ml-2">• 2FA Låst</span>}
            </span>
          </div>
          <span className="bg-slate-800 px-2 py-0.5 rounded text-sky-400 font-bold">
            {configuredCount} av {keys.length} aktiverade
          </span>
        </div>

        {/* Låst vy vid Step-Up krav */}
        {isLockedBy2FA ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 bg-slate-950/70 border border-amber-500/30 rounded-xl my-2 text-center">
            <div className="p-3.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 mb-3">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <h4 className="text-base font-bold text-white mb-1">Valvet är låst med tvåfaktor (Step-Up)</h4>
            <p className="text-xs text-slate-400 max-w-md mb-5">
              Du har aktiverat extra skydd för ditt lokala API-valv. Bekräfta din identitet med din säkerhetsnyckel eller autentiseringsapp för att dekryptera nycklarna i 15 minuter.
            </p>
            <button
              onClick={() => setShowStepUpModal(true)}
              className="py-2.5 px-5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-sky-900/30 flex items-center gap-2 transition"
            >
              <KeyRound className="w-4 h-4" />
              Lås upp valvet (Step-Up)
            </button>
          </div>
        ) : (
          <>
            {/* Formulär för att lägga till/uppdatera nyckel */}
            <form onSubmit={handleSaveKey} className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-3 mb-4">
              <h4 className="text-xs font-bold text-slate-200">Konfigurera eller Uppdatera API-nyckel</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <select
                  value={selectedKeyName}
                  onChange={(e) => setSelectedKeyName(e.target.value)}
                  className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg p-2 focus:border-amber-500"
                  required
                >
                  <option value="">Välj tjänst / API...</option>
                  {keys.map((k) => (
                    <option key={k.key_name} value={k.key_name}>
                      {k.service} ({k.label}) {k.is_configured ? "✓ Konfigurerad" : ""}
                    </option>
                  ))}
                </select>

                <input
                  type="password"
                  placeholder="Klistra in din API-nyckel här..."
                  value={keyValue}
                  onChange={(e) => setKeyValue(e.target.value)}
                  className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg p-2 focus:border-amber-500"
                  required
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-4 py-1.5 rounded-lg transition shadow flex items-center gap-1.5"
                >
                  <Lock className="w-3.5 h-3.5" />
                  {saving ? "Krypterar..." : "Kryptera & Spara i Valvet"}
                </button>
              </div>
            </form>

            {/* Tabell över stödda tjänster */}
            <div className="flex-1 overflow-y-auto space-y-2">
              {loading ? (
                <div className="text-center py-8 text-xs text-slate-500">Laddar valvstatus...</div>
              ) : (
                keys.map((k) => (
                  <div
                    key={k.key_name}
                    className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-100">{k.service}</span>
                        <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                          {k.domain}
                        </span>
                        {k.is_configured ? (
                          <span className="text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 px-1.5 py-0.5 rounded flex items-center gap-1">
                            <Check className="w-3 h-3" /> Konfigurerad
                          </span>
                        ) : (
                          <span className="text-[10px] bg-slate-800/80 text-slate-500 px-1.5 py-0.5 rounded">
                            Ej inställd
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">{k.description}</p>
                      {k.is_configured && (
                        <div className="text-[10px] font-mono text-slate-500 mt-1">
                          Krypterad: {k.masked_value}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {k.is_configured && (
                        <>
                          <button
                            onClick={() => handleTest(k.key_name)}
                            disabled={testing === k.key_name}
                            className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded transition"
                          >
                            {testing === k.key_name ? "Testar..." : "Testa"}
                          </button>
                          <button
                            onClick={() => handleDelete(k.key_name)}
                            className="text-slate-500 hover:text-rose-400 p-1"
                            title="Radera nyckel"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        <div className="pt-3 mt-3 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200"
          >
            Stäng
          </button>
        </div>
      </div>

      {showStepUpModal && (
        <StepUpModal
          isOpen={showStepUpModal}
          onClose={() => setShowStepUpModal(false)}
          onSuccess={() => {
            setIsLockedBy2FA(false);
            loadKeys();
          }}
          title="Lås upp API-valvet"
          description="Bekräfta din behörighet med FIDO2-nyckel eller TOTP för att komma åt API-nycklarna."
        />
      )}
    </div>
  );
}
