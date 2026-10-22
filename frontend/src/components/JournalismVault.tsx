"use client";

import React, { useState } from "react";
import { api } from "@/lib/api";
import {
  Newspaper,
  Shield,
  FileCheck,
  Upload,
  Download,
  Trash2,
  Lock,
  Sparkles,
  ExternalLink,
  Search,
} from "lucide-react";

interface JournalismVaultProps {
  caseId: string;
}

export default function JournalismVault({ caseId }: JournalismVaultProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [stripping, setStripping] = useState(false);
  const [sanitizedResult, setSanitizedResult] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setSanitizedResult(null);
    }
  };

  const handleStripMetadata = async () => {
    if (!selectedFile) return;

    try {
      setStripping(true);
      const res = await api.sanitizeWhistleblowerMedia(caseId, selectedFile);
      setSanitizedResult(res);
    } catch (err: any) {
      alert(`Kunde inte sanera fil: ${err.message}`);
    } finally {
      setStripping(false);
    }
  };

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] p-6 overflow-y-auto">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Newspaper className="w-5 h-5 text-emerald-400" /> Källskydd & Dokumentvalv
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Verktyg för grävande journalistik: rensning av EXIF/GPS-metadata för att skydda visselblåsare,
              diariesökning och dokumentarkiv.
            </p>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-950/80 border border-emerald-800 text-emerald-400 px-3 py-1 rounded-full">
            Källskydd Aktiverat
          </span>
        </div>

        {/* 1. Metadata Stripper & Vault */}
        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            <h3 className="text-sm font-bold text-slate-200">
              Metadata Stripper: Avidentifiera källmaterial
            </h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Raderar all EXIF-, GPS-positionering, kamerans serienummer och enhetsfingeravtryck ur bilder och
            dokument innan de publiceras eller delas i redaktionen.
          </p>

          <div className="border-2 border-dashed border-slate-700 hover:border-emerald-500/60 p-6 rounded-xl text-center bg-slate-900/40 transition">
            <input
              type="file"
              id="whistleblower-file-input"
              className="hidden"
              onChange={handleFileChange}
              accept="image/*"
            />
            <label
              htmlFor="whistleblower-file-input"
              className="cursor-pointer flex flex-col items-center justify-center space-y-2"
            >
              <Upload className="w-8 h-8 text-slate-400 hover:text-emerald-400 transition" />
              <div className="text-xs font-semibold text-slate-200">
                {selectedFile ? selectedFile.name : "Klicka för att välja fil eller släpp källmaterial här"}
              </div>
              <div className="text-[10px] text-slate-500">
                Stödjer JPEG, PNG, WebP med automatisk SHA-256 revisionslogg.
              </div>
            </label>
          </div>

          {selectedFile && !sanitizedResult && (
            <div className="mt-4 flex justify-end">
              <button
                onClick={handleStripMetadata}
                disabled={stripping}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow transition flex items-center gap-2"
              >
                <Shield className="w-4 h-4" />
                {stripping ? "Sanerar metadata..." : "Sanera & Rensa Metadata"}
              </button>
            </div>
          )}

          {sanitizedResult && (
            <div className="mt-5 p-4 bg-emerald-950/30 border border-emerald-700/60 rounded-xl space-y-2">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold">
                <FileCheck className="w-4 h-4" />
                <span>{sanitizedResult.message}</span>
              </div>
              <div className="text-xs text-slate-300 space-y-1 font-mono text-[11px] pt-1">
                <div>Ursprunglig SHA-256: <span className="text-slate-400">{sanitizedResult.original_sha256}</span></div>
                <div>Sanerad fil SHA-256: <span className="text-emerald-400">{sanitizedResult.sanitized_sha256}</span></div>
              </div>
            </div>
          )}
        </div>

        {/* 2. Myndighetsregister & Diarier */}
        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl">
          <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 mb-2">
            <Search className="w-4 h-4 text-sky-400" /> Offentlighetsregister & Myndighetsdiarier
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Sökning i offentliga diarier, upphandlingsdatabaser och allmänna handlingar för granskning av makthavare.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="font-semibold text-slate-200">Upphandlingsmyndigheten & Konkurrensverket</div>
              <p className="text-[11px] text-slate-400 mt-1">
                Korsreferera offentliga avtal mot bolagsengagemang och jäv.
              </p>
            </div>
            <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="font-semibold text-slate-200">Arkiv- & Ändringsspårare (Wayback)</div>
              <p className="text-[11px] text-slate-400 mt-1">
                Spårar ändringar på myndighetssidor och pressmeddelanden över tid.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
