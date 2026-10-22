"use client";

import React, { useEffect, useRef, useState } from "react";
import { Entity } from "@/types";
import { api } from "@/lib/api";
import { MapPin, Globe, Compass, ShieldAlert } from "lucide-react";

interface MapViewProps {
  caseId: string;
}

interface GeoPoint {
  entity: Entity;
  lat: number;
  lng: number;
  title: string;
  subtitle: string;
}

export default function MapView({ caseId }: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);

  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPoint, setSelectedPoint] = useState<GeoPoint | null>(null);

  useEffect(() => {
    async function loadGeoData() {
      try {
        setLoading(true);
        const entities = await api.listEntities(caseId);

        const foundPoints: GeoPoint[] = [];
        entities.forEach((e: Entity) => {
          const lat = parseFloat(e.attributes?.latitude);
          const lng = parseFloat(e.attributes?.longitude);
          if (!isNaN(lat) && !isNaN(lng)) {
            foundPoints.push({
              entity: e,
              lat,
              lng,
              title: e.name,
              subtitle:
                e.attributes?.country ||
                e.attributes?.city ||
                (e.type === "location" ? "Geografisk plats" : "Server/IP Placering"),
            });
          }
        });

        setPoints(foundPoints);
      } catch (err) {
        console.error("Kunde inte hämta kartdata:", err);
      } finally {
        setLoading(false);
      }
    }

    if (caseId) {
      loadGeoData();
    }
  }, [caseId]);

  // Initiera Leaflet klient-sidan
  useEffect(() => {
    if (!mapContainerRef.current) return;

    let isMounted = true;

    import("leaflet").then((L) => {
      if (!isMounted || !mapContainerRef.current) return;

      if (!leafletMapRef.current) {
        const map = L.map(mapContainerRef.current).setView([59.3293, 18.0686], 4);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 18,
        }).addTo(map);

        leafletMapRef.current = map;
      }

      // Rensa gamla markörer
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      const map = leafletMapRef.current;
      const markerGroup = L.featureGroup();

      points.forEach((pt) => {
        const marker = L.circleMarker([pt.lat, pt.lng], {
          radius: 9,
          fillColor: pt.entity.type === "location" ? "#ec4899" : "#06b6d4",
          color: "#ffffff",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.85,
        });

        marker.bindPopup(`
          <div style="font-family: inherit; font-size: 12px; color: #111;">
            <strong>${pt.title}</strong><br/>
            <span>${pt.subtitle}</span><br/>
            <small style="color: #666;">Lat: ${pt.lat.toFixed(4)}, Lon: ${pt.lng.toFixed(4)}</small>
          </div>
        `);

        marker.on("click", () => {
          setSelectedPoint(pt);
        });

        marker.addTo(map);
        markerGroup.addLayer(marker);
        markersRef.current.push(marker);
      });

      if (points.length > 0) {
        map.fitBounds(markerGroup.getBounds(), { padding: [50, 50], maxZoom: 12 });
      }
    });

    return () => {
      isMounted = false;
    };
  }, [points]);

  const focusPoint = (pt: GeoPoint) => {
    setSelectedPoint(pt);
    if (leafletMapRef.current) {
      leafletMapRef.current.flyTo([pt.lat, pt.lng], 12, { duration: 1.2 });
    }
  };

  return (
    <div className="w-full h-[calc(100vh-68px)] bg-[#090d16] flex relative overflow-hidden">
      {/* Vänster sidofält med lista över identifierade geokoordinater */}
      <div className="w-80 h-full bg-[#0f172a] border-r border-slate-800 p-4 flex flex-col z-10 shadow-xl">
        <div className="pb-3 border-b border-slate-800">
          <h3 className="font-bold text-slate-100 flex items-center gap-2 text-sm">
            <Compass className="w-4 h-4 text-sky-400" /> Geointelligens (GEOINT)
          </h3>
          <p className="text-[11px] text-slate-400 mt-1">
            {points.length} noder med verifierade GPS- eller GeoIP-koordinater.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto mt-3 space-y-2">
          {loading ? (
            <div className="text-xs text-slate-500 py-6 text-center">Laddar geonoder...</div>
          ) : points.length === 0 ? (
            <div className="text-xs text-slate-500 py-10 text-center">
              Inga noder i ärendet har koordinater ännu. Kör IP-Geo eller EXIF transforms för att
              geolokalisera.
            </div>
          ) : (
            points.map((pt, idx) => (
              <button
                key={idx}
                onClick={() => focusPoint(pt)}
                className={`w-full text-left p-2.5 rounded-xl border transition flex items-start gap-2.5 ${
                  selectedPoint?.entity.id === pt.entity.id
                    ? "bg-sky-950/40 border-sky-500/60"
                    : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                }`}
              >
                <MapPin className="w-4 h-4 text-pink-400 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-slate-200 truncate">{pt.title}</div>
                  <div className="text-[11px] text-slate-400 truncate">{pt.subtitle}</div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    {pt.lat.toFixed(4)}, {pt.lng.toFixed(4)}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Själva kartcontainern */}
      <div className="flex-1 h-full relative">
        <div ref={mapContainerRef} className="w-full h-full z-0" />
      </div>
    </div>
  );
}
