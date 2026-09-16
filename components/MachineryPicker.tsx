"use client";

import { useEffect, useState } from "react";
import { getSites, Site } from "@/lib/api";
import { 
  MapPin, Truck, Wrench, Loader2, ChevronRight,
  Hammer, Settings, Droplet, Zap, Flame, Wind, Disc, PenTool, Pickaxe, Drill
} from "lucide-react";

const VEHICLES = [
  { id: "Dump Truck",              icon: Truck },
  { id: "Articulated Hauler",      icon: Truck },
  { id: "Excavator",               icon: Truck },
  { id: "Bulldozer",               icon: Truck },
  { id: "Wheel Loader",            icon: Settings },
  { id: "Motor Grader",            icon: Settings },
  { id: "Water Truck",             icon: Droplet },
  { id: "Scraper",                 icon: Wrench },
  { id: "Drill Rig",               icon: Hammer },
  { id: "Continuous Miner",        icon: Hammer },
  { id: "Scoop Tram",              icon: Truck },
  { id: "Underground Haul Truck",  icon: Truck },
];

const TOOLS = [
  { id: "Jackhammer",              icon: Hammer },
  { id: "Power Drill",             icon: Wrench },
  { id: "Angle Grinder",           icon: Disc },
  { id: "Concrete Crusher",        icon: Settings },
  { id: "Water Pump",              icon: Droplet },
  { id: "Generator",               icon: Zap },
  { id: "Welding Machine",         icon: Flame },
  { id: "Air Compressor",          icon: Wind },
];

interface Props {
  onStart: (site: Site, category: "vehicle" | "tool", machineryType: string) => void;
  onBack: () => void;
}

export default function MachineryPicker({ onStart, onBack }: Props) {
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSite, setSelectedSite] = useState<Site | null>(null);
  const [category, setCategory] = useState<"vehicle" | "tool">("vehicle");
  const [selectedMachinery, setSelectedMachinery] = useState<string | null>(null);
  const [loadingSites, setLoadingSites] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSites()
      .then(setSites)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingSites(false));
  }, []);

  const items = category === "vehicle" ? VEHICLES : TOOLS;

  return (
    <div className="picker-container">
      <div className="picker-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h2>Machinery Inspection</h2>
          <p>Select a site and machinery type to begin the inspection</p>
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

      {/* Machinery Category Tabs */}
      <div style={{ marginBottom: 24, display: "flex", gap: 12 }}>
        <button
          className={`btn-${category === "vehicle" ? "primary" : "ghost"}`}
          onClick={() => { setCategory("vehicle"); setSelectedMachinery(null); }}
          style={{ flex: 1, justifyContent: "center" }}
        >
          <Truck size={16} /> Vehicles
        </button>
        <button
          className={`btn-${category === "tool" ? "primary" : "ghost"}`}
          onClick={() => { setCategory("tool"); setSelectedMachinery(null); }}
          style={{ flex: 1, justifyContent: "center", background: category === "tool" ? "#f59e0b" : undefined }}
        >
          <Wrench size={16} /> Tools
        </button>
      </div>

      {/* Machinery type grid */}
      <div style={{ marginBottom: 28 }}>
        <div className="picker-section-title" style={{ marginBottom: 10 }}>
          {category === "vehicle" ? <Truck size={16} /> : <Wrench size={16} />} Select {category === "vehicle" ? "Vehicle" : "Tool"} Type
        </div>
        <div className="vehicle-grid">
          {items.map((v) => {
            const Icon = v.icon;
            return (
              <button
                key={v.id}
                className={`vehicle-tile ${selectedMachinery === v.id ? "vehicle-tile-active" : ""}`}
                onClick={() => setSelectedMachinery(v.id)}
              >
                <span className="vehicle-tile-emoji" style={{ fontSize: 24, marginBottom: 8 }}><Icon size={28} strokeWidth={1.5} color="#3b82f6" /></span>
                <span className="vehicle-tile-name">{v.id}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="picker-actions">
        <button
          className="btn-primary"
          disabled={!selectedSite || !selectedMachinery}
          onClick={() => selectedSite && selectedMachinery && onStart(selectedSite, category, selectedMachinery)}
        >
          Start Inspection →
        </button>
      </div>
    </div>
  );
}
