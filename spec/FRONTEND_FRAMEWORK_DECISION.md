# Frontend Framework Decision — Kingswalk SCADA GUI

**Date:** 2026-04-10
**Status:** Recommended — awaiting client sign-off
**Author:** Watson Mattheus Consulting

---

## Context

The Kingswalk Mall SCADA GUI is a web-based industrial control interface for monitoring and operating ABB switchgear across 9 Main Boards (104 outgoing breakers, ~150 IP-addressable field devices). It is accessed from fixed operator workstations in switchrooms, a central control room, and potentially a facility manager's laptop over VPN.

The CCMD project evaluated React Native, Flutter and Capacitor/Ionic for a multi-platform mobile-first command centre app. This document re-evaluates those options against the specific constraints of Kingswalk SCADA.

## Decision

**React (Vite + TypeScript SPA)** — a pure browser application served over HTTPS/WSS, with no native mobile wrapper at this stage.

## Why — requirement-by-requirement

### 1. Real-time state updates (<1s field → browser)

The backend pushes telemetry over WebSocket. In the browser, `WebSocket` is a native API with zero abstraction overhead. React 18 concurrent rendering handles hundreds of state updates per second without frame drops.

React Native and Flutter both bridge WebSocket through their native runtimes, adding 10–50ms of jitter. For an industrial control dashboard where an operator watches live breaker state, that jitter is unnecessary risk.

**Winner:** React (browser-native WebSocket)

### 2. Interactive floor-plan overlay (SVG with live state)

The SCADA floor plan renders an SVG with 100+ interactive hotspots (breakers, distribution boards, measuring devices), colour-coded by live state, with zoom/pan and tooltips. In the browser, SVG is a first-class DOM citizen — each element is individually addressable, CSS-transitionable, and hardware-accelerated.

Flutter rasterises SVG via `flutter_svg`, losing per-element interactivity. React Native requires `react-native-svg`, which is less performant and mature than browser SVG.

**Winner:** React (browser-native SVG)

### 3. Role-gated breaker control (two-step confirm, audit trail)

This is pure application logic — no framework advantage. All three can implement confirmation dialogs and POST to the FastAPI backend. However, React's ecosystem has mature form/modal libraries (Radix, Headless UI) that map directly to WCAG 2.1 AA compliance.

**Winner:** Neutral (slight React edge for accessibility libraries)

### 4. Reporting (PDF/CSV generation)

Reports are generated server-side by FastAPI and delivered as file downloads or email attachments. The frontend just triggers and displays them. No framework advantage.

**Winner:** Neutral

### 5. Deployment model

SCADA is an intranet/VPN application, not an App Store product. A web app behind nginx/Caddy with TLS is the natural deployment:

- Zero client install
- Instant updates (no App Store review cycle)
- Works on any device with a modern browser
- No platform-specific build pipelines

React Native and Flutter both require build infrastructure (Xcode, Android SDK, EAS, Fastlane) that adds cost and complexity with no benefit for a browser-accessed control system.

**Winner:** React (simplest deployment, zero client install)

### 6. Network architecture

The browser never touches the SCADA VLAN directly. All communication flows through the FastAPI backend over HTTPS/WSS. There is no requirement for native device APIs (Bluetooth, local network discovery, background tasks) that would justify a native mobile shell.

**Winner:** Neutral (no native access needed)

### 7. Future mobile access

If a facility manager later needs mobile alarm notifications and a read-only dashboard on their phone:

- **Phase 1:** Progressive Web App (PWA) with service worker push notifications. This requires zero additional code — just a manifest and service worker added to the existing React app.
- **Phase 2 (if needed):** Wrap the existing React app in Capacitor for App Store distribution. This is a 2–3 day integration task, not an upfront architecture decision.

**Winner:** React (PWA path is incremental, not architectural)

## Framework comparison matrix

| Requirement | React (Vite) | React Native | Flutter | Capacitor |
|---|---|---|---|---|
| WebSocket (<1s latency) | Native | Bridged (+10-50ms) | Bridged (+10-50ms) | Native (web) |
| SVG floor plan | Native DOM | react-native-svg | Rasterised | Native (web) |
| WCAG 2.1 AA | Full ecosystem | Partial | Manual | Full (web) |
| Deployment (intranet) | nginx + TLS | App build pipeline | App build pipeline | nginx + TLS |
| Native device APIs | N/A | Full | Full | Partial |
| PWA upgrade path | Built-in | N/A | N/A | Built-in |
| Team skill requirement | TypeScript + React | TypeScript + React + Native | Dart | TypeScript + React |
| Build complexity | Low (Vite) | High (Metro + Xcode/Gradle) | High (Flutter CLI) | Medium |

## Recommended stack (as specified in SPEC.md §2.2)

| Layer | Technology |
|---|---|
| **Framework** | React 18 + TypeScript |
| **Bundler** | Vite 6 |
| **State management** | Zustand (lightweight, WebSocket-friendly) |
| **Styling** | Tailwind CSS 4 |
| **Component library** | Radix UI (headless, accessible) |
| **Charting** | Recharts or Apache ECharts (PQ trends, harmonics) |
| **SVG floor plan** | Custom React SVG components + d3-zoom |
| **WebSocket** | Native browser API, managed via Zustand middleware |
| **Forms** | React Hook Form + Zod validation |
| **Routing** | React Router 7 |
| **Testing** | Vitest + Testing Library + Playwright (E2E) |
| **Build target** | Static SPA, served by nginx/Caddy |
| **Future mobile** | PWA → Capacitor if App Store needed |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Client later insists on native iOS/Android app | Capacitor wrap is a 2–3 day task on the existing React codebase |
| Browser limitations on push notifications (iOS Safari) | iOS 16.4+ supports web push; fallback to email alerts |
| Large floor-plan SVG causes rendering lag | Virtualise off-screen elements; use `will-change: transform` for pan/zoom layer |
| WebSocket reconnection on unreliable site network | Exponential backoff with jitter; visual "connection lost" banner in UI |

## Conclusion

For a SCADA control system accessed from fixed workstations over an intranet, a pure React web application is the correct choice. It delivers the best real-time performance, the richest SVG interactivity, the simplest deployment, and leaves a clean upgrade path to PWA or Capacitor-wrapped mobile if the need arises.

React Native and Flutter solve a problem (multi-platform native mobile distribution) that Kingswalk SCADA does not have. Choosing either would add build complexity, runtime overhead, and team skill requirements with no compensating benefit.
