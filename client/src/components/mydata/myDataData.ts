export type DataCategory =
  | 'product_service'
  | 'pricing_payment'
  | 'contact_support'
  | 'offers_promotions'
  | 'delivery_shipping'
  | 'company_info'
  | 'policies_legal'
  | 'educational_content';

export type SourceType = 'csv_import' | 'google_sheets' | 'manual' | 'api';
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

// ── Category config with full smart-guide metadata ────────────────────────────

export interface CategoryMeta {
  label: string;
  emoji: string;
  icon: string;
  color: string;
  description: string;
  guide: string;
  exampleColumns: string[];
  exampleEntry: string;
}

export const CATEGORY_CONFIG: Record<DataCategory, CategoryMeta> = {
  product_service: {
    label: 'Product / Service Details',
    emoji: '🛍️',
    icon: 'inventory',
    color: '#818cf8',
    description: 'Descriptions, features, specs, variants, availability',
    guide: 'Add your products or services so the AI can describe them accurately in outreach. Include features, variants, and availability to maximize personalization.',
    exampleColumns: ['Product Name', 'Description', 'Features', 'Variants', 'Availability', 'Demo URL', 'Category'],
    exampleEntry: 'Product Name: Proxipilot Pro | Features: AI personalization, multi-inbox | Availability: In stock',
  },
  pricing_payment: {
    label: 'Pricing & Payment',
    emoji: '💰',
    icon: 'payments',
    color: '#34d399',
    description: 'Plans, tiers, discounts, taxes, payment methods, refund policy',
    guide: 'Pricing data is critical for the AI to handle objections and close deals. Include all tiers, payment options, and refund terms.',
    exampleColumns: ['Plan Name', 'Monthly Price', 'Annual Price', 'Discount', 'Payment Methods', 'Refund Policy', 'Tax Info'],
    exampleEntry: 'Plan: Pro | Price: $79/mo | Annual: $59/mo | Payment: UPI, Cards, EMI | Refund: 30-day money back',
  },
  contact_support: {
    label: 'Contact & Support',
    emoji: '📞',
    icon: 'people',
    color: '#f472b6',
    description: 'Phone, email, live chat, office locations, support hours',
    guide: 'Contact info lets the AI direct prospects to the right channel. Include all support touchpoints and hours so responses feel complete.',
    exampleColumns: ['Phone', 'Email', 'WhatsApp', 'Live Chat URL', 'Office Address', 'Support Hours', 'Timezone'],
    exampleEntry: 'Phone: +1-800-555-0100 | Email: support@company.com | Hours: Mon–Fri 9AM–6PM EST',
  },
  offers_promotions: {
    label: 'Offers & Promotions',
    emoji: '🎯',
    icon: 'local_offer',
    color: '#fbbf24',
    description: 'Seasonal deals, coupon codes, loyalty programs, referral bonuses',
    guide: 'Promotions create urgency in outreach. Add active offers with expiry dates and promo codes so the AI can mention them at the right moment.',
    exampleColumns: ['Offer Name', 'Discount', 'Promo Code', 'Valid Until', 'Eligible Plans', 'Referral Reward', 'Conditions'],
    exampleEntry: 'Offer: Diwali Sale | Discount: 40% off | Code: DIWALI40 | Valid Until: Nov 15 | New users only',
  },
  delivery_shipping: {
    label: 'Delivery & Shipping',
    emoji: '🚚',
    icon: 'local_shipping',
    color: '#22d3ee',
    description: 'Timelines, charges, serviceable locations, tracking, returns',
    guide: 'Shipping details reduce friction in sales conversations. Include delivery timelines, charges by region, and return process so the AI can answer logistics questions.',
    exampleColumns: ['Delivery Timeline', 'Shipping Charges', 'Free Shipping Above', 'Serviceable Locations', 'Tracking Available', 'Return Window', 'Return Process'],
    exampleEntry: 'Delivery: 3–5 days | Free shipping above ₹500 | Pan-India | 7-day returns | Tracking via SMS',
  },
  company_info: {
    label: 'Company Information',
    emoji: '🏢',
    icon: 'business',
    color: '#fb923c',
    description: 'About us, brand story, mission, certifications, media mentions',
    guide: 'Company context builds trust in cold outreach. Add your story, mission, and credibility signals so the AI can establish authority naturally.',
    exampleColumns: ['Company Name', 'Founded', 'Mission', 'Team Size', 'Headquarters', 'Certifications', 'Media Mentions', 'LinkedIn'],
    exampleEntry: 'Company: Proxipilot | Founded: 2023 | Mission: AI outreach for every sales team | 2,400+ customers',
  },
  policies_legal: {
    label: 'Policies & Legal',
    emoji: '🔐',
    icon: 'gavel',
    color: '#c084fc',
    description: 'Privacy policy, terms & conditions, warranty, return/refund policies',
    guide: 'Policy data helps the AI handle compliance questions and build trust. Add your key policies so prospects get accurate answers without escalation.',
    exampleColumns: ['Policy Name', 'Policy Text', 'Effective Date', 'Warranty Period', 'Return Window', 'Refund Timeline', 'Governing Law'],
    exampleEntry: 'Policy: Refund Policy | 30-day full refund | No questions asked | Processed in 5–7 business days',
  },
  educational_content: {
    label: 'Educational / Support',
    emoji: '📚',
    icon: 'school',
    color: '#a3e635',
    description: 'FAQs, guides, tutorials, knowledge base, troubleshooting',
    guide: 'Educational content powers objection handling and onboarding. Add FAQs and guides so the AI can educate prospects and reduce support load.',
    exampleColumns: ['Question', 'Answer', 'Topic', 'Guide Title', 'Steps', 'Troubleshooting Issue', 'Solution'],
    exampleEntry: 'Q: How do I connect my inbox? | A: Go to Settings → Email Accounts → Add Account → Follow OAuth flow',
  },
};

export const SOURCE_TYPE_CONFIG: Record<SourceType, { label: string; color: string }> = {
  csv_import:    { label: 'CSV Import',    color: '#34d399' },
  google_sheets: { label: 'Google Sheets', color: '#60a5fa' },
  manual:        { label: 'Manual Entry',  color: '#c084fc' },
  api:           { label: 'API Sync',      color: '#22d3ee' },
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
  { id: 's1', name: 'Manual Entry',  type: 'manual',        status: 'connected', records: 24, lastSync: '5m ago',     aiReadyPct: 96, usedIn: ['Q4 Enterprise Outreach'] },
  { id: 's2', name: 'Product Sheet', type: 'google_sheets', status: 'syncing',   records: 18, lastSync: 'Syncing...', aiReadyPct: 82, usedIn: ['SaaS Decision Makers'] },
  { id: 's3', name: 'CRM Export',    type: 'csv_import',    status: 'connected', records: 41, lastSync: '1h ago',     aiReadyPct: 74, usedIn: ['Q4 Enterprise Outreach', 'Cold Outbound'] },
  { id: 's4', name: 'Pricing API',   type: 'api',           status: 'paused',    records: 12, lastSync: '3h ago',     aiReadyPct: 65, usedIn: ['Cold Outbound'] },
];

export const DATA_ENTRIES: DataEntry[] = [
  {
    id: 'e1', title: 'Proxipilot — Core Platform', category: 'product_service',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 95, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers'],
    updatedAt: '2h ago', accentColor: '#818cf8',
    fields: [
      { key: 'product_name',    label: 'Product Name',    value: 'Proxipilot',                                    type: 'text',  aiRelevance: 'critical' },
      { key: 'tagline',         label: 'Tagline',         value: 'AI-powered cold email automation at scale',     type: 'text',  aiRelevance: 'critical' },
      { key: 'key_features',    label: 'Key Features',    value: 'AI personalization, multi-inbox, smart replies, analytics', type: 'list', aiRelevance: 'critical' },
      { key: 'target_audience', label: 'Target Audience', value: 'Sales teams, SDRs, growth hackers, agencies',   type: 'text',  aiRelevance: 'high' },
      { key: 'website',         label: 'Website',         value: 'https://Proxipilot.com',                        type: 'url',   aiRelevance: 'medium' },
    ],
  },
  {
    id: 'e3', title: 'Pro Plan', category: 'pricing_payment',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 98, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers'],
    updatedAt: '30m ago', accentColor: '#34d399',
    fields: [
      { key: 'plan_name',    label: 'Plan Name',      value: 'Pro',                                  type: 'text',   aiRelevance: 'critical' },
      { key: 'price',        label: 'Monthly Price',  value: '$79/month',                            type: 'text',   aiRelevance: 'critical' },
      { key: 'annual_price', label: 'Annual Price',   value: '$59/month (billed annually)',           type: 'text',   aiRelevance: 'critical' },
      { key: 'emails_limit', label: 'Emails / Month', value: '15,000',                               type: 'number', aiRelevance: 'high' },
      { key: 'support',      label: 'Support',        value: 'Priority chat + email',                type: 'text',   aiRelevance: 'medium' },
    ],
  },
  {
    id: 'e6', title: 'Q4 Holiday Deal — 40% Off', category: 'offers_promotions',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 99, missingFields: [], usedIn: ['Q4 Enterprise Outreach', 'Cold Outbound'],
    updatedAt: '10m ago', accentColor: '#fbbf24',
    fields: [
      { key: 'offer_name',  label: 'Offer Name',    value: 'Q4 Holiday Special',         type: 'text', aiRelevance: 'critical' },
      { key: 'discount',    label: 'Discount',      value: '40% off all annual plans',   type: 'text', aiRelevance: 'critical' },
      { key: 'promo_code',  label: 'Promo Code',    value: 'HOLIDAY40',                  type: 'text', aiRelevance: 'critical' },
      { key: 'valid_until', label: 'Valid Until',   value: 'December 31, 2025',          type: 'date', aiRelevance: 'critical' },
    ],
  },
  {
    id: 'e8', title: 'Support & Sales Hours', category: 'contact_support',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 100, missingFields: [], usedIn: ['Q4 Enterprise Outreach'],
    updatedAt: '1w ago', accentColor: '#f472b6',
    fields: [
      { key: 'email',    label: 'Support Email', value: 'hello@Proxipilot.com',       type: 'email', aiRelevance: 'critical' },
      { key: 'weekdays', label: 'Mon – Fri',     value: '9:00 AM – 6:00 PM (EST)',      type: 'time',  aiRelevance: 'high' },
      { key: 'timezone', label: 'Timezone',      value: 'Eastern Standard Time (UTC-5)', type: 'text', aiRelevance: 'high' },
    ],
  },
  {
    id: 'e10', title: 'Company Overview', category: 'company_info',
    sourceId: 's1', sourceName: 'Manual Entry', sourceType: 'manual',
    qualityScore: 93, missingFields: ['funding_stage'], usedIn: ['Q4 Enterprise Outreach', 'SaaS Decision Makers', 'Cold Outbound'],
    updatedAt: '3d ago', accentColor: '#fb923c',
    fields: [
      { key: 'company_name', label: 'Company Name', value: 'Proxipilot Inc.',                                          type: 'text', aiRelevance: 'critical' },
      { key: 'mission',      label: 'Mission',      value: 'Make AI-powered outreach accessible to every sales team',  type: 'text', aiRelevance: 'high' },
      { key: 'customers',    label: 'Customers',    value: '2,400+ businesses across 40 countries',                    type: 'text', aiRelevance: 'high' },
      { key: 'linkedin',     label: 'LinkedIn',     value: 'https://linkedin.com/company/Proxipilot',                  type: 'url',  aiRelevance: 'medium' },
    ],
  },
];
