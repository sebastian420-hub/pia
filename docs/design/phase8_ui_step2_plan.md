# 🏢 BURMANLABS: Phase 8 UI Architecture - Step 2 (Entity Dossier & Triage)

**Phase:** 8.2 (Triage & Context)
**Subject:** Implementation Plan for the Entity Dossier and Filter Bar.

---

## 1. Objective
To complete the "Decision Dominance" interface, the dashboard needs two critical components:
1.  **The Filter Bar (Top):** To control the signal-to-noise ratio of the incoming data.
2.  **The Entity Dossier (Right Sidebar):** To provide deep context (AI summaries, sources) for any selected event or node, eliminating the need to guess *why* an event is flagged.

---

## 2. Technical Architecture

### 2.1 The Filter Bar (`src/components/hud/FilterBar.tsx`)
A top-aligned, glassmorphic panel containing pill-shaped toggle buttons.
*   **State Management:** The `Dashboard.tsx` will hold a `filters` state object (e.g., `{ domains: ['MILITARY', 'CYBER'], minPriority: 'NORMAL' }`).
*   **Action:** When a user clicks "MILITARY", the `Dashboard` state updates, instantly filtering both the `LiveTicker` list and the `Cesium` markers.

### 2.2 The Entity Dossier (`src/components/hud/EntityDossier.tsx`)
A right-aligned, slide-in panel (using Framer Motion) that triggers when a user clicks a marker on the globe or an item in the Live Ticker.
*   **State Management:** `Dashboard.tsx` will hold an `activeDossierEvent` state.
*   **Content:**
    *   **Header:** Headline and Domain.
    *   **Body:** A placeholder for the AI Summary (until we wire up the specific API endpoint).
    *   **Action:** A "VIEW RELATIONAL WEB" button inside the dossier that triggers the existing `RelationalWeb` component, seamlessly linking the spatial and relational views.

---

## 3. Implementation Steps

1.  **Build `FilterBar.tsx`:** Create the top navigation component with domain toggle buttons.
2.  **Update `Dashboard.tsx` (Filtering):** Wire the `FilterBar` to the `events` state so that the map and ticker only show events matching the active filters.
3.  **Build `EntityDossier.tsx`:** Create the right-hand slide-out panel using Framer Motion.
4.  **Update `Dashboard.tsx` (Dossier Logic):** 
    *   Modify `handleEventClick` so that instead of just flying the camera, it also sets the `activeDossierEvent`.
    *   Render the `EntityDossier` component conditionally.
5.  **Connect Dossier to Graph:** Add a button in the Dossier that sets `activeGraphEntity` to launch the 3D graph, replacing the hardcoded "TEST GRAPH (ISRAEL)" button.

---
*End of Plan.*