"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Play, Square, Activity, ShieldCheck, ShieldAlert, Zap,
  Lightbulb, Disc, ScanLine, Eye, Flame, Radio, Bell, Wrench,
  CheckCircle2, MapPin, Truck, LogOut, Loader2, ChevronLeft
} from "lucide-react";
import { Site, WS_BASE } from "@/lib/api";

type ItemStatus = "pass" | "fail" | "not_visible" | "no_vehicle";

const VEHICLE_ITEMS = [
  "lights", "tires", "mirrors", "windshield",
  "fire_extinguisher", "beacon", "reverse_alarm", "body_condition",
] as const;

function getVehicleIcon(item: string) {
  switch (item) {
    case "lights":           return <Lightbulb size={18} />;
    case "tires":            return <Disc size={18} />;
    case "mirrors":          return <ScanLine size={18} />;
    case "windshield":       return <Eye size={18} />;
    case "fire_extinguisher": return <Flame size={18} />;
    case "beacon":           return <Radio size={18} />;
    case "reverse_alarm":    return <Bell size={18} />;
    case "body_condition":   return <Wrench size={18} />;
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
    default:            return { label: "WAITING",    cls: "check-pending" };
  }
}

interface Props {
  site: Site;
  vehicleType: string;
  token: string;
  onDone: () => void;
}

export default function VehicleScannerView({ site, vehicleType, token, onDone }: Props) {
  const videoRef    = useRef<HTMLVideoElement>(null);
  const overlayRef  = useRef<HTMLCanvasElement>(null);
  const captureRef  = useRef<HTMLCanvasElement>(null);
  const wsRef       = useRef<WebSocket | null>(null);
  const streamRef   = useRef<MediaStream | null>(null);
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
    const ws = new WebSocket(`${WS_BASE}/ws/vehicle-scan?token=${token}`);
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
        setLastScan({ overall: data.scan.overall, vehicle: data.scan.vehicle_type });
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
  }, [token]);

  // ── bounding-box overlay ──────────────────────────────────────
  function drawBoxes(data: any) {
    const overlay = overlayRef.current;
    const video   = videoRef.current;
    if (!overlay || !video || !data.frame_width) return;
    const rect = video.getBoundingClientRect();
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
      const video = videoRef.current, cap = captureRef.current, ws = wsRef.current;
      if (!video || !cap || !ws || ws.readyState !== WebSocket.OPEN) { resolve(); return; }
      const MAX = 640;
      let w = video.videoWidth, h = video.videoHeight;
      if (w > MAX) { h = Math.round(h * MAX / w); w = MAX; }
      cap.width = w; cap.height = h;
      const ctx = cap.getContext("2d");
      if (!ctx) { resolve(); return; }
      ctx.drawImage(video, 0, 0, w, h);
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

  async function startScanning() {
    setError(null); setLastScan(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 640 } }, audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      wsRef.current?.send(JSON.stringify({ type: "reset" }));
      runningRef.current = true;
      setScanning(true);
      scanLoop();
    } catch (err) { setError("Camera access failed: " + (err as Error).message); }
  }

  function stopScanning() {
    runningRef.current = false;
    setScanning(false);
    streamRef.current?.getTracks().forEach(t => t.stop());
    setItems({}); setStable(false); setOverall(null);
    const overlay = overlayRef.current;
    if (overlay) { overlay.getContext("2d")?.clearRect(0, 0, overlay.width, overlay.height); }
  }

  function recordResult() {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setRecording(true);
    wsRef.current.send(JSON.stringify({ type: "record", vehicle_type: vehicleType, site_id: site.id }));
  }

  return (
    <div>
      {/* context bar */}
      <div className="context-bar">
        <button className="btn-ghost" onClick={() => { stopScanning(); onDone(); }}>
          <ChevronLeft size={16} /> Back
        </button>
        <span className="context-pill"><MapPin size={13} />{site.name}</span>
        <span className="context-pill"><Truck size={13} />{vehicleType}</span>
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
              {!scanning
                ? <button className="btn-primary" onClick={startScanning} disabled={!wsConnected}
                    style={{ background: "#f59e0b" }}><Play size={16} />Start Scan</button>
                : <button className="btn-danger" onClick={stopScanning}><Square size={16} />Stop</button>
              }
            </div>
          </div>

          <div className="video-container">
            <video ref={videoRef} muted playsInline />
            <canvas ref={overlayRef} style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }} />
            {!scanning && !lastScan && (
              <div className="video-overlay">
                <Truck size={48} opacity={0.4} />
                <p>Camera offline. Press Start Scan.</p>
              </div>
            )}
            {lastScan && !scanning && (
              <div className="video-overlay" style={{ background: lastScan.overall === "pass" ? "rgba(16,185,129,0.85)" : "rgba(239,68,68,0.85)" }}>
                {lastScan.overall === "pass" ? <ShieldCheck size={48} /> : <ShieldAlert size={48} />}
                <p style={{ fontWeight: 700, fontSize: 20 }}>Inspection Recorded — {lastScan.overall.toUpperCase()}</p>
                <p>{lastScan.vehicle}</p>
                <button className="btn-primary" style={{ marginTop: 8, background: "white", color: "#111" }}
                  onClick={() => { setLastScan(null); onDone(); }}>
                  Inspect Next Vehicle
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
              {VEHICLE_ITEMS.map((item) => {
                const { label, cls } = statusLabel(items[item] as ItemStatus);
                return (
                  <div key={item} className={`check-item ${cls}`}>
                    <div className="check-item-info">
                      <div className="check-item-icon">{getVehicleIcon(item)}</div>
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
              <strong>Flow:</strong> Point the camera at the vehicle until the checklist stabilises.
              Then click <strong>Record Result</strong> to save the inspection.
            </div>
          </div>
        </div>
      </div>

      <canvas ref={captureRef} style={{ display: "none" }} />
    </div>
  );
}
