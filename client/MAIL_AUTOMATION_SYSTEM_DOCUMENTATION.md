# MailFlowAI — Complete Client-Side Architecture Documentation

> Last updated: March 2026 — reflects full current frontend implementation including React Query data layer

---

## 1. Executive Summary

**MailFlowAI** is an enterprise-grade AI-powered mail automation SaaS. The frontend is a Next.js 14 App Router application with Material UI v5, TypeScript, TanStack Query v5, Axios, and a fully custom design system. It provides a complete dashboard for email outreach, lead pipelines, AI automation, analytics, team collaboration, integrations, billing, and support — all backed by a real API data layer.

**Product name**: MailFlowAI  
**Backend gateway**: `http://localhost:8000` (configurable via `NEXT_PUBLIC_API_URL`)

---

## 2. Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| UI Library | Material UI v5 (MUI) |
| Styling | MUI `sx` prop + Emotion |
| Data Fetching | TanStack Query v5 (`@tanstack/react-query`) |
| HTTP Client | Axios (centralized `apiClient`) |
| Charts | `@visx` + `d3-shape` |
| Theme | Custom dual-mode MUI theme (light + dark) |
| Auth State | Custom `AuthContext` (localStorage-based JWT) |
| Icons | Material Icons Rounded |

---

## 3. Project Structure

```
client/
├── src/
│   ├── app/                          # Next.js App Router pages
│   │   ├── layout.tsx                # Root: QueryProvider > AppThemeProvider > AuthProvider
│   │   ├── page.tsx                  # Landing page (/)
│   │   ├── sign-in/page.tsx
│   │   ├── sign-up/page.tsx
│   │   └── dashboard/
│   │       ├── layout.tsx            # Dashboard shell (Sidebar + TopBar)
│   │       ├── page.tsx
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
│   ├── components/                   # UI components (see Section 8)
│   ├── contexts/
│   │   └── AuthContext.tsx           # JWT session state (no API calls)
│   ├── hooks/
│   │   ├── queries/                  # React Query read hooks
│   │   └── mutations/                # React Query write hooks
│   ├── lib/
│   │   └── react-query/
│   │       ├── queryClient.ts        # Global QueryClient config
│   │       ├── queryKeys.ts          # Centralized key factory
│   │       └── provider.tsx          # QueryProvider + DevTools
│   ├── services/
│   │   ├── apiClient.ts              # Axios instance + interceptors
│   │   └── endpoints/               # Per-resource API modules
│   ├── providers/
│   │   └── AppThemeProvider.tsx
│   ├── theme/                        # MUI design system
│   └── styles/
```

---

## 4. Provider Stack (Root Layout)

```tsx
// app/layout.tsx
<QueryProvider>           // TanStack Query — server state
  <AppThemeProvider>      // MUI theme (light/dark toggle)
    <AuthProvider>        // JWT session state
      {children}
    </AuthProvider>
  </AppThemeProvider>
</QueryProvider>
```

**Order matters**: `QueryProvider` is outermost so mutations inside `AuthProvider` can use `useQueryClient()`.

---

## 5. Data Layer Architecture

### 5.1 QueryClient Configuration (`lib/react-query/queryClient.ts`)

Single global instance with enterprise-tuned defaults:

| Setting | Value | Rationale |
|---------|-------|-----------|
| `staleTime` | 5 min | Dashboard data doesn't change second-by-second |
| `gcTime` | 30 min | Keep cache in memory for instant back-navigation |
| `retry` | 1 | One retry on transient errors; surface persistent errors fast |
| `refetchOnWindowFocus` | false | Prevents API burst on alt-tab — critical for cost optimization |
| `refetchOnReconnect` | true | Refresh stale data when user comes back online |
| `refetchOnMount` | true | Always check staleness on component mount |
| Mutation `retry` | 0 | Mutations never auto-retry — UI handles it |

### 5.2 Query Key Factory (`lib/react-query/queryKeys.ts`)

Centralized, typed key factory. **Never inline strings in `useQuery` calls.**

```typescript
queryKeys.campaigns.all()              // ['campaigns']
queryKeys.campaigns.detail(id)         // ['campaigns', id]
queryKeys.leads.list(params)           // ['leads', 'list', params]
queryKeys.inbox.thread(threadId)       // ['inbox', 'thread', threadId]
queryKeys.analytics.overview(range)    // ['analytics', 'overview', range]
queryKeys.accounts.all()               // ['accounts']
queryKeys.team.members()               // ['team', 'members']
queryKeys.integrations.all()           // ['integrations']
queryKeys.billing.overview()           // ['billing', 'overview']
queryKeys.billing.invoices()           // ['billing', 'invoices']
queryKeys.billing.paymentMethods()     // ['billing', 'payment-methods']
queryKeys.settings.all()               // ['settings']
// Research uses inline keys: ['research', 'history', params], ['research', id]
```

### 5.3 API Client (`services/apiClient.ts`)

Centralized Axios instance. **All hooks must use this — never raw fetch/axios in components.**

**Base URL**: `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`

**Request interceptor — JWT attachment**:
1. Tries `auth_tokens` key in localStorage (new `AuthContext` format) → extracts `access_token`
2. Falls back to `mailflow_token` key (legacy format)
3. Attaches as `Authorization: Bearer <token>`

**Response interceptor — error normalization**:
- Normalizes all errors to `{ message, status, code }` shape
- On 401: clears all auth keys (`auth_tokens`, `auth_user`, `auth_token_expiry`, `mailflow_token`) and redirects to `/sign-in`

**Typed helpers**: `get<T>()`, `post<T,B>()`, `put<T,B>()`, `patch<T,B>()`, `del<T>()`

---

## 6. Service Endpoints (`services/endpoints/`)

Each file is a pure API module — no React, no hooks, just typed functions using `apiClient`.

### 6.1 `email.ts` — Email Connection (Primary)

**Backend**: `POST /email-service/email/connect`

```typescript
type EmailProvider       = 'gmail' | 'outlook' | 'smtp'
type EmailConnectionType = 'oauth' | 'manual'
type ConnectionStatus    = 'connected' | 'disconnected' | 'error'
type SyncStatus          = 'idle' | 'syncing' | 'failed'

interface ConnectEmailPayload {
  provider: EmailProvider
  connection_type: EmailConnectionType
  email?: string
  credentials: {
    code?: string           // OAuth
    code_verifier?: string  // PKCE (Outlook)
    smtp_host?: string      // SMTP
    smtp_port?: number
    username?: string
    password?: string
    smtp_use_tls?: boolean
    imap_host?: string
    imap_port?: number
  }
}

interface EmailAccountFull {
  id, user_id, email_address, display_name, provider,
  connection_status, sync_status,
  daily_send_limit, daily_sent_count,
  warmup_enabled, is_active, is_primary, automation_enabled,
  last_synced_at, last_error_message, created_at, updated_at
}
```

`emailApi.connect()` → `POST /email-service/email/connect`  
`emailApi.listAccounts()` → `GET /email-service/email/accounts`

### 6.2 `accounts.ts` — Account Management

Delegates to real `/email-service/email/accounts` endpoints. Re-exports `EmailAccountFull` as `EmailAccount` for backwards compatibility.

```
accountsApi.list()          GET  /email-service/email/accounts
accountsApi.get(id)         GET  /email-service/email/accounts/:id
accountsApi.update(id, data) PATCH /email-service/email/accounts/:id
accountsApi.sync(id)        POST /email-service/email/accounts/:id/sync
accountsApi.delete(id)      DELETE /email-service/email/accounts/:id
```

### 6.3 `campaigns.ts`
```
campaignsApi.list()         GET    /campaigns
campaignsApi.get(id)        GET    /campaigns/:id
campaignsApi.create(p)      POST   /campaigns
campaignsApi.update(id,p)   PATCH  /campaigns/:id
campaignsApi.delete(id)     DELETE /campaigns/:id
campaignsApi.pause(id)      PATCH  /campaigns/:id/pause
campaignsApi.resume(id)     PATCH  /campaigns/:id/resume
```

### 6.4 `leads.ts`
Supports pagination: `{ page, limit, status, search, campaign }` params.  
Import: `POST /leads/import` with `multipart/form-data`.

### 6.5 `inbox.ts`
```
inboxApi.conversations(params)  GET  /inbox/conversations
inboxApi.thread(threadId)       GET  /inbox/conversations/:id
inboxApi.sendReply(payload)     POST /inbox/reply
inboxApi.markRead(threadId)     POST /inbox/conversations/:id/read
```

### 6.6 `analytics.ts`
```
analyticsApi.overview(range)    GET /analytics/overview?range=7d|30d|90d
analyticsApi.campaigns()        GET /analytics/campaigns
analyticsApi.accounts()         GET /analytics/accounts
```

### 6.7 `team.ts`
```
teamApi.list()              GET    /team/members
teamApi.invite(p)           POST   /team/invite
teamApi.update(id,p)        PATCH  /team/members/:id
teamApi.remove(id)          DELETE /team/members/:id
teamApi.activity()          GET    /team/activity
```

### 6.8 `integrations.ts`
```
integrationsApi.list()          GET    /integrations
integrationsApi.connect(p)      POST   /integrations/connect
integrationsApi.update(id,p)    PATCH  /integrations/:id
integrationsApi.disconnect(id)  DELETE /integrations/:id
integrationsApi.sync(id)        POST   /integrations/:id/sync
```

### 6.9 `billing.ts`
```
billingApi.overview()           GET   /billing/overview
billingApi.invoices()           GET   /billing/invoices
billingApi.paymentMethods()     GET   /billing/payment-methods
billingApi.changePlan(planId)   POST  /billing/change-plan
billingApi.addPaymentMethod(t)  POST  /billing/payment-methods
billingApi.setDefault(pmId)     PATCH /billing/payment-methods/:id/default
billingApi.cancelPlan()         POST  /billing/cancel
```

### 6.10 `settings.ts`
```
settingsApi.getSettings()       GET   /user-service/settings
settingsApi.updateSettings(d)   PATCH /user-service/settings
settingsApi.resetSettings()     POST  /user-service/settings/reset
```

Full `UserSettings` interface covers: email sync, AI behavior, automation rules, notification preferences, security (2FA), team workspace, data/privacy toggles.

### 6.11 `research.ts`
```
researchApi.list(params)    GET  /research
researchApi.get(id)         GET  /research/:id
researchApi.run(query)      POST /research
researchApi.delete(id)      POST /research/:id/delete
```

### 6.12 `auth.ts`
```
authApi.sendOtp(p)          POST /auth-service/auth/send-otp
authApi.verifyOtp(p)        POST /auth-service/auth/verify-otp
authApi.login(p)            POST /auth-service/auth/login
authApi.signup(p)           POST /auth-service/auth/signup
authApi.getProfile()        GET  /auth-service/auth/me
authApi.refreshToken(p)     POST /auth-service/auth/refresh
authApi.logout(p)           POST /auth-service/auth/logout
```

---

## 7. Query Hooks (`hooks/queries/`)

All hooks use `queryKeys` factory. **Never call API functions directly in components.**

### Stale Time Strategy

| Hook | staleTime | refetchInterval | Rationale |
|------|-----------|-----------------|-----------|
| `useAccounts` | 2 min | — | Connection status changes frequently |
| `useConversations` | 30s | 60s | Inbox needs near-real-time updates |
| `useThread` | 30s | 30s | Active thread polls every 30s |
| `useLeads` | 3 min | — | Lead data is moderately dynamic |
| `useCampaigns` | 5 min | — | Campaign stats update periodically |
| `useTeamMembers` | 5 min | — | Team changes are infrequent |
| `useTeamActivity` | 2 min | 2 min | Activity feed refreshes every 2 min |
| `useAnalyticsOverview` | 10 min | — | Historical data rarely changes |
| `useIntegrations` | 10 min | — | Integration status rarely changes |
| `useBillingOverview` | 10 min | — | Billing data is stable |
| `useInvoices` | 30 min | — | Invoices are immutable history |
| `useUserSettings` | 15 min | — | Settings rarely change |
| `useResearchQuery` | — | 3s (until done) | Polls until status = done/failed |

### Select Transforms

Hooks use `select` to derive filtered views from a single cache entry:

```typescript
// useAccounts — one cache entry, multiple derived views
{ all, connected, error, active, gmail, outlook, smtp, totalSentToday }

// useCampaigns
{ all, running, paused, draft }

// useConversations
{ all, unread, aiHandled, replied }

// useTeamMembers
{ all, active, invited, suspended, owners, admins, members }

// useIntegrations
{ all, connected, disconnected, byCategory }

// useAnalyticsKPI / useAnalyticsSeries — same cache, different select
// All 3 time ranges (7d/30d/90d) cached simultaneously (gcTime: 1 hour)
```

### Pagination

`useLeads(params)` — paginated with `placeholderData: prev` (no loading flash on page change).  
`useLeadsInfinite(params)` — infinite scroll variant, 20 items per page.  
`useResearchHistory(params)` — paginated research history.

---

## 8. Mutation Hooks (`hooks/mutations/`)

### 8.1 `useEmailMutations.ts`

**`useConnectEmail()`** — unified email provider connection:
- Calls `POST /email-service/email/connect`
- Accepts `ConnectEmailPayload` (Gmail OAuth, Outlook OAuth, or SMTP)
- On success: invalidates `accounts.all()` + `integrations.all()`
- Used in: `EmailAccountsPage` ConnectModal, `IntegrationsPage` EmailConnectModal, `Step5Email` signup step

### 8.2 `useAccountMutations.ts`

| Hook | Optimistic? | Invalidates |
|------|-------------|-------------|
| `useToggleAutomation` | ✅ Yes | `accounts.all()` |
| `useToggleActive` | ✅ Yes | `accounts.all()` |
| `useSyncAccount` | No | `accounts.all()` |
| `useDeleteAccount` | ✅ Yes (removes from list) | `accounts.all()` |

All optimistic mutations: cancel in-flight queries → snapshot prev → update cache → rollback on error → invalidate on settle.

### 8.3 `useCampaignMutations.ts`

| Hook | Optimistic? |
|------|-------------|
| `useCreateCampaign` | ✅ Adds placeholder to list |
| `useUpdateCampaign` | ✅ Updates detail cache |
| `useDeleteCampaign` | ✅ Removes from list |
| `usePauseCampaign` | ✅ Sets status = 'paused' |
| `useResumeCampaign` | ✅ Sets status = 'running' |

### 8.4 `useLeadMutations.ts`

| Hook | Notes |
|------|-------|
| `useCreateLead` | Invalidates `leads.all()` |
| `useUpdateLead` | Optimistic on detail cache |
| `useDeleteLead` | Invalidates `leads.all()` |
| `useImportLeads` | Sends `FormData`, invalidates `leads.all()` on success |

### 8.5 `useInboxMutations.ts`

**`useSendReply()`** — optimistic: appends message to thread immediately, rolls back on error.  
**`useMarkRead()`** — optimistic: zeros unread count on conversation list.

### 8.6 `useSettingsMutations.ts`

**`useUpdateSettings()`** — optimistic update with full rollback. Invalidates `settings.all()` on success.  
**`useResetSettings()`** — sets cache directly with reset data from server.

### 8.7 `useAuthMutations.ts`

Pure React Query mutations — no side effects. `AuthContext` handles token storage.

| Hook | Endpoint |
|------|---------|
| `useSendOtp` | POST /auth-service/auth/send-otp |
| `useVerifyOtp` | POST /auth-service/auth/verify-otp |
| `useLogin` | POST /auth-service/auth/login |
| `useSignup` | POST /auth-service/auth/signup |
| `useGetProfile` | GET /auth-service/auth/me |
| `useRefreshToken` | POST /auth-service/auth/refresh |
| `useLogout` | POST /auth-service/auth/logout |

### 8.8 Other Mutation Hooks

`useTeamMutations` — invite, update (optimistic), remove (optimistic)  
`useBillingMutations` — changePlan, addPaymentMethod, setDefault, cancelPlan  
`useIntegrationMutations` — connect, update, disconnect, sync  
`useProfileMutations` — updateProfile, uploadAvatar  
`useResearchMutations` — runQuery (polls via `useResearchQuery` until done)

---

## 9. Authentication Architecture

### 9.1 Separation of Concerns

```
React Query mutations  →  API calls (login, signup, refresh, logout)
AuthContext            →  Client state only (user, tokens, auth status)
apiClient interceptor  →  JWT attachment on every request
```

### 9.2 Token Storage (localStorage)

| Key | Content |
|-----|---------|
| `auth_tokens` | `{ access_token, refresh_token, expires_in, token_type }` |
| `auth_user` | Serialized `User` object |
| `auth_token_expiry` | Unix timestamp (ms) of access token expiry |
| `mailflow_token` | Legacy fallback (still supported by apiClient) |

### 9.3 AuthContext Features

- **Initialization**: Reads localStorage on mount, validates token expiry, restores session synchronously
- **Route protection**: Redirects unauthenticated users from `/dashboard/*` to `/sign-in`; redirects authenticated users from `/` to `/dashboard`
- **`setAuthData(user, tokens)`**: Called after successful login/signup to persist session
- **`clearAuth()`**: Clears all storage keys, resets state
- **`isTokenExpired()`**: Checks `auth_token_expiry` against `Date.now()`

### 9.4 Public Routes

`/`, `/sign-in`, `/sign-up` — no auth required.

---

## 10. Email Connection Integration

### 10.1 Flow

```
User clicks "Connect Gmail"
  → useConnectEmail.mutate({ provider: 'gmail', connection_type: 'oauth', credentials: {} })
  → POST /email-service/email/connect
  → On success: invalidate ['accounts'] + ['integrations']
  → EmailAccountsPage refetches → shows new account
  → IntegrationsPage EmailProviderSection refetches → shows connected status
```

### 10.2 Where `useConnectEmail` is Used

1. **`EmailAccountsPage` ConnectModal** — OAuth tab (Gmail/Outlook) + SMTP tab
2. **`IntegrationsPage` EmailConnectModal** — same modal, same mutation
3. **`Step5Email` (signup step 5)** — optional email connection during onboarding

### 10.3 EmailProviderSection (IntegrationsPage)

Synced with real account data via `useAccounts()`:
- Gmail/Outlook connected status derived from `connection_status === 'connected'`
- Account count badge from actual account list
- Email addresses shown as description when connected
- Last sync time from `last_synced_at` field
- Connect/Manage buttons both open `EmailConnectModal`

### 10.4 EmailAccountsPage Real Data

Uses `useAccounts()` for data, `useToggleAutomation` / `useSyncAccount` / `useDeleteAccount` for mutations. Shows:
- Loading skeleton (3 placeholder cards)
- Error state with warning icon
- Empty state with connect CTA
- Real `EmailAccountFull` data: `email_address`, `connection_status`, `sync_status`, `daily_send_limit`, `daily_sent_count`, `warmup_enabled`, `automation_enabled`, `last_synced_at`, `last_error_message`

---

## 11. Design System

### 11.1 Theme

Dual-mode MUI theme. `AppThemeProvider` + `useThemeMode()` hook.

**Dark mode backgrounds**: `#080d18` (root) → `#0f172a` (default) → `#1e293b` (paper)  
**Sidebar dark**: `rgba(15,10,40,0.85)` with `backdropFilter: blur(16px)`

**Brand colors**:
- Light primary: `#4338ca` | Dark primary: `#818cf8`
- Accent palette: `#818cf8` (indigo), `#c084fc` (purple), `#34d399` (green), `#22d3ee` (cyan), `#fbbf24` (amber), `#f87171` (red), `#f472b6` (pink)

**Gradients**:
- `lightGradients.primary = 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)'`
- `darkGradients.primary  = 'linear-gradient(135deg, #818cf8 0%, #a78bfa 100%)'`

### 11.2 Design Patterns

- **Non-card approach**: Rows + thin dividers + glassmorphism containers
- **Glassmorphism**: `backdropFilter: blur(12px)` + semi-transparent gradient backgrounds
- **Glow effects**: `boxShadow: 0 0 Xpx alpha(color, 0.4)` on active states
- **Micro-animations**: `fadeDown`, `fadeUp`, `popIn`, `pulse`, `spin` keyframes inline in `sx`
- **Mobile-first**: `xs/sm/md/lg` breakpoints, `overflowX: hidden` on all scroll roots

---

## 12. Navigation Structure

### 12.1 Sidebar (Desktop, 220px)

**Main sections**:
1. Dashboard, Inbox (badge: 12)
2. **Outreach**: Campaigns, Leads, Email Accounts
3. **Intelligence**: Automation, Research, My Data
4. **Insights**: Analytics, Notifications (badge: 3)
5. **Workspace**: Team, Integrations

**Bottom section** (separated):
- Settings → `/dashboard/settings`
- Billing → `/dashboard/billing` (accent: `#34d399`)
- Help & Support → `/dashboard/help` (accent: `#fbbf24`)

### 12.2 TopBar (Mobile)

Mirrors sidebar exactly — same 5 sections, same badges, same bottom items. Full-screen `Drawer` overlay.

---

## 13. Page-by-Page Summary

| Route | Data Source | Key Hooks |
|-------|-------------|-----------|
| `/dashboard` | Mock widgets | — |
| `/dashboard/inbox` | `inboxApi` | `useConversations`, `useSendReply`, `useMarkRead` |
| `/dashboard/campaigns` | `campaignsApi` | `useCampaigns`, `useCreateCampaign`, `usePauseCampaign` |
| `/dashboard/leads` | `leadsApi` | `useLeads`, `useLeadsInfinite`, `useImportLeads` |
| `/dashboard/accounts` | `accountsApi` + `emailApi` | `useAccounts`, `useConnectEmail`, `useToggleAutomation`, `useSyncAccount`, `useDeleteAccount` |
| `/dashboard/analytics` | `analyticsApi` | `useAnalyticsOverview`, `useAnalyticsKPI`, `useAnalyticsSeries` |
| `/dashboard/team` | `teamApi` | `useTeamMembers`, `useTeamActivity`, `useInviteMember`, `useUpdateMember` |
| `/dashboard/integrations` | `integrationsApi` + `accountsApi` | `useIntegrations`, `useAccounts`, `useConnectEmail` |
| `/dashboard/settings` | `settingsApi` | `useUserSettings`, `useUpdateSettings` |
| `/dashboard/billing` | `billingApi` | `useBillingOverview`, `useInvoices`, `usePaymentMethods` |
| `/dashboard/help` | Static + AI chat | — |
| `/dashboard/research` | `researchApi` | `useResearchHistory`, `useResearchQuery`, `useRunResearch` |
| `/dashboard/my-data` | Static mock | — |
| `/dashboard/automation` | Static mock | — |

---

## 14. Shared Components

### CSVImportModal (`components/shared/CSVImportModal.tsx`)

Shared between Leads page and Integrations page (CSV Import row).

**3-step flow**: Upload → Loading (animated progress, 4-step checklist) → Done (stats: Imported/Duplicates/Skipped)

**"View leads"** navigates to `/dashboard/leads` via `useRouter().push('/dashboard/leads')`.

Required columns: `email`, `first_name`, `last_name` (company excluded for B2B/B2C flexibility).

---

## 15. Routing Map

| Route | Component | Auth Required |
|-------|-----------|---------------|
| `/` | Landing page | No |
| `/sign-in` | `SignInPage` | No |
| `/sign-up` | `SignUpPage` (6 steps) | No |
| `/dashboard/*` | Dashboard shell | Yes |

**Sign-up steps**: Account → OTP → Business → AI Context → Email (optional) → Review

---

## 16. Backend Service Map

| Service | Port | Frontend Prefix |
|---------|------|----------------|
| Gateway | 8000 | All requests routed through |
| Auth | 8001 | `/auth-service/auth/*` |
| User | 8002 | `/user-service/*` |
| Email | 8004 | `/email-service/email/*` |
| Campaign | 8006 | `/campaigns/*` |
| Analytics | 8007 | `/analytics/*` |
| Leads | 8009 | `/leads/*` |
| Inbox | 8005 | `/inbox/*` |
| Team | — | `/team/*` |
| Integrations | — | `/integrations/*` |
| Billing | — | `/billing/*` |
| Research | 8010 | `/research/*` |

---

## 17. Key Architecture Rules

| Rule | Detail |
|------|--------|
| No direct API calls in components | Always use hooks |
| No inline query key strings | Always use `queryKeys` factory |
| No `refetchOnWindowFocus` | Disabled globally (cost optimization) |
| Optimistic updates on all write operations | Rollback on error |
| Cache invalidation is surgical | Only invalidate affected queries |
| Auth state = localStorage only | No API calls in `AuthContext` |
| JWT dual-key support | `auth_tokens` (new) + `mailflow_token` (legacy) |
| Mobile overflow prevention | `overflowX: hidden` + `width: 100%` on all scroll roots |

---

## 18. Changelog

### Added in Current Version
- **TanStack Query v5** full integration (`@tanstack/react-query`, `@tanstack/react-query-devtools`)
- **Axios** centralized API client with JWT interceptors and error normalization
- **`lib/react-query/`**: `queryClient.ts`, `queryKeys.ts`, `provider.tsx`
- **`services/endpoints/`**: 11 typed API modules (email, accounts, campaigns, leads, inbox, analytics, team, integrations, billing, settings, research, auth)
- **`hooks/queries/`**: 10 query hooks with smart stale times and select transforms
- **`hooks/mutations/`**: 13 mutation hook files with optimistic updates
- **`contexts/AuthContext.tsx`**: Lightweight JWT session manager (no API calls)
- **`useConnectEmail`**: Unified email provider connection mutation
- **`EmailAccountsPage`**: Fully migrated from mock data to real `useAccounts()` + mutation hooks
- **`IntegrationsPage` EmailProviderSection**: Synced with real `useAccounts()` data
- **`Step5Email`**: Wired to `useConnectEmail` for signup email connection
- **`QueryProvider` + `AuthProvider`** in root `layout.tsx`
- **ReactQueryDevtools** (dev mode only, bottom-right)
