# PPE Scanner — API Contract (frontend ⇄ backend)

This is the agreement between the **frontend** (Next.js, built in Antigravity) and the
**backend** (FastAPI, built in Claude Code). Build the UI against this document.
If the UI needs something that isn't here, ask for it to be added — don't edit `backend/`.

## Folder ownership

| Folder / file | Owner |
|---|---|
| `app/`, `components/`, `lib/`, `public/`, `package.json`, styles, `.env.local` | Frontend (Antigravity) |
| `backend/`, `API_CONTRACT.md` | Backend (Claude Code) |

Only run **one** `npm run dev` for this folder at a time (two copies fight over `.next/`).

## Basics

- Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
- WebSocket URL: same host, `ws://` (or `wss://`) + `/ws/scan`
- All REST bodies are JSON. All timestamps are ISO-8601 UTC strings, e.g. `"2026-09-14T11:24:58Z"`.
- Auth: send `Authorization: Bearer <access_token>` on every request except login.
- Errors: `{"detail": "message"}`. `401` → send user to `/login`. `403` → "no permission". `422` → validation error.
- Sites, workers and users return a plain JSON array.
- Scans and violations are paginated: `?limit=` (default 50, max 500) and `?offset=`; response `{"items": [...], "total": n}`.
- Dates in filters (`date_from`, `date_to`) and `by_day` dates are calendar days in the server's timezone
  (`APP_TIMEZONE`, defaults to the server machine's local time). Timestamps are always UTC.

## Roles

| Action | admin | supervisor |
|---|---|---|
| Run scans | ✅ any site | ✅ own site only |
| View scans / violations / reports | ✅ all sites | ✅ own site only (server filters automatically) |
| Resolve violations | ✅ | ✅ own site |
| Manage workers | ✅ | ❌ (view only, own site) |
| Manage sites and users | ✅ | ❌ |

## Shared types

```ts
type Role = "admin" | "supervisor";
type ItemStatus = "pass" | "fail" | "not_visible";      // saved scans
type LiveItemStatus = ItemStatus | "no_person";          // live WebSocket only
type PpeItem = "helmet" | "vest" | "gloves" | "boots" | "mask";

interface User {
  id: number; username: string; full_name: string;
  role: Role; site_id: number | null; is_active: boolean; created_at: string;
}
interface Site { id: number; name: string; location: string; is_active: boolean; created_at: string; }
interface Worker {
  id: number; employee_code: string; full_name: string; trade: string;
  site_id: number; is_active: boolean; created_at: string;
}
interface Scan {
  id: number;
  created_at: string;
  worker: { id: number; full_name: string; employee_code: string };
  site: { id: number; name: string };
  scanned_by: { id: number; username: string; full_name: string };
  items: Record<PpeItem, ItemStatus>;
  overall: "pass" | "fail";          // pass only if all 5 items are "pass"
  has_snapshot: boolean;
  violation: null | {                // non-null when overall == "fail"
    status: "open" | "resolved";
    resolved_by: { id: number; username: string } | null;
    resolved_at: string | null;
    note: string;
  };
}
```

`not_visible` means the body part wasn't in frame (e.g. feet cut off, so boots can't be
checked). It counts as **not passing** — show it as amber "Not visible", not red.

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/auth/login` | `{username, password}` | `{access_token, token_type: "bearer", user: User}` |
| GET | `/api/auth/me` | — | `User` |

Tokens last 12 hours. Store the token client-side (e.g. localStorage) and log out on `401`.

## Sites (admin writes, everyone reads)

| Method | Path | Body / query |
|---|---|---|
| GET | `/api/sites` | `?active=true` |
| POST | `/api/sites` | `{name, location}` |
| PATCH | `/api/sites/{id}` | any of `{name, location, is_active}` |
| DELETE | `/api/sites/{id}` | soft delete (sets `is_active=false`) |

## Workers

| Method | Path | Body / query |
|---|---|---|
| GET | `/api/workers` | `?site_id=&q=&active=true` (`q` matches name or employee code) |
| POST | `/api/workers` | `{employee_code, full_name, trade, site_id}` |
| PATCH | `/api/workers/{id}` | any of the above + `is_active` |
| DELETE | `/api/workers/{id}` | soft delete |

## Users (admin only)

| Method | Path | Body |
|---|---|---|
| GET | `/api/users` | — |
| POST | `/api/users` | `{username, full_name, password, role, site_id}` (`site_id` required for supervisor) |
| PATCH | `/api/users/{id}` | any of `{full_name, password, role, site_id, is_active}` |
| DELETE | `/api/users/{id}` | soft delete (can't delete yourself) |

## Scans

| Method | Path | Query | Response |
|---|---|---|---|
| GET | `/api/scans` | `site_id, worker_id, result=pass\|fail, date_from, date_to (YYYY-MM-DD), limit, offset` | `{items: Scan[], total}` newest first |
| GET | `/api/scans/{id}` | — | `Scan` |
| GET | `/api/scans/{id}/snapshot` | — | `image/jpeg` (frame with boxes drawn) |

The snapshot and CSV endpoints also accept the token as `?token=<access_token>`, so a plain
`<img src=".../snapshot?token=...">` or download link works. (`fetch` with the auth header
→ `blob()` → `URL.createObjectURL` also works.)

## Violations

A violation is a failed scan. Same `Scan` shape.

| Method | Path | Body / query |
|---|---|---|
| GET | `/api/violations` | `?status=open\|resolved&site_id=&worker_id=&date_from=&date_to=&limit=&offset=` |
| POST | `/api/violations/{scan_id}/resolve` | `{note}` → returns updated `Scan` |

## Reports

`GET /api/reports/summary?site_id=&date_from=&date_to=` (defaults to last 30 days)

```ts
{
  total_scans: number; passed: number; failed: number;
  compliance_rate: number;            // 0–100, one decimal
  open_violations: number;
  by_item: Record<PpeItem, { pass: number; fail: number; not_visible: number }>;
  by_day:    { date: string; total: number; passed: number; failed: number }[];   // every day in range, zeros included
  by_site:   { site_id: number; site_name: string; total: number; passed: number; failed: number; compliance_rate: number }[];
  by_worker: { worker_id: number; full_name: string; employee_code: string; total: number; passed: number; failed: number; compliance_rate: number; last_scan_at: string | null }[];
}
```

`GET /api/reports/export.csv?site_id=&worker_id=&result=&date_from=&date_to=`: CSV download
of scans (use fetch + blob because of the auth header).

## Live scanning — WebSocket `/ws/scan?token=<access_token>`

Browsers can't set headers on WebSockets, so the token goes in the query string.
A bad token closes the socket with code `4401`.

### Flow
1. Scan page: user picks **site** then **worker** (from `GET /api/workers?site_id=`).
2. Open camera, open socket.
3. Send a frame, **wait for the `detection` reply, then send the next one** (never queue
   frames; aim for ~300 ms between frames). Resize frames to **max 640 px wide**, JPEG quality ~0.7.
4. Draw boxes and update the checklist from each `detection`.
5. When `stable` is true, enable **Record result**. Clicking it sends `record`.
6. Server replies `recorded` with the saved `Scan`. Show the result, then reset for the next worker.

### Client → server
```ts
{ type: "frame"; image: string }                        // "data:image/jpeg;base64,..."
{ type: "record"; worker_id: number; site_id: number }
{ type: "reset" }                                        // clear the rolling window (new worker)
```

### Server → client
```ts
{
  type: "detection";
  frame_width: number; frame_height: number;             // box coords are pixels in this frame
  person: { x1: number; y1: number; x2: number; y2: number; confidence: number } | null;
  detections: { label: PpeItem | "goggles"; x1: number; y1: number; x2: number; y2: number; confidence: number }[];
  items: Record<PpeItem, LiveItemStatus>;                // smoothed over recent frames
  overall: "pass" | "fail" | null;                       // null while no person
  stable: boolean;                                       // enough consistent frames to record
  latency_ms: number;
}
{ type: "recorded"; scan: Scan }
{ type: "error"; message: string }
```

Scale box coordinates from `frame_width/height` to the displayed video size (the
video element may be letterboxed or `object-fit: cover`).

### Behavior details
- `stable` becomes true once the 8-frame window is full and each item's majority status appears in at least 60% of those frames.
- `record` returns an `error` (and saves nothing) unless `stable` is true, the worker is active, and the worker belongs to `site_id`.
  Supervisors can only record at their own site.
- After `recorded`, the server clears its window itself, so the next worker starts fresh. Sending `reset` anyway is harmless.
- `detections` lists only gear found on the main worker (the largest person in frame): `label` is a PPE item or `"goggles"`.
- An unknown message type gets `{type: "error"}`; the socket stays open.
- A frame can also be sent as a raw binary JPEG message instead of `{type: "frame"}` JSON.

## Extra endpoints

| Method | Path | Body / query | Response |
|---|---|---|---|
| POST | `/api/auth/change-password` | `{current_password, new_password}` | success / `400` if current password is wrong |
| POST | `/api/violations/{scan_id}/reopen` | — | updated `Scan` (violation back to `open`) |
| GET | `/api/scans/export.csv` | same as `/api/reports/export.csv` | CSV (alias) |
| GET | `/api/model` | — | `{ppe_model, ppe_classes: string[], pose_model, device}` |
| POST | `/api/analyze` | multipart form, field `image` (JPEG/PNG) | single-frame PPE analysis plus `overall`; nothing is saved. Useful for testing without a camera. |

## Health

`GET /health` → `{"status": "ok", "model_loaded": boolean, "device": "cuda" | "cpu"}` (no auth)
