# My Data Page — Structure, Logic & Workflow

## Overview

The My Data page is the AI knowledge base for the application. It stores structured business data (products, pricing, offers, hours, etc.) that the AI uses to personalize outreach campaigns. Users can browse, search, and manage data entries and their sources.

---

## File Structure

```
client/src/components/mydata/
├── MyDataPage.tsx     — Main page component + all sub-components
└── myDataData.ts      — Types, config maps, and mock data
```

---

## Data Layer (`myDataData.ts`)

### Types

| Type | Values |
|------|--------|
| `DataCategory` | `products`, `pricing`, `offers`, `business_hours`, `meetings`, `contacts`, `company_info`, `custom` |
| `SourceType` | `csv_import`, `google_sheets`, `manual`, `api` |
| `SourceStatus` | `connected`, `syncing`, `paused` |
| `QualityLevel` | `high` (≥75), `medium` (≥45), `low` (<45) |

### Key Interfaces

**`DataField`** — A single key-value field within an entry.
- `key`, `label`, `value`, `type` (text/number/url/email/phone/time/date/boolean/list)
- `aiRelevance`: `critical | high | medium | low` — drives the colored dot indicator

**`DataEntry`** — A structured business data record.
- Belongs to a `category`, linked to a `sourceId`
- Has `fields[]`, `qualityScore` (0–100), `missingFields[]`, `usedIn[]` (campaign names)

**`DataSource`** — A connected data source.
- Has `type`, `status`, `records` count, `lastSync` timestamp, `aiReadyPct`

### Config Maps

- `CATEGORY_CONFIG` — label, color, description per category
- `SOURCE_TYPE_CONFIG` — label and color per source type
- `SOURCE_STATUS_CONFIG` — label, color, background per status
- `QUALITY_CONFIG` — label, color, bg per quality level
- `AI_RELEVANCE_CONFIG` — label, color, dot color per relevance level

---

## Component Tree (`MyDataPage.tsx`)

```
MyDataPage
├── TopBar (header with title, stat pills, Sources button, Add Data button)
├── LeftNav (sidebar: search, All Data, Data Sources, category nav, AI Health panel)
│   └── NavItem (reusable nav button with count badge)
├── Right Content Area
│   ├── Mobile search bar
│   ├── AI Insight Banner (shown when low-quality entries exist)
│   ├── SourcesView (when activeCategory === 'sources')
│   │   ├── Header strip (count + total records)
│   │   └── Source table (with pause/sync/delete actions per row)
│   ├── All Data view (when activeCategory === 'all')
│   │   └── CategorySection[] (one per category with entries)
│   │       └── EntryRow[] (clickable table rows)
│   └── Single Category view (when a specific category is selected)
│       └── CategorySection (filtered entries)
├── EntryPanel (modal overlay — shown when an entry row is clicked)
└── AddDataModal (modal — shown when "Add Data" is clicked)
    ├── Choose step (CSV / Manual / Google Sheets / API)
    ├── CSV step (drag-and-drop upload)
    ├── Manual step (category picker + title + content fields)
    ├── Sheets step (URL + sheet name input)
    └── API step (source name + endpoint URL input)
```

---

## Helper Components

| Component | Purpose |
|-----------|---------|
| `CountUp` | Animates a number from 0 to target on mount (eased) |
| `SourcePill` | Status badge (Connected / Syncing / Paused) with icon |
| `RelevanceDot` | Colored dot indicating AI field relevance level |
| `QualityStrip` | Mini progress bar + percentage for data quality score |
| `NavItem` | Sidebar navigation button with icon, label, and count badge |

---

## State Management

All state is local (React `useState`). No external store.

| State | Location | Purpose |
|-------|----------|---------|
| `activeCategory` | `MyDataPage` | Controls which view is shown (all / sources / specific category) |
| `search` | `MyDataPage` | Filters entries by title or field value/label |
| `selectedEntry` | `MyDataPage` | Opens the `EntryPanel` detail modal |
| `modalOpen` | `MyDataPage` | Opens the `AddDataModal` |
| `collapsed` | `CategorySection` | Toggles section expand/collapse |
| `step` | `AddDataModal` | Controls which add-data step is shown |
| `sources` | `SourcesView` | Local copy of `DATA_SOURCES` for interactive mutations |
| `deletingId` | `SourcesView` | Tracks which source row is animating out on delete |

---

## Core Workflows

### 1. Browsing Data

1. Page loads with `activeCategory = 'all'`
2. `filteredEntries` is computed via `useMemo` — filters by category and search query
3. `groupedEntries` groups filtered entries by category into a `Map`
4. Each group renders as a `CategorySection` with collapsible rows
5. Clicking a row opens `EntryPanel` with full field details

### 2. Searching

- Search input lives in `LeftNav` (desktop) and a mobile bar (mobile)
- Both update the shared `search` state in `MyDataPage`
- Filtering matches against `entry.title` and any `field.value` or `field.label`

### 3. Viewing Sources

1. Clicking the "Sources" button in the top bar sets `activeCategory = 'sources'`
2. `SourcesView` renders with a local copy of `DATA_SOURCES`
3. Each source row shows: name, type badge, record count, AI-ready progress bar, status pill, and action buttons
4. Actions:
   - **Pause/Resume** — toggles status between `connected` and `paused`
   - **Sync Now** — sets status to `syncing` for 2 seconds, then back to `connected`
   - **Delete** — animates the row out, then removes it from local state

### 4. Adding Data

1. Clicking "Add Data" opens `AddDataModal` at the `choose` step
2. User picks one of four methods: CSV Upload, Manual Entry, Google Sheets, API/Webhook
3. Each method has its own form step with relevant inputs
4. Back arrow returns to the `choose` step; close button resets and dismisses

### 5. Entry Detail

1. Clicking any `EntryRow` sets `selectedEntry` in `MyDataPage`
2. `EntryPanel` renders as a fixed overlay with backdrop blur
3. Shows: category, source, last updated, quality score, missing fields warning, all fields with AI relevance dots
4. URL-type fields render with an external link icon; list-type fields render as tag chips
5. Edit and Delete buttons are present (UI only — no mutation logic yet)
6. Clicking the backdrop or close button clears `selectedEntry`

---

## Quality Score Logic

```ts
getQualityLevel(score: number): QualityLevel
  score >= 75  → 'high'   (green)
  score >= 45  → 'medium' (yellow)
  score < 45   → 'low'    (red)
```

The AI Insight Banner appears when any entries have `qualityScore < 75` or non-empty `missingFields[]`.

---

## AI Health Panel (Sidebar)

Displays two static metrics at the bottom of the left nav:
- **Data completeness**: 87%
- **AI-ready entries**: 91%

These represent the overall readiness of the knowledge base for AI-powered campaign generation.
