"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Play, Square, Activity, ShieldCheck, ShieldAlert, Zap,
  Lightbulb, Disc, ScanLine, Eye, Flame, Radio, Bell, Wrench,
  CheckCircle2, MapPin, Truck, LogOut, Loader2, ChevronLeft, Upload,
  Box, HandMetal
} from "lucide-react";
import { Site, WS_BASE } from "@/lib/api";

type ItemStatus = "pass" | "fail" | "not_visible" | "no_vehicle" | "no_tool";

const VEHICLE_ITEMS = [
  "lights", "tires", "mirrors", "windshield",
  "fire_extinguisher", "beacon", "reverse_alarm", "body_condition",
];

const TOOL_ITEMS = [
  "casing", "cords", "guards", "switches", "handles", "overall_condition"
];

function getRelevantItems(category: "vehicle" | "tool", type: string): string[] {
  if (category === "vehicle") {
    const lookup: Record<string, string[]> = {
      "Excavator": ["body_condition", "lights", "mirrors", "fire_extinguisher", "beacon"],
      "Dump Truck": ["body_condition", "tires", "lights", "mirrors", "windshield", "fire_extinguisher", "beacon", "reverse_alarm"],
      "Articulated Hauler": ["body_condition", "tires", "lights", "mirrors", "windshield", "fire_extinguisher", "beacon", "reverse_alarm"],
      "Bulldozer": ["body_condition", "lights", "mirrors", "fire_extinguisher", "beacon"],
      "Wheel Loader": ["body_condition", "tires", "lights", "mirrors", "windshield", "fire_extinguisher", "beacon", "reverse_alarm"],
      "Motor Grader": ["body_condition", "tires", "lights", "mirrors", "windshield", "fire_extinguisher", "beacon", "reverse_alarm"],
      "Water Truck": ["body_condition", "tires", "lights", "mirrors", "windshield", "fire_extinguisher", "beacon", "reverse_alarm"],
      "Drill Rig": ["body_condition", "lights", "fire_extinguisher", "beacon"],
    };
    return lookup[type] || VEHICLE_ITEMS;
  } else {
    const lookup: Record<string, string[]> = {
      "Jackhammer": ["overall_condition", "casing", "cords", "switches", "handles"],
      "Angle Grinder": ["overall_condition", "casing", "cords", "guards", "switches", "handles"],
      "Power Drill": ["overall_condition", "casing", "cords", "switches", "handles"],
      "Water Pump": ["overall_condition", "casing", "cords", "guards"],
      "Generator": ["overall_condition", "casing", "cords", "guards", "switches"],
      "Welding Machine": ["overall_condition", "casing", "cords", "switches", "handles"],
      "Air Compressor": ["overall_condition", "casing", "cords", "guards", "switches"],
    };
    return lookup[type] || TOOL_ITEMS;
  }
}

function getIcon(item: string) {
  switch (item) {
    case "lights":           return <Lightbulb size={18} />;
    case "tires":            return <Disc size={18} />;
    case "mirrors":          return <ScanLine size={18} />;
    case "windshield":       return <Eye size={18} />;
    case "fire_extinguisher": return <Flame size={18} />;
    case "beacon":           return <Radio size={18} />;
    case "reverse_alarm":    return <Bell size={18} />;
    case "body_condition":   return <Wrench size={18} />;
    case "casing":           return <Box size={18} />;
    case "cords":            return <Zap size={18} />;
    case "guards":           return <ShieldAlert size={18} />;
    case "switches":         return <Radio size={18} />;
    case "handles":          return <HandMetal size={18} />;
    case "overall_condition": return <Activity size={18} />;
    default:                 return <CheckCircle2 size={18} />;
  }
}

function itemLabel(item: string) {
  return item.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function statusLabel(s: ItemStatus | undefined) {
  switch (s) {
    case "pass":        return { label: "PASS",       cls: "check-pass" };
    case "fail":        return { label: "FAIL",       cls: "check-fail" };
    case "not_visible": return { label: "NOT VISIBLE", cls: "check-amber" };
    case "no_vehicle":  return { label: "NO VEHICLE", cls: "check-pending" };
    case "no_tool":     return { label: "NO TOOL",    cls: "check-pending" };
    default:            return { label: "WAITING",    cls: "check-pending" };
  }
}

interface Props {
  site: Site;
  category: "vehicle" | "tool";
  machineryType: string;
  token: string;
  onDone: () => void;
}

export default function MachineryScannerView({ site, category, machineryType, token, onDone }: Props) {
  const imgRef        = useRef<HTMLImageElement>(null);
  const fileInputRef  = useRef<HTMLInputElement>(null);
  const overlayRef    = useRef<HTMLCanvasElement>(null);
  const captureRef    = useRef<HTMLCanvasElement>(null);
  const wsRef         = useRef<WebSocket | null>(null);
  const pendingRef  = useRef<(() => void) | null>(null);
  const runningRef  = useRef(false);

  const [wsConnected, setWsConnected] = useState(false);
  const [scanning,    setScanning]    = useState(false);
  const [items,       setItems]       = useState<Record<string, ItemStatus>>({});
  const [latency,     setLatency]     = useState<number | null>(null);
  const [stable,      setStable]      = useState(false);
  const [overall,     setOverall]     = useState<"pass" | "fail" | null>(null);
  const [recording,   setRecording]   = useState(false);
  const [lastScan,    setLastScan]    = useState<{ overall: string; vehicle: string } | null>(null);
  const [error,       setError]       = useState<string | null>(null);

  // ── WebSocket ────────────────────────────────────────────────
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/${category}-scan?token=${token}`);
    wsRef.current = ws;
    ws.onopen  = () => setWsConnected(true);
    ws.onclose = (e) => {
      setWsConnected(false);
      if (e.code === 4401) setError("Session expired. Please sign in again.");
    };
    ws.onerror = () => setError("Cannot reach backend WebSocket");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "detection") {
        drawBoxes(data);
        setItems(data.items || {});
        setStable(data.stable || false);
        setOverall(data.overall);
        setLatency(data.latency_ms ?? null);
        if (pendingRef.current) { pendingRef.current(); pendingRef.current = null; }
      } else if (data.type === "recorded") {
        setLastScan({ overall: data.scan.overall, vehicle: data.scan.vehicle_type || data.scan.tool_type });
        setRecording(false);
        stopScanning();
      } else if (data.type === "error") {
        setError(data.message);
        setRecording(false);
        if (pendingRef.current) { pendingRef.current(); pendingRef.current = null; }
      }
    };
    return () => { 
      ws.onerror = null;
      ws.onclose = null;
      ws.close(); 
    };
  }, [token, category]);

  // ── bounding-box overlay ──────────────────────────────────────
  function drawBoxes(data: any) {
    const overlay = overlayRef.current;
    const img     = imgRef.current;
    if (!overlay || !img || !data.frame_width) return;
    const rect = img.getBoundingClientRect();
    overlay.width = rect.width; overlay.height = rect.height;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const sx = overlay.width / data.frame_width;
    const sy = overlay.height / data.frame_height;
    const draw = (x1: number, y1: number, x2: number, y2: number, color: string, lbl: string) => {
      ctx.strokeStyle = color; ctx.lineWidth = 3;
      ctx.strokeRect(x1 * sx, y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy);
      ctx.fillStyle = color;
      const tw = ctx.measureText(lbl).width;
      ctx.fillRect(x1 * sx, y1 * sy - 22, tw + 10, 22);
      ctx.fillStyle = "#fff"; ctx.font = "bold 13px sans-serif";
      ctx.fillText(lbl, x1 * sx + 5, y1 * sy - 5);
    };
    for (const d of (data.detections || [])) {
      draw(d.x1, d.y1, d.x2, d.y2, "#f59e0b", `${d.label} ${(d.confidence * 100).toFixed(0)}%`);
    }
  }

  // ── frame loop ────────────────────────────────────────────────
  const sendFrame = useCallback((): Promise<void> => {
    return new Promise((resolve) => {
      const img = imgRef.current, cap = captureRef.current, ws = wsRef.current;
      if (!img || !cap || !ws || ws.readyState !== WebSocket.OPEN) { resolve(); return; }
      const MAX = 640;
      let w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
      if (w === 0 || h === 0) { resolve(); return; }
      if (w > MAX) { h = Math.round(h * MAX / w); w = MAX; }
      cap.width = w; cap.height = h;
      const ctx = cap.getContext("2d");
      if (!ctx) { resolve(); return; }
      ctx.drawImage(img, 0, 0, w, h);
      ws.send(JSON.stringify({ type: "frame", image: cap.toDataURL("image/jpeg", 0.7) }));
      pendingRef.current = resolve;
      setTimeout(() => { if (pendingRef.current === resolve) { pendingRef.current = null; resolve(); } }, 3000);
    });
  }, []);

  const scanLoop = useCallback(async () => {
    while (runningRef.current) {
      await sendFrame();
      await new Promise(r => setTimeout(r, 50));
    }
  }, [sendFrame]);

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null); setLastScan(null);
    
    const url = URL.createObjectURL(file);
    if (imgRef.current) imgRef.current.src = url;
    
    wsRef.current?.send(JSON.stringify({ type: "reset" }));
    runningRef.current = true;
    setScanning(true);
    scanLoop();
  }

  function stopScanning() {
    runningRef.current = false;
    setScanning(false);
    if (imgRef.current && imgRef.current.src) {
      URL.revokeObjectURL(imgRef.current.src);
      imgRef.current.src = "";
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
    setItems({}); setStable(false); setOverall(null);
    const overlay = overlayRef.current;
    if (overlay) { overlay.getContext("2d")?.clearRect(0, 0, overlay.width, overlay.height); }
  }

  function recordResult() {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setRecording(true);
    const key = category === "vehicle" ? "vehicle_type" : "tool_type";
    wsRef.current.send(JSON.stringify({ type: "record", [key]: machineryType, site_id: site.id }));
  }

  return (
    <div>
      {/* context bar */}
      <div className="context-bar">
        <button className="btn-ghost" onClick={() => { stopScanning(); onDone(); }}>
          <ChevronLeft size={16} /> Back
        </button>
        <span className="context-pill"><MapPin size={13} />{site.name}</span>
        <span className="context-pill">{category === "vehicle" ? <Truck size={13} /> : <Wrench size={13} />}{machineryType}</span>
        <div style={{ marginLeft: "auto" }}>
          <span className={`status-badge ${wsConnected ? "status-connected" : "status-disconnected"}`}>
            <span className="status-indicator" />
            {wsConnected ? "Backend Online" : "Backend Offline"}
          </span>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Camera */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Activity size={18} color="#f59e0b" />Live Feed</div>
            <div className="controls">
              <input type="file" ref={fileInputRef} accept="image/*" style={{ display: "none" }} onChange={handleFileChange} />
              {!scanning
                ? <button className="btn-primary" onClick={handleUploadClick} disabled={!wsConnected}
                    style={{ background: "#f59e0b" }}><Upload size={16} />Upload Photo</button>
                : <button className="btn-danger" onClick={stopScanning}><Square size={16} />Stop</button>
              }
            </div>
          </div>

          <div className="video-container">
            <img ref={imgRef} style={{ width: "100%", height: "100%", objectFit: "contain" }} alt="" />
            <canvas ref={overlayRef} style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }} />
            {!scanning && !lastScan && (
              <div className="video-overlay">
                <Upload size={48} opacity={0.4} />
                <p>Upload a photo to begin inspection.</p>
              </div>
            )}
            {lastScan && !scanning && (
              <div className="video-overlay" style={{ background: lastScan.overall === "pass" ? "rgba(16,185,129,0.85)" : "rgba(239,68,68,0.85)" }}>
                {lastScan.overall === "pass" ? <ShieldCheck size={48} /> : <ShieldAlert size={48} />}
                <p style={{ fontWeight: 700, fontSize: 20 }}>Inspection Recorded — {lastScan.overall.toUpperCase()}</p>
                <p>{lastScan.vehicle}</p>
                <button className="btn-primary" style={{ marginTop: 8, background: "white", color: "#111" }}
                  onClick={() => { setLastScan(null); onDone(); }}>
                  Inspect Next {category === "vehicle" ? "Vehicle" : "Tool"}
                </button>
              </div>
            )}
            {error && (
              <div className="video-overlay" style={{ background: "rgba(220,38,38,0.85)" }}>
                <ShieldAlert size={40} />
                <p style={{ textAlign: "center", maxWidth: 320 }}>{error}</p>
                <button className="btn-primary" style={{ marginTop: 8, background: "white", color: "#111" }}
                  onClick={() => setError(null)}>Dismiss</button>
              </div>
            )}
          </div>

          <div className="card-header" style={{ borderTop: "1px solid var(--border)", borderBottom: "none" }}>
            <div className="stats-bar" style={{ margin: 0 }}>
              <div className="stat-item"><Zap size={13} color="#f59e0b" />Latency: {latency !== null ? `${latency}ms` : "--"}</div>
              <div className="stat-item" style={{ color: stable ? "var(--success)" : undefined }}>
                <CheckCircle2 size={13} />{stable ? "Stable — ready" : "Not stable"}
              </div>
            </div>
          </div>
        </div>

        {/* Checklist */}
        <div className="card">
          <div className="card-header" style={{ justifyContent: "space-between" }}>
            <div className="card-title"><ShieldCheck size={18} color="#f59e0b" />Inspection Checklist</div>
            {stable && !recording && (
              <button className="btn-primary" style={{ background: "#f59e0b", padding: "8px 14px", fontSize: 13 }}
                onClick={recordResult}>
                <CheckCircle2 size={15} />Record Result
              </button>
            )}
            {recording && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-secondary)" }}>
                <Loader2 size={15} className="spin" />Saving…
              </div>
            )}
          </div>

          <div className="results-container">
            <div className="results-grid">
              {getRelevantItems(category, machineryType).map((item) => {
                const status = scanning ? (items[item] || (category === "vehicle" ? "no_vehicle" : "no_tool")) : undefined;
                const { label, cls } = statusLabel(status);
                return (
                  <div key={item} className={`check-item ${cls}`}>
                    <div className="check-item-info">
                      <div className="check-item-icon">{getIcon(item)}</div>
                      <div className="check-item-name">{itemLabel(item)}</div>
                    </div>
                    <div className="check-item-status">{label}</div>
                  </div>
                );
              })}
            </div>

            {overall && (
              <div className={`overall-banner ${overall === "pass" ? "overall-pass" : "overall-fail"}`}>
                {overall === "pass" ? <ShieldCheck size={22} /> : <ShieldAlert size={22} />}
                OVERALL {overall.toUpperCase()}
              </div>
            )}

            <div className="disclaimer">
              <strong>Flow:</strong> Upload a photo of the {category === "vehicle" ? "vehicle" : "tool"} until the checklist stabilises.
              Then click <strong>Record Result</strong> to save the inspection.
            </div>
          </div>
        </div>
      </div>

      <canvas ref={captureRef} style={{ display: "none" }} />
    </div>
  );
}
