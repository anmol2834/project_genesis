export type DataCategory =
  | 'products'
  | 'pricing'
  | 'offers'
  | 'business_hours'
  | 'meetings'
  | 'contacts'
  | 'company_info'
  | 'custom';

export type SourceType = 'csv_import' | 'google_sheets' | 'manual' | 'api' | 'crm_sync';
export type SourceStatus = 'connected' | 'syncing' | 'paused';
export type QualityLevel = 'high' | 'medium' | 'low';

export interface DataField {
  key: string;
  label: string;
  value: string;
  type: 'text' | 'number' | 'url' | 'email' | 'phone' | 'time' | 'date' | 'boolean' | 'list';
  aiRelevance: 'critical' | 'high' | 'medium' | 'low';
}

export interface DataEntry {
  id: string;
  title: string;
  category: DataCategory;
  sourceId: string;
  sourceName: string;
  sourceType: SourceType;
  fields: DataField[];
  qualityScore: number;
  missingFields: string[];
  usedIn: string[];
  updatedAt: string;
  accentColor: string;
}

export interface DataSource {
  id: string;
  name: string;
  type: SourceType;
  status: SourceStatus;
  records: number;
  lastSync: string;
  aiReadyPct: number;
  usedIn: string[];
}

export const CATEGORY_CONFIG: Record<DataCategory, {
  label: string; icon: string; color: string; description: string;
}> = {
  products:      { label: 'Products',       icon: 'inventory',    color: '#818cf8', description: 'Product catalog, features, specs' },
  pricing:       { label: 'Pricing',        icon: 'payments',     color: '#34d399', description: 'Plans, tiers, discounts, offers' },
  offers:        { label: 'Special Offers', icon: 'local_offer',  color: '#fbbf24', description: 'Promotions, deals, limited-time offers' },
  business_hours:{ label: 'Business Hours', icon: 'schedule',     color: '#22d3ee', description: 'Open/close times, holidays, availability' },
  meetings:      { label: 'Meetings',       icon: 'event',        color: '#c084fc', description: 'Booking slots, meeting types, availability' },
  contacts:      { label: 'Contacts',       icon: 'people',       color: '#f472b6', description: 'Team members, key contacts, roles' },
  company_info:  { label: 'Company Info',   icon: 'business',     color: '#fb923c', description: 'About, mission, values, location' },
  custom:        { label: 'Custom Data',    icon: 'tune',         color: '#a3e635', description: 'Any other business-specific data' },
};

export const SOURCE_TYPE_CONFIG: Record<SourceType, { label: string; color: string }> = {
  csv_import:    { label: 'CSV Import',    color: '#34d399' },
  google_sheets: { label: 'Google Sheets', color: '#60a5fa' },
  manual:        { label: 'Manual Entry',  color: '#c084fc' },
  api:           { label: 'API Sync',      color: '#22d3ee' },
  crm_sync:      { label: 'CRM Sync',      color: '#fbbf24' },
};

export const SOURCE_STATUS_CONFIG: Record<SourceStatus, { label: string; color: string; bg: string }> = {
  connected: { label: 'Connected', color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  syncing:   { label: 'Syncing',   color: '#60a5fa', bg: 'rgba(96,165,250,0.1)' },
  paused:    { label: 'Paused',    color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
};

export const QUALITY_CONFIG: Record<QualityLevel, { label: string; color: string; bg: string; darkBg: string }> = {
  high:   { label: 'High',   color: '#34d399', bg: 'rgba(52,211,153,0.1)',  darkBg: 'rgba(52,211,153,0.15)'  },
  medium: { label: 'Medium', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',  darkBg: 'rgba(251,191,36,0.15)'  },
  low:    { label: 'Low',    color: '#f87171', bg: 'rgba(248,113,113,0.1)', darkBg: 'rgba(248,113,113,0.15)' },
};

export function getQualityLevel(score: number): QualityLevel {
  if (score >= 75) return 'high';
  if (score >= 45) return 'medium';
  return 'low';
}

export const AI_RELEVANCE_CONFIG = {
  critical: { label: 'Critical for AI', color: '#f87171', dot: '#ef4444' },
  high:     { label: 'High impact',     color: '#fbbf24', dot: '#f59e0b' },
  medium:   { label: 'Medium impact',   color: '#818cf8', dot: '#6366f1' },
  low:      { label: 'Low impact',      color: '#64748b', dot: '#475569' },
};

export const DATA_SOURCES: DataSource[] = [
  { id: 's1', name: 'Manual Entry',       type: 'manual',        status: 'connected', records: 24, lastSync: '5m ago',     aiReadyPct: 96, usedIn: ['Q4 Enterprise Outreach'] },
  { id: 's2', name: 'Product Sheet',      type: 'google_sheets', status: 'syncing',   records: 18, lastSync: 'Syncing...', aiReadyPct: 82, usedIn: ['SaaS Decision Makers'] },
  { id: 's3', name: 'CRM Export',         type: 'csv_import',    status: 'connected', records: 41, lastSync: '1h ago',     aiReadyPct: 74, usedIn: ['Q4 Enterprise Outreach', 'Cold Outbound'] },
  { id: 's4', name: 'HubSpot Sync',       type: 'crm_sync',      status: 'connected', records: 89, lastSync: '10m ago',    aiReadyPct: 91, usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers', 'Cold Outbound'] },
  { id: 's5', name: 'Pricing API',        type: 'api',           status: 'paused',    records: 12, lastSync: '3h ago',     aiReadyPct: 65, usedIn: ['Cold Outbound'] },
];

export const DATA_ENTRIES: DataEntry[] = [
  // ── Products ──────────────────────────────────────────────────────────────
  {
    id: 'e1', title: 'MailFlowAI — Core Platform', category: 'products',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 95, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers'],
    updatedAt: '2h ago', accentColor: '#818cf8',
    fields: [
      { key: 'product_name',    label: 'Product Name',    value: 'MailFlowAI',                                    type: 'text',    aiRelevance: 'critical' },
      { key: 'tagline',         label: 'Tagline',         value: 'AI-powered cold email automation at scale',     type: 'text',    aiRelevance: 'critical' },
      { key: 'category',        label: 'Category',        value: 'B2B SaaS / Email Automation',                   type: 'text',    aiRelevance: 'high' },
      { key: 'key_features',    label: 'Key Features',    value: 'AI personalization, multi-inbox, smart replies, analytics', type: 'list', aiRelevance: 'critical' },
      { key: 'target_audience', label: 'Target Audience', value: 'Sales teams, SDRs, growth hackers, agencies',   type: 'text',    aiRelevance: 'high' },
      { key: 'website',         label: 'Website',         value: 'https://mailflowai.com',                        type: 'url',     aiRelevance: 'medium' },
    ],
  },
  {
    id: 'e2', title: 'Chrome Extension — Inbox Assistant', category: 'products',
    sourceId: 's2', sourceName: 'Product Sheet', sourceType: 'google_sheets',
    qualityScore: 78, missingFields: ['demo_url'], usedIn: ['SaaS Decision Makers'],
    updatedAt: '1d ago', accentColor: '#818cf8',
    fields: [
      { key: 'product_name',  label: 'Product Name',  value: 'MailFlowAI Chrome Extension',          type: 'text',    aiRelevance: 'critical' },
      { key: 'description',   label: 'Description',   value: 'One-click AI reply suggestions in Gmail & Outlook', type: 'text', aiRelevance: 'high' },
      { key: 'compatibility', label: 'Compatibility', value: 'Chrome 90+, Edge 90+',                 type: 'text',    aiRelevance: 'medium' },
      { key: 'installs',      label: 'Active Installs', value: '12,400+',                            type: 'number',  aiRelevance: 'medium' },
    ],
  },

  // ── Pricing ───────────────────────────────────────────────────────────────
  {
    id: 'e3', title: 'Starter Plan', category: 'pricing',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 98, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'Cold Outbound'],
    updatedAt: '30m ago', accentColor: '#34d399',
    fields: [
      { key: 'plan_name',    label: 'Plan Name',       value: 'Starter',                              type: 'text',    aiRelevance: 'critical' },
      { key: 'price',        label: 'Monthly Price',   value: '$29/month',                            type: 'text',    aiRelevance: 'critical' },
      { key: 'annual_price', label: 'Annual Price',    value: '$19/month (billed annually)',           type: 'text',    aiRelevance: 'critical' },
      { key: 'emails_limit', label: 'Emails / Month',  value: '2,000',                                type: 'number',  aiRelevance: 'high' },
      { key: 'inboxes',      label: 'Connected Inboxes', value: '3',                                  type: 'number',  aiRelevance: 'high' },
      { key: 'ai_credits',   label: 'AI Credits',      value: '500 / month',                          type: 'text',    aiRelevance: 'high' },
      { key: 'support',      label: 'Support',         value: 'Email support',                        type: 'text',    aiRelevance: 'medium' },
    ],
  },
  {
    id: 'e4', title: 'Pro Plan', category: 'pricing',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 98, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers'],
    updatedAt: '30m ago', accentColor: '#34d399',
    fields: [
      { key: 'plan_name',    label: 'Plan Name',       value: 'Pro',                                  type: 'text',    aiRelevance: 'critical' },
      { key: 'price',        label: 'Monthly Price',   value: '$79/month',                            type: 'text',    aiRelevance: 'critical' },
      { key: 'annual_price', label: 'Annual Price',    value: '$59/month (billed annually)',           type: 'text',    aiRelevance: 'critical' },
      { key: 'emails_limit', label: 'Emails / Month',  value: '15,000',                               type: 'number',  aiRelevance: 'high' },
      { key: 'inboxes',      label: 'Connected Inboxes', value: '15',                                 type: 'number',  aiRelevance: 'high' },
      { key: 'ai_credits',   label: 'AI Credits',      value: 'Unlimited',                            type: 'text',    aiRelevance: 'high' },
      { key: 'support',      label: 'Support',         value: 'Priority chat + email',                type: 'text',    aiRelevance: 'medium' },
      { key: 'extras',       label: 'Extras',          value: 'A/B testing, advanced analytics, team seats', type: 'list', aiRelevance: 'medium' },
    ],
  },
  {
    id: 'e5', title: 'Enterprise Plan', category: 'pricing',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 92, missingFields: ['custom_pricing_notes'], usedIn: ['Q4 Enterprise Outreach'],
    updatedAt: '1h ago', accentColor: '#34d399',
    fields: [
      { key: 'plan_name',    label: 'Plan Name',       value: 'Enterprise',                           type: 'text',    aiRelevance: 'critical' },
      { key: 'price',        label: 'Pricing',         value: 'Custom — contact sales',               type: 'text',    aiRelevance: 'critical' },
      { key: 'emails_limit', label: 'Emails / Month',  value: 'Unlimited',                            type: 'text',    aiRelevance: 'high' },
      { key: 'inboxes',      label: 'Connected Inboxes', value: 'Unlimited',                          type: 'text',    aiRelevance: 'high' },
      { key: 'sla',          label: 'SLA',             value: '99.9% uptime guarantee',               type: 'text',    aiRelevance: 'high' },
      { key: 'support',      label: 'Support',         value: 'Dedicated account manager + 24/7 support', type: 'text', aiRelevance: 'medium' },
    ],
  },

  // ── Special Offers ────────────────────────────────────────────────────────
  {
    id: 'e6', title: 'Q4 Holiday Deal — 40% Off Annual', category: 'offers',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 99, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'Cold Outbound'],
    updatedAt: '10m ago', accentColor: '#fbbf24',
    fields: [
      { key: 'offer_name',   label: 'Offer Name',      value: 'Q4 Holiday Special',                   type: 'text',    aiRelevance: 'critical' },
      { key: 'discount',     label: 'Discount',        value: '40% off all annual plans',             type: 'text',    aiRelevance: 'critical' },
      { key: 'promo_code',   label: 'Promo Code',      value: 'HOLIDAY40',                            type: 'text',    aiRelevance: 'critical' },
      { key: 'valid_until',  label: 'Valid Until',     value: 'December 31, 2025',                    type: 'date',    aiRelevance: 'critical' },
      { key: 'eligible',     label: 'Eligible Plans',  value: 'Starter, Pro (new signups only)',      type: 'text',    aiRelevance: 'high' },
      { key: 'cta',          label: 'CTA Message',     value: 'Lock in your rate before Dec 31',      type: 'text',    aiRelevance: 'high' },
    ],
  },
  {
    id: 'e7', title: 'Referral Program', category: 'offers',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 85, missingFields: ['referral_link'], usedIn: ['SaaS Decision Makers'],
    updatedAt: '2d ago', accentColor: '#fbbf24',
    fields: [
      { key: 'program_name', label: 'Program',         value: 'Refer & Earn',                         type: 'text',    aiRelevance: 'high' },
      { key: 'reward',       label: 'Reward',          value: '$50 credit per successful referral',   type: 'text',    aiRelevance: 'critical' },
      { key: 'conditions',   label: 'Conditions',      value: 'Referral must upgrade to paid plan',   type: 'text',    aiRelevance: 'high' },
    ],
  },

  // ── Business Hours ────────────────────────────────────────────────────────
  {
    id: 'e8', title: 'Support & Sales Hours', category: 'business_hours',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 100, missingFields: [], usedIn: ['Q4 Enterprise Outreach'],
    updatedAt: '1w ago', accentColor: '#22d3ee',
    fields: [
      { key: 'weekdays',     label: 'Mon – Fri',       value: '9:00 AM – 6:00 PM (EST)',              type: 'time',    aiRelevance: 'critical' },
      { key: 'saturday',     label: 'Saturday',        value: '10:00 AM – 2:00 PM (EST)',             type: 'time',    aiRelevance: 'high' },
      { key: 'sunday',       label: 'Sunday',          value: 'Closed',                               type: 'text',    aiRelevance: 'high' },
      { key: 'timezone',     label: 'Timezone',        value: 'Eastern Standard Time (UTC-5)',        type: 'text',    aiRelevance: 'critical' },
      { key: 'holidays',     label: 'Holidays',        value: 'US Federal Holidays — office closed',  type: 'text',    aiRelevance: 'medium' },
      { key: 'emergency',    label: 'Emergency',       value: 'Enterprise clients: 24/7 via Slack',   type: 'text',    aiRelevance: 'medium' },
    ],
  },

  // ── Meetings ──────────────────────────────────────────────────────────────
  {
    id: 'e9', title: 'Demo Call Availability', category: 'meetings',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 97, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers'],
    updatedAt: '3h ago', accentColor: '#c084fc',
    fields: [
      { key: 'meeting_type', label: 'Meeting Type',    value: 'Product Demo (30 min)',                type: 'text',    aiRelevance: 'critical' },
      { key: 'available',    label: 'Available Slots', value: 'Mon–Fri, 10 AM – 4 PM EST',           type: 'time',    aiRelevance: 'critical' },
      { key: 'booking_link', label: 'Booking Link',    value: 'https://cal.com/mailflowai/demo',      type: 'url',     aiRelevance: 'critical' },
      { key: 'platform',     label: 'Platform',        value: 'Google Meet / Zoom (prospect choice)', type: 'text',    aiRelevance: 'high' },
      { key: 'prep',         label: 'What to Expect',  value: 'Live walkthrough, Q&A, custom pricing discussion', type: 'text', aiRelevance: 'high' },
    ],
  },

  // ── Company Info ──────────────────────────────────────────────────────────
  {
    id: 'e10', title: 'Company Overview', category: 'company_info',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 93, missingFields: ['funding_stage'], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers', 'Cold Outbound'],
    updatedAt: '3d ago', accentColor: '#fb923c',
    fields: [
      { key: 'company_name', label: 'Company Name',    value: 'MailFlowAI Inc.',                      type: 'text',    aiRelevance: 'critical' },
      { key: 'founded',      label: 'Founded',         value: '2023',                                 type: 'text',    aiRelevance: 'medium' },
      { key: 'team_size',    label: 'Team Size',       value: '18 people',                            type: 'text',    aiRelevance: 'medium' },
      { key: 'hq',           label: 'Headquarters',    value: 'San Francisco, CA',                    type: 'text',    aiRelevance: 'medium' },
      { key: 'mission',      label: 'Mission',         value: 'Make AI-powered outreach accessible to every sales team', type: 'text', aiRelevance: 'high' },
      { key: 'customers',    label: 'Customers',       value: '2,400+ businesses across 40 countries', type: 'text',   aiRelevance: 'high' },
      { key: 'linkedin',     label: 'LinkedIn',        value: 'https://linkedin.com/company/mailflowai', type: 'url',  aiRelevance: 'medium' },
    ],
  },
];
