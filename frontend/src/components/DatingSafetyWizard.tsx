"use client";

import React, { useState } from "react";
import { DatingVerificationResult } from "@/types";
import { api } from "@/lib/api";
import {
  HeartHandshake,
  ShieldAlert,
  ShieldCheck,
  Search,
  Camera,
  Phone,
  Mail,
  FileText,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

interface DatingSafetyWizardProps {
  caseId: string;
  onVerificationDone?: () => void;
}

export default function DatingSafetyWizard({
  caseId,
  onVerificationDone,
}: DatingSafetyWizardProps) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [story, setStory] = useState("");

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DatingVerificationResult | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      setRunning(true);
      const res = await api.runDatingVerification({
        case_id: caseId,
        name: name.trim(),
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        image_url: imageUrl.trim() || undefined,
        story: story.trim() || undefined,
      });

      setResult(res);
      if (onVerificationDone) onVerificationDone();
    } catch (err: any) {
      alert(`Kunde inte genomföra verifiering: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setName("");
    setPhone("");
    setEmail("");
    setImageUrl("");
    setStory("");
  };

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] p-6 overflow-y-auto">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center pb-4 border-b border-slate-800">
          <div className="inline-flex p-3 rounded-2xl bg-pink-950/40 border border-pink-700/50 mb-3 shadow-lg">
            <HeartHandshake className="w-8 h-8 text-pink-400" />
          </div>
          <h2 className="text-2xl font-bold text-slate-100">
            Säkerhetskoll & Dejt-verifiering
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-lg mx-auto">
            Defensiv verifiering för att skydda dig mot romansbedrägerier, sol-och-vår-profiler,
            stulna foton (catfishing) och anonyma engångsnummer.
          </p>
        </div>

        {!result ? (
          /* Steg-för-steg Formulär (Wizard) */
          <form
            onSubmit={handleSubmit}
            className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-slate-200 mb-1">
                Namn eller Alias på personen *
              </label>
              <input
                type="text"
                placeholder="t.ex. Sophia Miller, Marcus Lind, Dr. Alex"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl p-3 focus:border-pink-500 focus:outline-none"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-slate-400" /> Telefonnummer
                </label>
                <input
                  type="text"
                  placeholder="+46701234567 eller +12025550199"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl p-3 focus:border-pink-500 focus:outline-none"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Kontrollerar om numret är ett anonymt VoIP / burner-nummer.
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-slate-400" /> E-postadress
                </label>
                <input
                  type="email"
                  placeholder="kontakt@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl p-3 focus:border-pink-500 focus:outline-none"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Korsrefereras mot dataläckor och registrerade konton.
                </span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <Camera className="w-3.5 h-3.5 text-slate-400" /> Länk till profilbild (eller bild-URL)
              </label>
              <input
                type="text"
                placeholder="https://.../profilfoto.jpg"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl p-3 focus:border-pink-500 focus:outline-none"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">
                Jämförs mot kända sol-och-vår-modeller, stockfoton och AI-genererade ansikten.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-slate-400" /> Berättelse, yrke eller påstående (frivilligt)
              </label>
              <textarea
                rows={2}
                placeholder="t.ex. Påstår sig arbeta som militärläkare i Syrien, vill skicka paket med tullavgift..."
                value={story}
                onChange={(e) => setStory(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl p-3 focus:border-pink-500 focus:outline-none"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">
                Skannas mot varningslistornas vanligaste bedrägerinarrativ.
              </span>
            </div>

            <button
              type="submit"
              disabled={running}
              className="w-full bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white font-bold text-xs py-3.5 rounded-xl shadow-lg transition flex items-center justify-center gap-2 mt-4"
            >
              <Search className="w-4 h-4" />
              {running ? "Kör defensiv verifiering..." : "Kör Säkerhetskoll Nu"}
            </button>
          </form>
        ) : (
          /* Resultatkort med tydlig klartextbedömning */
          <div className="space-y-5 animate-in fade-in duration-300">
            {/* Huvudresultat Banner */}
            <div
              className={`p-6 rounded-2xl border shadow-xl text-center ${
                result.risk_level === "CRITICAL"
                  ? "bg-rose-950/40 border-rose-600 text-rose-200"
                  : result.risk_level === "WARNING"
                  ? "bg-amber-950/40 border-amber-600 text-amber-200"
                  : "bg-emerald-950/40 border-emerald-600 text-emerald-200"
              }`}
            >
              <div className="inline-flex p-3 rounded-full bg-black/40 mb-2">
                {result.risk_level === "CRITICAL" ? (
                  <ShieldAlert className="w-10 h-10 text-rose-400" />
                ) : result.risk_level === "WARNING" ? (
                  <AlertTriangle className="w-10 h-10 text-amber-400" />
                ) : (
                  <ShieldCheck className="w-10 h-10 text-emerald-400" />
                )}
              </div>

              <div className="text-xs uppercase tracking-widest font-bold opacity-80">
                Utredningens Slutsats
              </div>
              <h3 className="text-xl font-extrabold mt-1">{result.overall_verdict}</h3>
              <p className="text-xs mt-2 max-w-lg mx-auto font-medium">
                {result.recommended_action}
              </p>

              {/* Risknivå mätare */}
              <div className="mt-4 max-w-xs mx-auto">
                <div className="flex justify-between text-[11px] font-bold mb-1">
                  <span>Beräknad Riskfaktor</span>
                  <span>{result.risk_score_pct}%</span>
                </div>
                <div className="w-full h-2.5 bg-black/50 rounded-full overflow-hidden p-0.5">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ${
                      result.risk_level === "CRITICAL"
                        ? "bg-rose-500"
                        : result.risk_level === "WARNING"
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${Math.max(8, result.risk_score_pct)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Detaljerade kontrollpunkter */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* 1. Bildkontroll */}
              <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Camera className="w-4 h-4 text-pink-400" />
                  <span className="text-xs font-bold text-slate-200">Catfish & Bildanalys</span>
                </div>
                {result.catfish_check.detected ? (
                  <div className="text-xs text-rose-400 font-semibold flex items-start gap-1.5 mt-2">
                    <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>Matchning mot stulna bilder: {result.catfish_check.source}</span>
                  </div>
                ) : (
                  <div className="text-xs text-emerald-400 font-medium flex items-center gap-1.5 mt-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>Inga träffar i sol-och-vår-register</span>
                  </div>
                )}
              </div>

              {/* 2. Telefonkontroll */}
              <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Phone className="w-4 h-4 text-sky-400" />
                  <span className="text-xs font-bold text-slate-200">Telefonoperatör & VoIP</span>
                </div>
                {result.phone_check.is_voip ? (
                  <div className="text-xs text-amber-400 font-semibold flex items-start gap-1.5 mt-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>Virtuellt burner-nummer ({result.phone_check.carrier})</span>
                  </div>
                ) : result.phone_check.checked ? (
                  <div className="text-xs text-emerald-400 font-medium flex items-center gap-1.5 mt-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>Vanligt mobilabonnemang ({result.phone_check.carrier})</span>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic mt-2">Inget nummer angavs</div>
                )}
              </div>

              {/* 3. Digitalt fotspår */}
              <div className="bg-[#111827] border border-slate-800 p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Search className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-slate-200">Digitala Fotspår</span>
                </div>
                <div className="text-xs text-slate-300 mt-2">
                  Funna offentliga konton: <strong>{result.profiles_found} st</strong>
                </div>
              </div>
            </div>

            {/* Varningsflaggor lista */}
            {result.risk_factors.length > 0 && (
              <div className="bg-[#111827] border border-slate-800 p-5 rounded-2xl">
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" /> Identifierade Riskfaktorer
                </h4>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {result.risk_factors.map((rf, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-rose-400 font-bold">•</span>
                      <span>{rf}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-between items-center pt-2">
              <button
                onClick={handleReset}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 px-3 py-2 bg-slate-800 rounded-xl transition"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Gör en ny säkerhetskoll
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
