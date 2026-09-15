"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Play, Square, Activity, ShieldCheck, ShieldAlert, Zap,
  HardHat, Shirt, HandMetal, Footprints, Settings,
  CheckCircle2, User, MapPin, LogOut, Loader2, ChevronLeft, Upload
} from "lucide-react";
import { clearToken, User as UserType, Site, Worker, WS_BASE, getMe } from "@/lib/api";
import LoginPage from "@/components/LoginPage";
import ModulePicker from "@/components/ModulePicker";
import SiteWorkerPicker from "@/components/SiteWorkerPicker";
import VehiclePicker from "@/components/VehiclePicker";
import VehicleScannerView from "@/components/VehicleScannerView";
import TestView from "@/components/TestView";

// ── types ──────────────────────────────────────────────────────────────────
type LiveItemStatus = "pass" | "fail" | "not_visible" | "no_person";
type PpeResult = Record<string, LiveItemStatus>;

const PPE_ITEMS = ["helmet", "vest", "gloves", "boots", "mask"] as const;

type View = "login" | "module" | "ppe-pick" | "ppe-scan" | "vehicle-pick" | "vehicle-scan" | "test-pick" | "test-take";

// ── helpers ────────────────────────────────────────────────────────────────
function getIcon(item: string) {
  switch (item) {
    case "helmet": return <HardHat size={20} />;
    case "vest":   return <Shirt size={20} />;
    case "gloves": return <HandMetal size={20} />;
    case "boots":  return <Footprints size={20} />;
    case "mask":   return <ShieldCheck size={20} />;
    default:       return <Settings size={20} />;
  }
}

function statusLabel(s: LiveItemStatus | undefined) {
  switch (s) {
    case "pass":        return { label: "PASS",        cls: "check-pass" };
    case "fail":        return { label: "FAIL",        cls: "check-fail" };
    case "not_visible": return { label: "NOT VISIBLE", cls: "check-amber" };
    case "no_person":   return { label: "NO PERSON",   cls: "check-pending" };
    default:            return { label: "WAITING",     cls: "check-pending" };
  }
}

// ── main component ─────────────────────────────────────────────────────────
export default function App() {
  const [view, setView]               = useState<View>("login");
  const [currentUser, setCurrentUser] = useState<UserType | null>(null);
  const [token, setToken]             = useState<string | null>(null);
  const [site, setSite]               = useState<Site | null>(null);
  const [worker, setWorker]           = useState<Worker | null>(null);
  const [vehicleType, setVehicleType] = useState<string | null>(null);

  // Restore session on mount
  useEffect(() => {
    const saved = localStorage.getItem("ppe_token");
    if (!saved) return;
    setToken(saved);
    getMe().then((u) => { setCurrentUser(u); setView("module"); }).catch(() => {
      clearToken(); setView("login");
    });
  }, []);

  function handleLogin(user: UserType, tok: string) {
    setCurrentUser(user); setToken(tok); setView("module");
  }

  function handleModuleSelect(module: "ppe" | "vehicle" | "test") {
    if (module === "ppe") setView("ppe-pick");
    else if (module === "vehicle") setView("vehicle-pick");
    else setView("test-pick");
  }

  function handleStartPpe(s: Site, w: Worker) {
    setSite(s); setWorker(w); setView("ppe-scan");
  }

  function handleStartVehicle(s: Site, vType: string) {
    setSite(s); setVehicleType(vType); setView("vehicle-scan");
  }

  function handleStartTest(s: Site, w: Worker) {
    setSite(s); setWorker(w); setView("test-take");
  }

  function handleLogout() {
    clearToken(); setCurrentUser(null); setToken(null); setView("login");
  }

  function handleScanDone() {
    setSite(null); setWorker(null); setVehicleType(null); setView("module");
  }

  return (
    <div>
      {view === "login" && <LoginPage onLogin={handleLogin} />}

      {view === "module" && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <ModulePicker onSelect={handleModuleSelect} />
        </main>
      )}

      {view === "ppe-pick" && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <div style={{ marginBottom: 12 }}>
            <button className="btn-ghost" onClick={() => setView("module")}>← Back to Modules</button>
          </div>
          <SiteWorkerPicker onStart={handleStartPpe} />
        </main>
      )}

      {view === "ppe-scan" && site && worker && token && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <ScannerView site={site} worker={worker} token={token} onDone={handleScanDone} />
        </main>
      )}

      {view === "vehicle-pick" && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <VehiclePicker onStart={handleStartVehicle} onBack={() => setView("module")} />
        </main>
      )}

      {view === "vehicle-scan" && site && vehicleType && token && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <VehicleScannerView site={site} vehicleType={vehicleType} token={token} onDone={handleScanDone} />
        </main>
      )}

      {view === "test-pick" && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <div style={{ marginBottom: 12 }}>
            <button className="btn-ghost" onClick={() => setView("module")}>← Back to Modules</button>
          </div>
          <SiteWorkerPicker onStart={handleStartTest} />
        </main>
      )}

      {view === "test-take" && site && worker && (
        <main className="app-container">
          <TopBar user={currentUser} onLogout={handleLogout} />
          <TestView site={site} worker={worker} onDone={handleScanDone} />
        </main>
      )}
    </div>
  );
}

// ── TopBar ─────────────────────────────────────────────────────────────────
function TopBar({ user, onLogout }: { user: UserType | null; onLogout: () => void }) {
  return (
    <div className="dashboard-header">
      <div className="title-group">
        <h1>Security &amp; Compliance</h1>
        <p>Real-time AI Inspection Dashboard</p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {user && (
          <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>
            <User size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
            {user.full_name || user.username}
          </span>
        )}
        <button className="btn-outline" onClick={onLogout}>
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </div>
  );
}

// ── ScannerView (PPE) ───────────────────────────────────────────────────────
function ScannerView({
  site, worker, token, onDone,
}: { site: Site; worker: Worker; token: string; onDone: () => void }) {
  const imgRef           = useRef<HTMLImageElement>(null);
  const fileInputRef     = useRef<HTMLInputElement>(null);
  const overlayRef       = useRef<HTMLCanvasElement>(null);
  const captureRef       = useRef<HTMLCanvasElement>(null);
  const wsRef            = useRef<WebSocket | null>(null);
  const pendingResolveRef = useRef<(() => void) | null>(null);
  const runningRef       = useRef(false);

  const [wsConnected, setWsConnected] = useState(false);
  const [scanning,    setScanning]    = useState(false);
  const [ppeResult,   setPpeResult]   = useState<PpeResult>({});
  const [latency,     setLatency]     = useState<number | null>(null);
  const [stable,      setStable]      = useState(false);
  const [overall,     setOverall]     = useState<"pass" | "fail" | null>(null);
  const [personIn,    setPersonIn]    = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [recording,   setRecording]   = useState(false);
  const [lastScan,    setLastScan]    = useState<{ overall: string; worker: string } | null>(null);

  // Open WebSocket with token in query string (browsers can't set WS headers)
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/scan?token=${token}`);
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
        setPersonIn(!!data.person);
        setPpeResult(data.items || {});
        setStable(data.stable || false);
        setOverall(data.overall);
        setLatency(data.latency_ms ?? null);

        if (pendingResolveRef.current) {
          pendingResolveRef.current();
          pendingResolveRef.current = null;
        }
      } else if (data.type === "recorded") {
        setLastScan({ overall: data.scan.overall, worker: data.scan.worker.full_name });
        setRecording(false);
        stopScanning();
      } else if (data.type === "error") {
        setError(data.message);
        setRecording(false);
        if (pendingResolveRef.current) { pendingResolveRef.current(); pendingResolveRef.current = null; }
      }
    };

    return () => { 
      ws.onerror = null;
      ws.onclose = null;
      ws.close(); 
    };
  }, [token]);

  function drawBoxes(data: any) {
    const overlay = overlayRef.current;
    const img     = imgRef.current;
    if (!overlay || !img || !data.frame_width) return;

    const rect = img.getBoundingClientRect();
    overlay.width  = rect.width;
    overlay.height = rect.height;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    const sx = overlay.width  / data.frame_width;
    const sy = overlay.height / data.frame_height;

    const drawBox = (x1: number, y1: number, x2: number, y2: number, color: string, label: string) => {
      ctx.strokeStyle = color; ctx.lineWidth = 3;
      ctx.strokeRect(x1 * sx, y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy);
      ctx.fillStyle = color;
      const tw = ctx.measureText(label).width;
      ctx.fillRect(x1 * sx, y1 * sy - 22, tw + 10, 22);
      ctx.fillStyle = "#fff"; ctx.font = "bold 13px sans-serif";
      ctx.fillText(label, x1 * sx + 5, y1 * sy - 5);
    };

    if (data.person) {
      const p = data.person;
      drawBox(p.x1, p.y1, p.x2, p.y2, "#3b82f6", `Person ${(p.confidence * 100).toFixed(0)}%`);
    }
    for (const d of (data.detections || [])) {
      drawBox(d.x1, d.y1, d.x2, d.y2, "#10b981", `${d.label} ${(d.confidence * 100).toFixed(0)}%`);
    }
  }

  const sendFrame = useCallback((): Promise<void> => {
    return new Promise((resolve) => {
      const img   = imgRef.current;
      const cap   = captureRef.current;
      const ws    = wsRef.current;
      if (!img || !cap || !ws || ws.readyState !== WebSocket.OPEN) { resolve(); return; }

      const MAX = 640;
      let w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
      if (w === 0 || h === 0) { resolve(); return; }
      
      if (w > MAX) { h = Math.round(h * MAX / w); w = MAX; }
      cap.width = w; cap.height = h;
      const ctx = cap.getContext("2d");
      if (!ctx) { resolve(); return; }
      ctx.drawImage(img, 0, 0, w, h);
      const imgData = cap.toDataURL("image/jpeg", 0.7);
      ws.send(JSON.stringify({ type: "frame", image: imgData }));

      pendingResolveRef.current = resolve;
      // timeout safety
      setTimeout(() => { if (pendingResolveRef.current === resolve) { pendingResolveRef.current = null; resolve(); } }, 3000);
    });
  }, []);

  const scanLoop = useCallback(async () => {
    while (runningRef.current) {
      await sendFrame();
      await new Promise(r => setTimeout(r, 50)); // tiny gap between frame/reply cycle
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
    setPpeResult({}); setStable(false); setOverall(null); setPersonIn(false);
    const overlay = overlayRef.current;
    if (overlay) { const ctx = overlay.getContext("2d"); ctx?.clearRect(0, 0, overlay.width, overlay.height); }
  }

  function recordResult() {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setRecording(true);
    wsRef.current.send(JSON.stringify({ type: "record", worker_id: worker.id, site_id: site.id }));
  }

  return (
    <div>
      {/* context bar */}
      <div className="context-bar">
        <button className="btn-ghost" onClick={() => { stopScanning(); onDone(); }}>
          <ChevronLeft size={16} /> Back
        </button>
        <span className="context-pill"><MapPin size={13} />{site.name}</span>
        <span className="context-pill"><User size={13} />{worker.full_name} · {worker.employee_code}</span>
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
            <div className="card-title"><Activity size={18} color="#3b82f6" />Image Inspection</div>
            <div className="controls">
              <input type="file" ref={fileInputRef} accept="image/*" style={{ display: "none" }} onChange={handleFileChange} />
              {!scanning
                ? <button className="btn-primary" onClick={handleUploadClick} disabled={!wsConnected}><Upload size={16} />Upload Photo</button>
                : <button className="btn-danger"  onClick={stopScanning}><Square size={16} />Stop</button>
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
                <p style={{ fontWeight: 700, fontSize: 20 }}>Scan Recorded — {lastScan.overall.toUpperCase()}</p>
                <p>{lastScan.worker}</p>
                <button className="btn-primary" style={{ marginTop: 8, background: "white", color: "#111" }} onClick={() => { setLastScan(null); onDone(); }}>
                  Scan Next Worker
                </button>
              </div>
            )}
            {error && (
              <div className="video-overlay" style={{ background: "rgba(220,38,38,0.85)" }}>
                <ShieldAlert size={40} />
                <p style={{ textAlign: "center", maxWidth: 320 }}>{error}</p>
                <button className="btn-primary" style={{ marginTop: 8, background: "white", color: "#111" }} onClick={() => setError(null)}>Dismiss</button>
              </div>
            )}
          </div>

          <div className="card-header" style={{ borderTop: "1px solid var(--border)", borderBottom: "none" }}>
            <div className="stats-bar" style={{ margin: 0 }}>
              <div className="stat-item"><Zap size={13} color="#f59e0b" />Latency: {latency !== null ? `${latency}ms` : "--"}</div>
              <div className="stat-item" style={{ color: personIn ? "var(--success)" : undefined }}>
                <User size={13} />{personIn ? "Person detected" : "No person"}
              </div>
              <div className="stat-item" style={{ color: stable ? "var(--success)" : undefined }}>
                <CheckCircle2 size={13} />{stable ? "Stable — ready" : "Not stable"}
              </div>
            </div>
          </div>
        </div>

        {/* Checklist */}
        <div className="card">
          <div className="card-header" style={{ justifyContent: "space-between" }}>
            <div className="card-title"><ShieldCheck size={18} color="#10b981" />PPE Checklist</div>
            {stable && !recording && (
              <button className="btn-primary" style={{ background: "#10b981", padding: "8px 14px", fontSize: 13 }} onClick={recordResult}>
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
              {PPE_ITEMS.map((item) => {
                const { label, cls } = statusLabel(ppeResult[item]);
                return (
                  <div key={item} className={`check-item ${cls}`}>
                    <div className="check-item-info">
                      <div className="check-item-icon">{getIcon(item)}</div>
                      <div className="check-item-name">{item}</div>
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
              <strong>Flow:</strong> Point the camera at the worker until the checklist stabilises. Then click <strong>Record Result</strong> to save the scan.
            </div>
          </div>
        </div>
      </div>

      <canvas ref={captureRef} style={{ display: "none" }} />
    </div>
  );
}
