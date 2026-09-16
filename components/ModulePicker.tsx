"use client";

import { ShieldCheck, Truck, ClipboardCheck } from "lucide-react";

interface Props {
  onSelect: (module: "ppe" | "vehicle" | "test-hot" | "test-cold") => void;
}

export default function ModulePicker({ onSelect }: Props) {
  return (
    <div className="module-picker-wrap">
      <div className="module-picker-header">
        <h2>Inspection Dashboard</h2>
        <p>Choose an inspection module to begin</p>
      </div>
      <div className="module-picker-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
        {/* PPE Inspection */}
        <button
          id="module-ppe"
          className="module-card"
          onClick={() => onSelect("ppe")}
        >
          <div className="module-card-icon module-card-icon--blue">
            <ShieldCheck size={36} />
          </div>
          <div className="module-card-body">
            <div className="module-card-title">PPE Inspection</div>
            <div className="module-card-desc">
              Scan workers for Personal Protective Equipment compliance — helmet, vest, gloves, boots &amp; mask.
            </div>
            <div className="module-card-pills">
              <span className="module-pill">Helmet</span>
              <span className="module-pill">Vest</span>
              <span className="module-pill">Gloves</span>
              <span className="module-pill">Boots</span>
              <span className="module-pill">Mask</span>
            </div>
          </div>
          <div className="module-card-arrow">→</div>
        </button>

        {/* Machinery Inspection */}
        <button
          id="module-vehicle"
          className="module-card"
          onClick={() => onSelect("vehicle")}
        >
          <div className="module-card-icon module-card-icon--amber">
            <Truck size={36} />
          </div>
          <div className="module-card-body">
            <div className="module-card-title">Machinery Inspection</div>
            <div className="module-card-desc">
              Camera-scan heavy vehicles and mining tools for safety compliance.
            </div>
            <div className="module-card-pills">
              <span className="module-pill">Dump Truck</span>
              <span className="module-pill">Excavator</span>
              <span className="module-pill">Jackhammer</span>
              <span className="module-pill">Generator</span>
              <span className="module-pill">+16 more</span>
            </div>
          </div>
          <div className="module-card-arrow">→</div>
        </button>
        
        {/* Hot Work Permit Test */}
        <button
          id="module-test-hot"
          className="module-card"
          onClick={() => onSelect("test-hot")}
        >
          <div className="module-card-icon" style={{ background: "linear-gradient(135deg, #ef4444, #dc2626)", boxShadow: "0 4px 14px rgba(239,68,68,.35)" }}>
            <ClipboardCheck size={36} />
          </div>
          <div className="module-card-body">
            <div className="module-card-title">Hot Work Permit Test</div>
            <div className="module-card-desc">
              Conduct a 50-question test covering Hot Work rules and hazards.
            </div>
            <div className="module-card-pills">
              <span className="module-pill">50 Questions</span>
              <span className="module-pill">Pass: 33%</span>
            </div>
          </div>
          <div className="module-card-arrow">→</div>
        </button>

        {/* Cold Work Permit Test */}
        <button
          id="module-test-cold"
          className="module-card"
          onClick={() => onSelect("test-cold")}
        >
          <div className="module-card-icon" style={{ background: "linear-gradient(135deg, #10b981, #059669)", boxShadow: "0 4px 14px rgba(16,185,129,.35)" }}>
            <ClipboardCheck size={36} />
          </div>
          <div className="module-card-body">
            <div className="module-card-title">Cold Work Permit Test</div>
            <div className="module-card-desc">
              Conduct a 50-question test covering Cold Work rules and hazards.
            </div>
            <div className="module-card-pills">
              <span className="module-pill">50 Questions</span>
              <span className="module-pill">Pass: 33%</span>
            </div>
          </div>
          <div className="module-card-arrow">→</div>
        </button>
      </div>
    </div>
  );
}
