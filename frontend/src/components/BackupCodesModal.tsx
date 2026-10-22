"use client";

import React, { useState } from "react";
import { ShieldAlert, Copy, Download, Check, Key } from "lucide-react";

interface BackupCodesModalProps {
  codes: string[];
  onClose: () => void;
}

export const BackupCodesModal: React.FC<BackupCodesModalProps> = ({ codes, onClose }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const text = `OPENINTEL OSINT PLATFORM - 2FA NÖDKODER\nSpara dessa koder på en säker plats. Varje kod kan användas en gång.\n\n` +
      codes.map((c, i) => `${i + 1}. ${c}`).join("\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownload = () => {
    const text = `OPENINTEL OSINT PLATFORM - 2FA NÖDKODER\nGenererade: ${new Date().toISOString()}\n\nVarje kod är för engångsbruk vid förlorad säkerhetsnyckel eller autentiseringsapp:\n\n` +
      codes.map((c, i) => `${i + 1}. ${c}`).join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `openintel-recovery-codes-${new Date().toISOString().slice(0, 10)}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-slate-900 border border-amber-500/30 rounded-xl shadow-2xl p-6 flex flex-col gap-5 text-slate-100 animate-in fade-in zoom-in-95 duration-200">
        
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Spara dina nödkoder</h3>
            <p className="text-xs text-slate-400 mt-1">
              Dessa engångskoder visas <span className="text-amber-400 font-semibold">endast en gång</span>. De kan användas om du förlorar din säkerhetsnyckel eller telefon.
            </p>
          </div>
        </div>

        {/* Kodrutnät */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 font-mono text-sm">
          <div className="grid grid-cols-2 gap-2 text-center">
            {codes.map((code, idx) => (
              <div
                key={idx}
                className="bg-slate-900/80 border border-slate-800/80 rounded py-1.5 px-2 text-emerald-400 font-semibold tracking-wider selection:bg-emerald-500 selection:text-black"
              >
                {code}
              </div>
            ))}
          </div>
        </div>

        <div className="text-xs text-slate-400 bg-slate-800/40 border border-slate-700/50 rounded-lg p-3 flex items-center gap-2">
          <Key className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Varje kod kan endast användas en gång för att logga in eller låsa upp valvet.</span>
        </div>

        {/* Åtgärdsknappar */}
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center justify-center gap-2 py-2 px-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-xs font-medium transition"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-slate-400" />}
              {copied ? "Kopierade!" : "Kopiera koder"}
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center justify-center gap-2 py-2 px-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-xs font-medium transition"
            >
              <Download className="w-4 h-4 text-slate-400" />
              Ladda ner .txt
            </button>
          </div>

          <button
            onClick={onClose}
            className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-semibold shadow-lg shadow-emerald-900/30 transition mt-2"
          >
            Jag har sparat koderna säkert
          </button>
        </div>
      </div>
    </div>
  );
};
