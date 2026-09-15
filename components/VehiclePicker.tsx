"use client";

import { useEffect, useState } from "react";
import { getSites, Site } from "@/lib/api";
import { MapPin, Truck, Loader2, ChevronRight } from "lucide-react";

const VEHICLES = [
  { id: "Dump Truck",              emoji: "🚛" },
  { id: "Articulated Hauler",      emoji: "🚚" },
  { id: "Excavator",               emoji: "🏗️" },
  { id: "Bulldozer",               emoji: "🚜" },
  { id: "Wheel Loader",            emoji: "⚙️" },
  { id: "Motor Grader",            emoji: "🛣️" },
  { id: "Water Truck",             emoji: "🚒" },
  { id: "Scraper",                 emoji: "🔧" },
  { id: "Drill Rig",               emoji: "⛏️" },
  { id: "Continuous Miner",        emoji: "⛏️" },
  { id: "Scoop Tram",              emoji: "🚜" },
  { id: "Underground Haul Truck",  emoji: "🚛" },
];

interface Props {
  onStart: (site: Site, vehicleType: string) => void;
  onBack: () => void;
}

export default function VehiclePicker({ onStart, onBack }: Props) {
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSite, setSelectedSite] = useState<Site | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<string | null>(null);
  const [loadingSites, setLoadingSites] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSites()
      .then(setSites)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingSites(false));
  }, []);

  return (
    <div className="picker-container">
      <div className="picker-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h2>Vehicle Inspection</h2>
          <p>Select a site and vehicle type to begin the inspection</p>
        </div>
        <button className="btn-ghost" onClick={onBack} style={{ whiteSpace: "nowrap", marginTop: 2 }}>
          ← Back
        </button>
      </div>

      {error && <div className="picker-error">{error}</div>}

      {/* Site picker */}
      <div style={{ marginBottom: 24 }}>
        <div className="picker-section-title" style={{ marginBottom: 10 }}>
          <MapPin size={16} /> Select Site
        </div>
        {loadingSites ? (
          <div className="picker-loading"><Loader2 size={20} className="spin" /> Loading sites…</div>
        ) : sites.length === 0 ? (
          <div className="picker-empty">No active sites found. Ask an admin to create one.</div>
        ) : (
          <div className="picker-list" style={{ maxHeight: 160 }}>
            {sites.map((s) => (
              <button
                key={s.id}
                className={`picker-item ${selectedSite?.id === s.id ? "picker-item-active" : ""}`}
                onClick={() => setSelectedSite(s)}
              >
                <div className="picker-item-name">{s.name}</div>
                <div className="picker-item-sub">{s.location}</div>
                {selectedSite?.id === s.id && <ChevronRight size={16} className="picker-item-arrow" />}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Vehicle type grid */}
      <div style={{ marginBottom: 28 }}>
        <div className="picker-section-title" style={{ marginBottom: 10 }}>
          <Truck size={16} /> Select Vehicle Type
        </div>
        <div className="vehicle-grid">
          {VEHICLES.map((v) => (
            <button
              key={v.id}
              className={`vehicle-tile ${selectedVehicle === v.id ? "vehicle-tile-active" : ""}`}
              onClick={() => setSelectedVehicle(v.id)}
            >
              <span className="vehicle-tile-emoji">{v.emoji}</span>
              <span className="vehicle-tile-name">{v.id}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="picker-actions">
        <button
          className="btn-primary"
          disabled={!selectedSite || !selectedVehicle}
          onClick={() => selectedSite && selectedVehicle && onStart(selectedSite, selectedVehicle)}
        >
          Start Inspection →
        </button>
      </div>
    </div>
  );
}
