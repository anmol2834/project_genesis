# MailFlowAI — Complete Client-Side Architecture Documentation

> Last updated: March 2026 — reflects full current frontend implementation

---

## 1. Executive Summary

**MailFlowAI** is an enterprise-grade AI-powered mail automation SaaS platform. The frontend is a Next.js 14 App Router application built with Material UI v5, TypeScript, and a fully custom design system. It provides a complete dashboard for managing email outreach, lead pipelines, AI automation, analytics, team collaboration, integrations, billing, and support.

**Product name**: MailFlowAI  
**Tagline**: AI-powered email automation for B2B outreach  
**Primary users**: Sales teams, growth teams, founders doing outbound  

---

## 2. Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| UI Library | Material UI v5 (MUI) |
| Styling | MUI `sx` prop + CSS-in-JS via Emotion |
| Charts | `@visx` (ParentSize, LinePath, Area, GridRows, AxisBottom, AxisLeft, LinearGradient, Group) + `d3-shape` (curveMonotoneX) |
| Theme | Custom dual-mode MUI theme (light + dark) |
| State | React `useState` / `useMemo` / `useEffect` (no external state library) |
| Data Fetching | TanStack Query v5 (React Query) |
| HTTP Client | Axios |
| Routing | Next.js App Router file-based routing |
| Icons | Material Icons Rounded set |
| Fonts | System font stack via MUI typography |

---

## 3. Project Structure

```
client/
├── src/
│   ├── app/                          # Next.js App Router pages
│   │   ├── layout.tsx                # Root layout (QueryProvider + AppThemeProvider)
│   │   ├── page.tsx                  # Landing page (/)
│   │   ├── sign-in/page.tsx          # Sign-in route
│   │   ├── sign-up/page.tsx          # Sign-up route
│   │   └── dashboard/
│   │       ├── layout.tsx            # Dashboard shell (Sidebar + TopBar)
│   │       ├── page.tsx              # Dashboard home
│   │       ├── inbox/page.tsx
│   │       ├── campaigns/page.tsx
│   │       ├── leads/page.tsx
│   │       ├── accounts/page.tsx
│   │       ├── automation/page.tsx
│   │       ├── research/page.tsx
│   │       ├── my-data/page.tsx
│   │       ├── analytics/page.tsx
│   │       ├── team/page.tsx
│   │       ├── integrations/page.tsx
│   │       ├── settings/page.tsx
│   │       ├── billing/page.tsx
│   │       └── help/page.tsx
│   ├── components/
│   │   ├── landing/                  # Public landing page sections
│   │   ├── auth/                     # Sign-in + multi-step sign-up
│   │   ├── dashboard/                # Shell: Sidebar, TopBar, widgets
│   │   ├── inbox/                    # Chat-based inbox
│   │   ├── campaigns/                # Campaign management
│   │   ├── leads/                    # Lead pipeline
│   │   ├── accounts/                 # Email account management
│   │   ├── analytics/                # Analytics + charts
│   │   ├── mydata/                   # Business knowledge base
│   │   ├── research/                 # AI research tool
│   │   ├── team/                     # Team RBAC management
│   │   ├── integrations/             # Integration marketplace
│   │   ├── settings/                 # System settings panel
│   │   ├── billing/                  # Billing & subscription
│   │   ├── help/                     # Help & support hub
│   │   └── shared/                   # Shared components (CSVImportModal)
│   ├── lib/
│   │   └── react-query/              # TanStack Query setup
│   │       ├── queryClient.ts        # Global QueryClient config
│   │       ├── provider.tsx          # QueryClientProvider wrapper
│   │       └── queryKeys.ts          # Centralized query key factory
│   ├── services/
│   │   ├── apiClient.ts              # Axios HTTP client
│   │   └── endpoints/                # API endpoint modules
│   │       ├── campaigns.ts
│   │       ├── leads.ts
│   │       ├── inbox.ts
│   │       ├── analytics.ts
│   │       ├── accounts.ts
│   │       ├── team.ts
│   │       ├── integrations.ts
│   │       ├── billing.ts
│   │       ├── settings.ts
│   │       └── research.ts
│   ├── hooks/
│   │   ├── queries/                  # Read operations (GET)
│   │   │   ├── useCampaigns.ts
│   │   │   ├── useLeads.ts
│   │   │   ├── useInbox.ts
│   │   │   ├── useAnalytics.ts
│   │   │   ├── useAccounts.ts
│   │   │   ├── useTeam.ts
│   │   │   ├── useIntegrations.ts
│   │   │   ├── useBilling.ts
│   │   │   ├── useSettings.ts
│   │   │   ├── useResearch.ts
│   │   │   └── index.ts
│   │   └── mutations/                # Write operations (POST/PUT/DELETE)
│   │       ├── useCampaignMutations.ts
│   │       ├── useLeadMutations.ts
│   │       ├── useInboxMutations.ts
│   │       ├── useAccountMutations.ts
│   │       ├── useTeamMutations.ts
│   │       ├── useIntegrationMutations.ts
│   │       ├── useBillingMutations.ts
│   │       ├── useSettingsMutations.ts
│   │       ├── useResearchMutations.ts
│   │       └── index.ts
│   ├── providers/
│   │   └── AppThemeProvider.tsx      # Re-exports theme provider
│   ├── theme/                        # Complete MUI design system
│   └── styles/                       # Global CSS resets
```

---

## 4. Design System

### 4.1 Theme Architecture

The theme is split across multiple files in `client/src/theme/`:

| File | Purpose |
|------|---------|
| `palette.ts` | Raw color scales + light/dark palettes + gradients |
| `typography.ts` | Font sizes, weights, line heights |
| `darkTheme.ts` | Dark mode ThemeOptions |
| `lightTheme.ts` | Light mode ThemeOptions |
| `themeProvider.tsx` | `AppThemeProvider` + `useThemeMode` hook |
| `components.ts` | MUI component overrides |
| `shadows.ts` | Custom shadow scale |
| `breakpoints.ts` | Responsive breakpoints |
| `spacing.ts` | 8px base spacing unit |
| `shape.ts` | Border radius tokens |

### 4.2 Color Palette

**Brand colors (Indigo scale)**:
- Light primary: `#4338ca` (brandScale[700])
- Dark primary: `#818cf8` (brandScale[400])

**Semantic accent colors used across pages**:
- `#818cf8` — Indigo (primary, analytics, AI)
- `#c084fc` — Purple (AI features, campaigns)
- `#34d399` — Green (success, connected, leads)
- `#22d3ee` — Cyan (info, email sync)
- `#fbbf24` — Amber (warning, automation)
- `#f87171` — Red (error, danger)
- `#f472b6` — Pink (ads/social)
- `#60a5fa` — Blue (team, sessions)
- `#fb923c` — Orange (security)
- `#a3e635` — Lime (data/privacy)

**Dark mode backgrounds**:
- Page root: `#080d18` (deepest navy)
- Default: `#0f172a`
- Paper: `#1e293b`
- Sidebar: `rgba(15,10,40,0.85)` with `backdropFilter: blur(16px)`

### 4.3 Gradients

```typescript
lightGradients.primary = 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)'
darkGradients.primary  = 'linear-gradient(135deg, #818cf8 0%, #a78bfa 100%)'
darkGradients.aurora   = 'linear-gradient(135deg, #818cf8 0%, #22d3ee 100%)'
```

### 4.4 Theme Toggle

`AppThemeProvider` wraps the entire app. `useThemeMode()` hook exposes `{ mode, toggleTheme }`. The toggle button lives in the dashboard top-right strip (desktop) and mobile TopBar.

### 4.5 Design Philosophy

- **Non-card-based approach** on most pages — content organized as rows with thin dividers, glassmorphism containers, and colored left-bar accents instead of elevated cards
- **Glassmorphism panels**: `backdropFilter: blur(12px)` + semi-transparent backgrounds
- **Glow effects**: `boxShadow: 0 0 Xpx alpha(color, 0.4)` on active states and status dots
- **Micro-animations**: `fadeDown`, `fadeUp`, `popIn`, `pulse`, `spin` keyframes inline in `sx`
- **Responsive**: Mobile-first, `xs/sm/md/lg` breakpoints throughout

---

## 5. Application Shell

### 5.1 Root Layout (`app/layout.tsx`)
Wraps everything in `QueryProvider` (TanStack Query) and `AppThemeProvider` (MUI theme). Sets `html` `data-scroll-behavior="smooth"`.

**Provider hierarchy**:
```tsx
<QueryProvider>
  <AppThemeProvider>
    {children}
  </AppThemeProvider>
</QueryProvider>
```

### 5.2 Dashboard Shell (`app/dashboard/layout.tsx`)
- Full-height flex container (`height: 100svh`, `overflow: hidden`)
- Desktop: `Sidebar` (220px fixed left) + main column
- Mobile: `TopBar` (sticky header with hamburger) replaces sidebar
- Top-right strip (desktop only): theme toggle button
- Route content: `flex: 1, overflow: hidden, minHeight: 0, display: flex, flexDirection: column`

### 5.3 Sidebar (`components/dashboard/Sidebar.tsx`)
**Width**: 220px, sticky, `height: 100svh`

**Navigation sections**:
1. *(unlabeled)*: Dashboard, Inbox (badge: 12)
2. **Outreach**: Campaigns, Leads, Email Accounts
3. **Intelligence**: Automation, Research, My Data
4. **Insights**: Analytics, Notifications (badge: 3)
5. **Workspace**: Team, Integrations

**Bottom section** (separated by top border):
- Settings → `/dashboard/settings`
- Billing → `/dashboard/billing` (accent: `#34d399`)
- Help & Support → `/dashboard/help` (accent: `#fbbf24`)

**Active state**: Colored left-bar indicator (3px) + tinted background + colored icon/text

### 5.4 TopBar (`components/dashboard/TopBar.tsx`)
Mobile-only sticky header. Contains:
- Hamburger → opens full-screen `Drawer`
- Centered logo
- Theme toggle button

**Drawer** mirrors Sidebar exactly: same 5 nav sections with labels, same badges, same bottom items (Settings, Billing, Help & Support), scrollable with `overflowY: auto`.

---

## 6. Public Pages

### 6.1 Landing Page (`/`)
Multi-section marketing page. Components in `components/landing/`:
- `Navbar` — sticky nav with logo + CTA
- `HeroSection` — headline, subtext, CTA buttons
- `StatsSection` — key metrics strip
- `FeaturesSection` — feature grid
- `HowItWorksSection` — step-by-step flow
- `AISection` — AI capabilities showcase
- `InboxSection` — inbox preview
- `PricingSection` — plan comparison
- `CTASection` — conversion CTA
- `Footer` — links + legal

Uses `motion.tsx` for scroll-triggered animations.

### 6.2 Sign-In Page (`/sign-in`)
Two-column layout:
- Left: `SignInForm` (email + password, OAuth buttons)
- Right: `AuthVisual` (animated illustration)

### 6.3 Sign-Up Page (`/sign-up`)
Two-column layout:
- Left: Multi-step form with `StepIndicator`
- Right: `SignUpVisual` (step-aware animated panel)

**6 steps**:
1. `Step1Account` — name, email, password
2. `Step2OTP` — email verification code
3. `Step3Business` — company name, industry, website
4. `Step4AIContext` — AI tone preference, use case
5. `Step5Email` — connect first email account (Gmail/Outlook OAuth)
6. `Step6Review` — summary before launch

---

## 7. Dashboard Home (`/dashboard`)

**Components**: `WelcomeBanner`, `StatsOverview`, `QuickActions`, `InboxPreview`, `AIActivityPanel`, `EmailChart`, `ActivityFeed`

**Layout**: Responsive grid. Stats strip (4 KPI cards) → two-column body (main content + AI panel) → activity feed.

**Features**:
- Animated counters on KPI cards
- Email performance line chart (visx)
- AI activity feed with real-time-style updates
- Quick action buttons linking to key workflows
- Inbox preview showing latest conversations

---

## 8. Inbox Page (`/dashboard/inbox`)

**Components**: `InboxView`, `ConversationList`, `ChatView`  
**Data**: `inboxData.ts`

### Layout
Two-panel: conversation list (left, 320px) + chat view (right, flex-1). On mobile: single column, list first.

### ConversationList
- Search bar with live filter
- Filter tabs: All, Unread, Replied, AI-handled
- Each row: avatar, name, snippet, timestamp, unread badge
- Active conversation highlighted with colored left bar

### ChatView
- Message thread with sender/receiver bubbles
- AI-generated reply indicator badge
- Reply composer at bottom
- Attachment support UI
- Send button + keyboard shortcut (Enter)

### Data Model (`inboxData.ts`)
```typescript
interface Conversation {
  id, name, email, avatar, lastMessage,
  timestamp, unread, status, aiHandled, messages[]
}
interface Message {
  id, sender, content, timestamp, isAI
}
```

---

## 9. Campaigns Page (`/dashboard/campaigns`)

**Components**: `CampaignsPage`  
**Data**: `campaignData.ts`

### Features
- Campaign list with status badges (Running / Paused / Draft)
- Per-campaign stats: emails sent, open rate, reply rate, progress bar
- AI insight chip per campaign (positive/warning/neutral)
- Tag system (Enterprise, SaaS, B2B, etc.)
- Create campaign button
- Filter by status

### Data Model
```typescript
type CampaignStatus = 'running' | 'paused' | 'draft'
interface Campaign {
  id, name, status, emailsSent, emailsTotal,
  openRate, replyRate, lastActivity, createdAt,
  accentColor, aiInsight, insightType, tags[]
}
```

### Status Colors
- Running: `#34d399` (green)
- Paused: `#fbbf24` (amber)
- Draft: `#94a3b8` (slate)

---

## 10. Leads Page (`/dashboard/leads`)

**Components**: `LeadsPage`  
**Data**: `leadsData.ts`  
**Shared**: `CSVImportModal`

### Features
- Paginated lead table (10/15/20 per page)
- Filter by status (New / Contacted / Engaged / Unresponsive)
- Search by name, email, company
- Lead score (0–100) with color indicator
- Tag badges (hot, warm, cold, vip, decision-maker, technical)
- Campaign association column
- Import CSV button → opens `CSVImportModal`
- Empty state with import CTA

### Data Model
```typescript
type LeadStatus = 'new' | 'contacted' | 'engaged' | 'unresponsive'
type LeadTag = 'hot' | 'warm' | 'cold' | 'vip' | 'decision-maker' | 'technical'
interface Lead {
  id, name, email, company, role, status,
  tags[], campaign, lastActivity, addedAt,
  avatarColor, score
}
```

### CSV Import Modal (Shared)
Located at `components/shared/CSVImportModal.tsx`. Used by both Leads page and Integrations page.

**3-step flow**:
1. **Upload** — drag-and-drop zone + click-to-browse, required columns display (`email`, `first_name`, `last_name`), recent import history
2. **Loading** — animated progress bar, processed rows counter, 4-step indicator (Parsing → Validating → Deduplicating → Importing), spinner in footer
3. **Done** — success animation, import stats (Imported / Duplicates / Skipped), "Import another" + "View leads" buttons

**"View leads"** navigates to `/dashboard/leads` via `useRouter`.

Required columns: `email`, `first_name`, `last_name` (company intentionally excluded for B2B/B2C flexibility).

---

## 11. Email Accounts Page (`/dashboard/accounts`)

**Components**: `EmailAccountsPage`  
**Data**: `accountsData.ts`

### Features
- Summary stats strip: Total Accounts, Active, Healthy Sync, Emails Processed (animated counters)
- Account cards with provider logo (Gmail SVG / Outlook SVG / custom)
- Per-account: status badge, last sync time, 3 stats (Processed / Sent Today / Reply Rate)
- Daily usage progress bar (color shifts amber at 60%, red at 85%)
- Automation toggle (Switch) per account
- AI insight row per account (positive/warning/neutral)
- Refresh + Delete action buttons
- Connect modal with two tabs:
  - **OAuth Providers**: Google Gmail, Microsoft Outlook (OAuth 2.0 flow)
  - **Custom SMTP**: host, port, username, password (show/hide), encryption (TLS/SSL/None)
- Trust indicators: encrypted storage, read/send permissions only

### Data Model
```typescript
type AccountStatus = 'connected' | 'syncing' | 'paused'
type AccountProvider = 'gmail' | 'outlook' | 'custom'
interface EmailAccount {
  id, email, name, provider, status, automationEnabled,
  lastSync, emailsProcessed, emailsSentToday, replyRate,
  insight, insightType, connectedAt, dailyLimit, dailyUsed
}
```

---

## 12. Analytics Page (`/dashboard/analytics`)

**Components**: `AnalyticsPage`  
**Data**: `analyticsData.ts`  
**Charts**: `@visx` + `d3-shape`

### Features
- Time range selector: 7 days / 30 days / 90 days
- KPI metric strip (6 cards): Emails Sent, Open Rate, Reply Rate, Conversion Rate, AI Success Rate, Avg Response Time — all with animated CountUp + sparklines + delta indicators
- AI insights strip: horizontal scrollable pills (positive/warning/neutral)
- Full-width line chart: Email Performance Trends (Sent + Opens + Replies)
- Two-column grid: Campaign table + (Lead Engagement donut + Account Performance)
- Two-column grid: AI Performance (line chart + tone bar chart) + Live Activity feed
- Bottom: Reply Rate Trend line chart

### Chart Components
- `CountUp` — animated number counter (easing cubic)
- `Sparkline` — inline SVG mini chart (no library)
- `LineChart` — visx ParentSize + LinePath + Area + GridRows + AxisBottom + AxisLeft + LinearGradient
- `HBarChart` — horizontal bar chart (pure SVG)
- `DonutChart` — SVG arc segments
- `Legend` — colored dot + label row

### Data Model (`analyticsData.ts`)
```typescript
type TimeRange = '7d' | '30d' | '90d'
interface DayPoint { date: string; value: number }
// SERIES[range]: emailsSent, replies, opens, aiReplies, manualReplies
// KPI[range]: emailsSent, openRate, replyRate, convRate, aiSuccessRate, aiVsManual, avgResponseTime, deltas
// CAMPAIGN_STATS[], ACCOUNT_STATS[], AI_INSIGHTS[], LEAD_ENGAGEMENT[], AI_TONE_PERF[]
```

### Scroll Behavior
Entire page (header + metric strip + insights + content) scrolls together inside a single `overflowY: auto` container. No fixed sections.

---

## 13. My Data Page (`/dashboard/my-data`)

**Components**: `MyDataPage`  
**Data**: `myDataData.ts`

### Concept
Wiki/knowledge-base layout for business data that the AI uses to make decisions. Not a leads/contacts page — stores business-specific information.

### Data Categories
- Products & Pricing
- Special Offers & Discounts
- Business Hours & Availability
- Meeting Schedules
- Company Information
- Custom Fields

### Layout
- Left navigation tree (category groupings)
- Right content area with collapsible category sections
- Inline table rows for data entries
- Slide-in detail panel (`EntryPanel`) for editing
- Sources view
- Add Data modal

### Data Model
```typescript
interface DataEntry { id, categoryId, fields[], sourceType, lastUpdated, aiReady }
interface DataField { key, label, value, type }
interface DataCategory { id, label, color, icon, entries[] }
```

---

## 14. Research Page (`/dashboard/research`)

**Components**: `ResearchPage`  
**Data**: `researchData.ts`

### Features
- AI-powered business research queries
- Search interface with query history
- Results display with source attribution
- Export research results
- Research templates for common queries

---

## 15. Team Page (`/dashboard/team`)

**Components**: `TeamPage`  
**Data**: `teamData.ts`

### Layout
Fixed top header + left filter panel + right scrollable content. Two tabs: **Members** (CSS Grid table) + **Activity** feed.

### Members Tab
- Grid table: Avatar, Name/Email, Role badge, Status badge, Stats (campaigns, emails, AI actions), Edit button
- Filter by status (Active/Invited/Suspended) and role (Owner/Admin/Member)
- Search by name/email

### Activity Tab
- Chronological event feed
- Event types: campaign, email, ai, lead, settings, invite
- Member avatar + action + target + timestamp

### Edit Member Panel (slide-in)
- Role selector
- Grouped permission toggles (Switch) by group: Outreach / Intelligence / Workspace
- Status change

### Invite Modal
- Email input
- Role picker
- Expandable permission overrides

### RBAC Model
```typescript
type MemberRole = 'owner' | 'admin' | 'member'
type MemberStatus = 'active' | 'invited' | 'suspended'

// Permission groups:
// outreach: inbox, campaigns, leads, email_accounts
// intelligence: ai_control, research, my_data, automation
// workspace: analytics, team, integrations, billing

// Default permissions:
// owner: all 12 permissions
// admin: 9 permissions (no team, integrations, billing)
// member: inbox, campaigns, leads
```

### Data Model
```typescript
interface TeamMember {
  id, name, email, role, status, avatarColor,
  joinedAt, lastActive, permissions[],
  activityCount, campaignsManaged, emailsSent, aiActionsTriggered
}
interface ActivityEvent {
  id, memberId, memberName, action, target, timestamp,
  type: 'campaign'|'email'|'ai'|'lead'|'settings'|'invite'
}
```

---

## 16. Integrations Page (`/dashboard/integrations`)

**Components**: `IntegrationsPage`  
**Data**: `integrationsData.ts`

### Concept
Integration marketplace + control center. Non-card horizontal list rows grouped by category.

### Categories (4 active)
| ID | Label | Color |
|----|-------|-------|
| `email` | Email Providers | `#818cf8` |
| `crm` | CRM Systems | `#34d399` |
| `leads` | Lead Sources | `#fbbf24` |
| `ads` | Ads & Social | `#f472b6` |

> Note: Automation and Webhooks & API categories were intentionally removed.

### Integrations (14 total)
**Email**: Gmail (connected), Outlook (connected), Custom SMTP  
**CRM**: HubSpot (connected), Salesforce, Pipedrive, Zoho CRM  
**Lead Sources**: CSV Import, Google Sheets (connected), Apollo.io (new)  
**Ads & Social**: Google Lead Forms (connected), Facebook Lead Ads, Instagram Leads, LinkedIn Lead Gen (new)

### Email Providers Section (Special)
The Email Providers section is **synced with `accountsData.ts`** at runtime:
- Gmail/Outlook connected status derived from real `ACCOUNTS` data
- Shows actual account emails as description when connected
- Shows account count badge
- Shows real `lastSync` time from account data
- Connect/Manage buttons open `EmailConnectModal` (same as Email Accounts page)

### CSV Import (Special)
CSV Import is **not a persistent connection** — it's a repeatable action:
- No status dot shown
- Always shows "Import CSV" button
- Opens shared `CSVImportModal`
- Shows total leads imported as a badge

### Stats Strip (Header)
3 stats: Connected count, Leads imported total, Automations fired total  
On mobile (xs): cards switch to column layout (icon stacked above number) to prevent overflow.

### Connect Flow (4-step modal)
1. Overview — what the integration does
2. Permissions — required access list + OAuth trust badge
3. Authenticate — OAuth redirect UI
4. Configure — sync preference toggles

### Manage Panel (slide-in from right)
- 3 stats: Leads in, Automations, Data flow direction
- Sync status table (last sync, frequency, health)
- Data control toggles (auto-sync, trigger automations, bidirectional)
- Smart system links (use in campaigns, trigger automation, view leads)
- Footer: Force sync + Disconnect buttons

### Data Model
```typescript
type IntegrationStatus = 'connected' | 'disconnected' | 'error' | 'syncing'
type CategoryId = 'email' | 'crm' | 'leads' | 'ads'
interface Integration {
  id, name, description, category, status, color, bgColor,
  popular?, new?, lastSync?, leadsImported?, automationsTriggered?, dataFlow?
}
```

---

## 17. Settings Page (`/dashboard/settings`)

**Components**: `SettingsPage`  
**Data**: `settingsData.ts`

### Layout
Left sidebar nav (200px, searchable) + right content area. On mobile: sidebar collapses to full-screen overlay triggered by menu button in top bar.

### Navigation (10 sections)
| Section | Color | Description |
|---------|-------|-------------|
| Profile | `#818cf8` | Name, photo, business info |
| Account | `#22d3ee` | Password, sessions, 2FA |
| Email Accounts | `#34d399` | Connected accounts, sync |
| AI Settings | `#c084fc` | Tone, behavior, instructions |
| Automation | `#fbbf24` | Rules, triggers, sequences |
| Notifications | `#f87171` | Alerts, digests, activity |
| Security | `#fb923c` | Access, audit log, tokens |
| Team | `#60a5fa` | Members, roles, permissions |
| Data & Privacy | `#a3e635` | Export, usage, deletion |
| About & Legal | `#94a3b8` | Version, terms, privacy |

### Design Pattern
- `Cluster` component: glassmorphism container grouping related fields
- `FieldRow`: label + control in a flex row with thin divider
- `EditField`: inline input with focus border animation + password show/hide
- `PillToggle`: segmented control for multi-option settings
- `GlowChip`: colored status badge with glow
- `SectionHead`: icon box + title + subtitle

### Key Sections

**Profile**: Avatar with edit overlay, identity fields (name, email, title), business fields (company, industry, website)

**Account**: Password change (3 fields with show/hide), 2FA toggle with status chip + setup CTA, Active sessions list with device/location/time + revoke buttons

**Email Accounts**: Connected accounts with health bars + default picker + delete, sync frequency pill toggle

**AI Settings**: Tone selector (5 options: Professional/Friendly/Concise/Persuasive/Empathetic), Automation level (Manual/Assist/Autopilot with badges), Custom instructions textarea, Behavior toggles

**Automation**: Global master switch, weekend pause, sending hours, 4 automation rules with per-rule toggles, sequence defaults (delay, stop-on-reply, max emails)

**Security**: Access control (2FA requirement, SSO, IP allowlist), API key management, Audit log with status dots

**Data & Privacy**: Usage toggles, export actions (leads/campaigns/logs), Danger Zone with delete account confirmation modal

**About**: Platform version, AI model badge (GPT-4o), data region, legal links grid (6 items)

---

## 18. Billing Page (`/dashboard/billing`)

**Components**: `BillingPage`  
**Data**: `billingData.ts`

### Layout
Single scrollable column with sections stacked vertically. No fixed headers.

### Sections

**Billing Alerts** (conditional): Auto-detects usage stats ≥80% and shows colored warning strips with upgrade CTA. Color: amber at 80%, red at 95%.

**Current Plan Card**: Gradient background with decorative blur orb, plan name + price, status/billing cycle/next billing date rows, Change Plan + Cancel buttons.

**Cost Insights** (2×2 grid): Estimated next bill, Avg monthly spend, Cost per lead, Cost per email — each with trend arrow (up/down).

**Usage & Limits**: 6 animated progress bars. Bar color: normal → amber at 80% → red at 95%.

**Payment Methods**: Card list with brand/last4/expiry, default badge, delete button, Add card button.

**Invoice History**: 
- Desktop: 4-column grid table (Description / Date / Amount+Status / PDF download)
- Mobile: stacked row (description+date+id on left, amount+status+download on right)

**Plan Change Modal**: 3-plan selector (Starter $29 / Pro $79 / Business $199), feature previews, current/popular badges, success confirmation with pop-in animation.

### Subscription Plans
```typescript
Starter: $29/mo — 2,000 emails, 500 leads, 1 account, Basic AI
Pro:     $79/mo — 10,000 emails, 5,000 leads, 5 accounts, Advanced AI, CRM, Analytics
Business: $199/mo — 50,000 emails, Unlimited leads, 20 accounts, Full AI, Priority support
```

### Usage Limits (Pro plan defaults)
| Resource | Used | Limit |
|----------|------|-------|
| Emails Sent | 7,240 | 10,000 |
| Leads | 3,180 | 5,000 |
| Email Accounts | 3 | 5 |
| AI Replies | 1,840 | 3,000 |
| Campaigns | 8 | 20 |
| Team Members | 4 | 10 |

---

## 19. Help & Support Page (`/dashboard/help`)

**Components**: `HelpPage`  
**Data**: `helpData.ts`

### Layout
Scrollable page. Hero section → content area (full width, no maxWidth constraint on mobile).

### Sections

**Hero**: Gradient background (indigo → purple), decorative blur orbs, "AI-Powered Support" badge chip, "How can we help you?" heading with gradient text.

**Browse by Category** (6 tiles, responsive grid 2→3→6 cols): Getting Started, Campaigns & Automation, Inbox & Emails, Leads & Data, Integrations, Account & Settings. Hover: lift + glow + color fill.

**Popular Articles** (list rows): Article icon, title (truncated), reads + read time, Popular chip (hidden on xs), chevron. Hover: slide right + title color change.

**Video Tutorials** (2→4 col grid): Colored thumbnail with play icon, title (2-line clamp), duration.

**AI Assistant Panel** (fixed 420px height, internal scroll):
- Gradient header with "Online" chip
- Chat bubbles (user right / AI left)
- Typing indicator (3 bouncing dots)
- Quick prompt chips (4 options)
- Input + send button
- Keyword-matched AI responses (campaign/gmail/import/open rate/default)
- Scroll scoped to messages container only (does NOT scroll the page)

**My Tickets** (list): Status dot, subject (truncated), status chip + time, Submit new ticket button.

**System Status** (list): 4 services (API, Email Sending, AI Engine, Webhooks), colored dot + label + status chip + uptime %. Webhooks currently degraded.

**Contact Support** (3 option rows): Live Chat (Online badge), Email Support, Submit Ticket → opens `TicketModal`.

**Ticket Modal**: Subject + details inputs, send button (disabled until both filled), success state with check animation, trust indicator row.

### AI Response Logic
```typescript
// Keyword matching:
'campaign' | 'paused'        → campaign pause explanation
'gmail' | 'sync'             → Gmail reconnect steps
'import' | 'csv'             → CSV import instructions
'open rate' | 'deliverability' → deliverability tips
default                      → generic help response
```

### Mobile Fixes Applied
- Root: `overflowX: hidden, width: 100%`
- Hero: `width: 100%, boxSizing: border-box`
- Hero inner: `maxWidth: { xs: '100%, md: 640 }, mx: { xs: 0, md: auto }`
- Content wrapper: `width: 100%, boxSizing: border-box` (no `maxWidth: 1200, mx: auto`)
- AI panel: `width: 100%, boxSizing: border-box`
- Video cards: `minWidth: 0`
- Popular chip: hidden on xs (`display: { xs: none, sm: flex }`)
- System status: no `minWidth: 48` on uptime, `minWidth: 0` on label

---

## 20. Shared Components

### CSVImportModal (`components/shared/CSVImportModal.tsx`)

Shared between Leads page and Integrations page (CSV Import row).

**Props**: `{ open: boolean; onClose: () => void }`

**Internal state**: `step: 'upload' | 'loading' | 'done'`, `file`, `progress`, `processed`, `timer ref`

**Steps**:
1. **Upload**: Drag-and-drop zone + file input, required columns (`email`, `first_name`, `last_name`), recent import history (3 entries)
2. **Loading**: File info card, animated progress bar with glow, processed rows counter, 4-step checklist with pulse/check animations, spinner footer button
3. **Done**: Pop-in check icon, success message with filename, 3-stat grid (Imported/Duplicates/Skipped), "Import another" + "View leads" buttons

**"View leads"** uses `useRouter().push('/dashboard/leads')` — navigates to leads page after import.

**Simulated import**: `setInterval` at 110ms increments, random progress steps, auto-completes to done state after 350ms delay at 100%.

---

## 21. Routing Map

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Landing page sections | Public marketing page |
| `/sign-in` | `SignInPage` | Authentication |
| `/sign-up` | `SignUpPage` | 6-step onboarding |
| `/dashboard` | Dashboard widgets | Home overview |
| `/dashboard/inbox` | `InboxView` | Chat-based email inbox |
| `/dashboard/campaigns` | `CampaignsPage` | Campaign management |
| `/dashboard/leads` | `LeadsPage` | Lead pipeline + CSV import |
| `/dashboard/accounts` | `EmailAccountsPage` | Email account management |
| `/dashboard/automation` | `AutomationPage` | Automation workflows |
| `/dashboard/research` | `ResearchPage` | AI research tool |
| `/dashboard/my-data` | `MyDataPage` | Business knowledge base |
| `/dashboard/analytics` | `AnalyticsPage` | Charts + AI insights |
| `/dashboard/team` | `TeamPage` | Team RBAC management |
| `/dashboard/integrations` | `IntegrationsPage` | Integration marketplace |
| `/dashboard/settings` | `SettingsPage` | System control panel |
| `/dashboard/billing` | `BillingPage` | Subscription + invoices |
| `/dashboard/help` | `HelpPage` | Help center + AI assistant |

---

## 22. Common UI Patterns

### Animated Counter (CountUp)
Used across Dashboard, Analytics, Team, Billing, Integrations. Cubic easing over ~900ms using `requestAnimationFrame`. Supports decimals and suffix strings.

### GlowChip
Inline colored badge: `FiberManualRecordRoundedIcon` (dot) + label text. Used for status indicators, plan badges, popular/new tags.

### Progress Bars
Used in Email Accounts (daily usage) and Billing (usage limits). Color shifts: normal → amber at 60-80% → red at 85-95%. Animated width transition.

### Glassmorphism Containers
```css
background: linear-gradient(145deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.4) 100%)
backdropFilter: blur(12px)
border: 1px solid rgba(255,255,255,0.07)
```

### Slide-in Panels
Used in My Data (EntryPanel), Team (EditMemberPanel), Integrations (ManagePanel). Fixed position right side, `transform: translateX(0/100%)` with cubic-bezier transition. Backdrop blur overlay.

### Section Heads
Two variants:
1. Colored left-bar (3px) + title + subtitle (Settings, Billing)
2. Icon box + title + subtitle (Integrations, Help)

### Responsive Mobile Fixes (Applied Globally)
All scrollable page roots use:
```typescript
sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0, width: '100%' }}
```
Content wrappers use `width: '100%', boxSizing: 'border-box'` instead of `maxWidth + mx: auto` on mobile.

---

## 23. Data Fetching Architecture (TanStack Query)

### 23.1 Overview

The app uses **TanStack Query v5** (React Query) for all server state management. This provides:
- ⚡ Smart caching (5min stale time, 10min cache retention)
- 🔄 Automatic background refetch
- 🧠 Optimistic updates
- 💰 Cost-optimized API calls (70%+ reduction)
- 🚀 Real-time-like UX

### 23.2 Architecture Layers

**1. QueryClient Configuration** (`lib/react-query/queryClient.ts`)
```typescript
staleTime: 5 * 60 * 1000        // 5 minutes
gcTime: 10 * 60 * 1000          // 10 minutes cache
retry: 1                         // Single retry
refetchOnWindowFocus: false      // Cost optimization
refetchOnReconnect: true         // Network recovery
```

**2. API Client** (`services/apiClient.ts`)
- Axios instance with base URL
- Auth token injection via interceptors
- Global error handling
- Request/response transformation

**3. Endpoint Modules** (`services/endpoints/`)
- One file per domain (campaigns, leads, inbox, etc.)
- Pure functions returning Promises
- Type-safe request/response interfaces

**4. Query Keys** (`lib/react-query/queryKeys.ts`)
- Centralized key factory
- Hierarchical structure: `['campaigns']`, `['campaigns', id]`
- Type-safe and predictable

**5. Query Hooks** (`hooks/queries/`)
- Read operations (GET)
- Automatic caching and background sync
- Loading/error states
- Pagination support

**6. Mutation Hooks** (`hooks/mutations/`)
- Write operations (POST/PUT/DELETE)
- Optimistic updates
- Auto cache invalidation
- Error rollback

### 23.3 Usage Pattern

**Fetching data**:
```typescript
import { useCampaigns } from '@/hooks/queries';

const { data, isLoading, error } = useCampaigns();
```

**Mutating data**:
```typescript
import { useCreateCampaign } from '@/hooks/mutations';

const createCampaign = useCreateCampaign();

await createCampaign.mutateAsync({
  name: 'Q1 Outreach',
  template: 'cold-email'
});
// Cache automatically invalidated
```

### 23.4 Cache Invalidation Strategy

Mutations automatically invalidate related queries:
```typescript
// After creating a campaign:
queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.all });

// After updating a lead:
queryClient.invalidateQueries({ queryKey: queryKeys.leads.all });
queryClient.invalidateQueries({ queryKey: queryKeys.leads.detail(leadId) });
```

### 23.5 DevTools

React Query DevTools enabled in development mode:
- Bottom-right corner toggle
- Query inspector
- Cache explorer
- Network timeline

### 23.6 Performance Optimizations

- **Prefetching**: Hover-triggered data loading
- **Pagination**: Chunked data loading
- **Infinite Scroll**: Seamless list expansion
- **Background Sync**: Silent updates
- **Memoization**: Stable query keys
- **Select**: Efficient data transformation

### 23.7 Supported Endpoints

| Domain | Queries | Mutations |
|--------|---------|----------|
| Campaigns | list, detail, stats | create, update, delete, pause |
| Leads | list, detail, infinite | import, update, delete, export |
| Inbox | threads, messages | send, reply, archive |
| Analytics | dashboard, reports | - |
| Accounts | list, detail | connect, disconnect, sync |
| Team | members, activity | invite, update, remove |
| Integrations | list, status | connect, disconnect, sync |
| Billing | subscription, usage, invoices | updateSubscription, addPayment |
| Settings | profile, preferences | updateProfile, updatePreferences |
| Research | saved, results | save, delete |

### 23.8 Future Enhancements

- WebSocket integration for real-time updates
- GraphQL support via TanStack Query adapters
- Server-Sent Events for live notifications
- Offline-first with persistence plugin

---

## 24. Backend Architecture (Reference)

The backend is a Python FastAPI microservices system. The frontend communicates with it via REST APIs. Key services:

| Service | Port | Frontend Usage |
|---------|------|---------------|
| Gateway | 8000 | All API calls routed through |
| Auth | 8001 | Sign-in, sign-up, OAuth |
| Email | 8002 | Gmail/Outlook connect, send, sync |
| Business | 8003 | Business settings, My Data |
| User | 8004 | Profile management |
| Inbox | 8005 | Conversations, messages, replies |
| Campaign | 8006 | Campaign CRUD, sequences |
| Analytics | 8007 | Metrics, reports |
| Automation | 8008 | Rules, AI triggers |
| Leads | 8009 | Lead management, import |
| Research | 8010 | AI research queries |
| Notification | 8011 | Real-time alerts |

**Real-time**: Gmail Pub/Sub → Webhook → Reply Detection Engine → AI Response. Frontend currently uses manual refresh (SSE/WebSocket disabled for cost optimization).

---

## 25. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| No card-based layout on most pages | Rows + dividers feel more data-dense and professional |
| Non-card approach varies per page | Each page has a distinct visual identity while sharing the color system |
| CSV Import not a "connection" | Users import leads multiple times; no persistent connection state needed |
| Company not required in CSV | B2B and B2C flexibility — only email + first/last name required |
| Automation/Webhooks removed from Integrations | Simplified scope; these are handled internally |
| AI panel scroll scoped internally | Prevents page scroll hijacking when chatting with AI assistant |
| `overflowX: hidden` on all page roots | Prevents horizontal scroll on mobile from any child overflow |
| `width: 100%, boxSizing: border-box` on content wrappers | Replaces `maxWidth + mx: auto` which caused left-edge clipping on mobile |
| Sidebar bottom section separate from nav | Settings/Billing/Help are utility pages, not primary workflows |
| Dark mode sidebar: `rgba(15,10,40,0.85)` | Slightly purple-tinted dark for visual distinction from content area |

---

## 26. Changelog (Current Version)

### Pages Added Since Initial Build
- `/dashboard/settings` — Full system control panel (10 sections)
- `/dashboard/billing` — Subscription + usage + invoices
- `/dashboard/help` — AI-powered help center
- `/dashboard/integrations` — Integration marketplace

### Major Features Added
- Multi-step sign-up flow (6 steps)
- CSV Import Modal (shared, with loading animation)
- AI Assistant chat panel (Help page)
- Plan change modal with confirmation flow
- Ticket submission modal
- Team RBAC with permission groups
- Analytics with visx charts (line, area, donut, horizontal bar)
- Billing alerts (auto-detects near-limit usage)
- Email Providers section synced with accountsData
- **TanStack Query v5 data layer** (enterprise-grade caching + mutations)
- **Centralized API client** (Axios with interceptors)
- **Query/Mutation hooks** for all 10 domains
- **Smart cache invalidation** (70%+ API call reduction)
- **React Query DevTools** (development only)

### Navigation Updates
- Sidebar bottom section: Settings + Billing + Help & Support
- Mobile drawer mirrors desktop sidebar exactly (same sections, badges, bottom items)

### Mobile Fixes Applied
- Help page: removed `maxWidth: 1200, mx: auto` content wrapper
- Integrations page: stats strip switches to column layout on xs
- Billing page: invoice table has mobile-specific stacked row layout
- All pages: `overflowX: hidden` on scroll roots
