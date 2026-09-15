"use client";

import { useEffect, useState } from "react";
import { getWorkers, getSites, Site, Worker } from "@/lib/api";
import { MapPin, User, ChevronRight, Loader2 } from "lucide-react";

interface Props {
  onStart: (site: Site, worker: Worker) => void;
}

export default function SiteWorkerPicker({ onStart }: Props) {
  const [sites, setSites] = useState<Site[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [selectedSite, setSelectedSite] = useState<Site | null>(null);
  const [selectedWorker, setSelectedWorker] = useState<Worker | null>(null);
  const [loadingSites, setLoadingSites] = useState(true);
  const [loadingWorkers, setLoadingWorkers] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSites()
      .then(setSites)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingSites(false));
  }, []);

  async function handleSiteSelect(site: Site) {
    setSelectedSite(site);
    setSelectedWorker(null);
    setWorkers([]);
    setLoadingWorkers(true);
    try {
      const ws = await getWorkers(site.id);
      setWorkers(ws);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingWorkers(false);
    }
  }

  return (
    <div className="picker-container">
      <div className="picker-header">
        <h2>Start New Scan</h2>
        <p>Select a site and worker to begin the PPE compliance check</p>
      </div>

      {error && <div className="picker-error">{error}</div>}

      <div className="picker-grid">
        {/* Sites */}
        <div className="picker-section">
          <div className="picker-section-title">
            <MapPin size={16} />
            Select Site
          </div>
          {loadingSites ? (
            <div className="picker-loading"><Loader2 size={20} className="spin" /> Loading sites…</div>
          ) : sites.length === 0 ? (
            <div className="picker-empty">No active sites found. Ask an admin to create one.</div>
          ) : (
            <div className="picker-list">
              {sites.map((s) => (
                <button
                  key={s.id}
                  className={`picker-item ${selectedSite?.id === s.id ? "picker-item-active" : ""}`}
                  onClick={() => handleSiteSelect(s)}
                >
                  <div className="picker-item-name">{s.name}</div>
                  <div className="picker-item-sub">{s.location}</div>
                  {selectedSite?.id === s.id && <ChevronRight size={16} className="picker-item-arrow" />}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Workers */}
        <div className="picker-section">
          <div className="picker-section-title">
            <User size={16} />
            Select Worker
          </div>
          {!selectedSite ? (
            <div className="picker-empty">Select a site first</div>
          ) : loadingWorkers ? (
            <div className="picker-loading"><Loader2 size={20} className="spin" /> Loading workers…</div>
          ) : workers.length === 0 ? (
            <div className="picker-empty">No active workers at this site</div>
          ) : (
            <div className="picker-list">
              {workers.map((w) => (
                <button
                  key={w.id}
                  className={`picker-item ${selectedWorker?.id === w.id ? "picker-item-active" : ""}`}
                  onClick={() => setSelectedWorker(w)}
                >
                  <div className="picker-item-name">{w.full_name}</div>
                  <div className="picker-item-sub">{w.employee_code} · {w.trade}</div>
                  {selectedWorker?.id === w.id && <ChevronRight size={16} className="picker-item-arrow" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="picker-actions">
        <button
          className="btn-primary"
          disabled={!selectedSite || !selectedWorker}
          onClick={() => selectedSite && selectedWorker && onStart(selectedSite, selectedWorker)}
        >
          Start Scan →
        </button>
      </div>
    </div>
  );
}
