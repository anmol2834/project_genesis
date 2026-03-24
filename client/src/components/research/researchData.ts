export type RelevanceLevel = 'high' | 'medium' | 'low';
export type ConfidenceLevel = 'verified' | 'likely' | 'unverified';
export type ResearchIndustry =
  | 'SaaS' | 'FinTech' | 'E-Commerce' | 'HealthTech' | 'EdTech'
  | 'Marketing' | 'Real Estate' | 'Logistics' | 'AI/ML' | 'Cybersecurity';

export interface ResearchResult {
  id: string;
  businessName: string;
  website: string;
  industry: ResearchIndustry;
  contactEmail: string;
  contactName: string;
  contactRole: string;
  phone?: string;
  location: string;
  companySize: '1-10' | '11-50' | '51-200' | '201-500' | '500+';
  relevanceScore: number; // 0–100
  confidenceLevel: ConfidenceLevel;
  aiInsight: string;
  insightType: 'positive' | 'warning' | 'neutral';
  tags: string[];
  avatarColor: string;
  discoveredAt: string;
  savedForLater: boolean;
  addedToLeads: boolean;
}

export const RELEVANCE_CONFIG: Record<RelevanceLevel, { label: string; color: string; bg: string; darkBg: string }> = {
  high:   { label: 'High Match',   color: '#34d399', bg: 'rgba(52,211,153,0.1)',  darkBg: 'rgba(52,211,153,0.15)'  },
  medium: { label: 'Medium Match', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',  darkBg: 'rgba(251,191,36,0.15)'  },
  low:    { label: 'Low Match',    color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', darkBg: 'rgba(148,163,184,0.12)' },
};

export const CONFIDENCE_CONFIG: Record<ConfidenceLevel, { label: string; color: string; bg: string }> = {
  verified:   { label: 'Verified',   color: '#34d399', bg: 'rgba(52,211,153,0.1)'  },
  likely:     { label: 'Likely',     color: '#60a5fa', bg: 'rgba(96,165,250,0.1)'  },
  unverified: { label: 'Unverified', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
};

export function getRelevanceLevel(score: number): RelevanceLevel {
  if (score >= 75) return 'high';
  if (score >= 45) return 'medium';
  return 'low';
}

export const RESEARCH_RESULTS: ResearchResult[] = [
  {
    id: '1', businessName: 'Nexus Analytics', website: 'nexusanalytics.io',
    industry: 'SaaS', contactEmail: 'ceo@nexusanalytics.io', contactName: 'Jordan Blake',
    contactRole: 'CEO', phone: '+1 (415) 882-3301', location: 'San Francisco, CA',
    companySize: '51-200', relevanceScore: 94, confidenceLevel: 'verified',
    aiInsight: 'High match — SaaS company actively hiring sales team, likely scaling outreach.',
    insightType: 'positive', tags: ['SaaS', 'Series B', 'Scaling'],
    avatarColor: '#818cf8', discoveredAt: '2m ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '2', businessName: 'Meridian Capital', website: 'meridiancap.com',
    industry: 'FinTech', contactEmail: 'partnerships@meridiancap.com', contactName: 'Priya Nair',
    contactRole: 'Head of Partnerships', location: 'New York, NY',
    companySize: '201-500', relevanceScore: 88, confidenceLevel: 'verified',
    aiInsight: 'Recommended for outreach — recently closed Series C, expanding B2B partnerships.',
    insightType: 'positive', tags: ['FinTech', 'Series C', 'B2B'],
    avatarColor: '#22d3ee', discoveredAt: '8m ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '3', businessName: 'ShopStream', website: 'shopstream.co',
    industry: 'E-Commerce', contactEmail: 'growth@shopstream.co', contactName: 'Marcus Webb',
    contactRole: 'VP Growth', phone: '+44 20 7946 0123', location: 'London, UK',
    companySize: '11-50', relevanceScore: 81, confidenceLevel: 'verified',
    aiInsight: 'Strong fit — e-commerce brand with active email marketing budget.',
    insightType: 'positive', tags: ['E-Commerce', 'Growth Stage'],
    avatarColor: '#34d399', discoveredAt: '15m ago', savedForLater: true, addedToLeads: false,
  },
  {
    id: '4', businessName: 'PulseHealth AI', website: 'pulsehealth.ai',
    industry: 'HealthTech', contactEmail: 'bd@pulsehealth.ai', contactName: 'Dr. Aisha Osei',
    contactRole: 'Business Development', location: 'Austin, TX',
    companySize: '51-200', relevanceScore: 76, confidenceLevel: 'likely',
    aiInsight: 'Good potential — HealthTech startup with recent product launch, open to partnerships.',
    insightType: 'positive', tags: ['HealthTech', 'AI', 'Startup'],
    avatarColor: '#c084fc', discoveredAt: '32m ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '5', businessName: 'LearnForge', website: 'learnforge.io',
    industry: 'EdTech', contactEmail: 'hello@learnforge.io', contactName: 'Sam Okafor',
    contactRole: 'Co-Founder', location: 'Toronto, Canada',
    companySize: '11-50', relevanceScore: 68, confidenceLevel: 'likely',
    aiInsight: 'Medium match — EdTech platform growing user base, email automation could help.',
    insightType: 'neutral', tags: ['EdTech', 'B2C', 'Early Stage'],
    avatarColor: '#fbbf24', discoveredAt: '1h ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '6', businessName: 'GrowthPilot Agency', website: 'growthpilot.agency',
    industry: 'Marketing', contactEmail: 'team@growthpilot.agency', contactName: 'Elena Vasquez',
    contactRole: 'Founder', phone: '+34 91 123 4567', location: 'Madrid, Spain',
    companySize: '1-10', relevanceScore: 72, confidenceLevel: 'verified',
    aiInsight: 'Agency with 40+ B2B clients — high potential for white-label outreach tool.',
    insightType: 'positive', tags: ['Agency', 'B2B', 'White-label'],
    avatarColor: '#f472b6', discoveredAt: '1h ago', savedForLater: true, addedToLeads: false,
  },
  {
    id: '7', businessName: 'PropTech Ventures', website: 'proptech.vc',
    industry: 'Real Estate', contactEmail: 'invest@proptech.vc', contactName: 'Daniel Cho',
    contactRole: 'Managing Partner', location: 'Singapore',
    companySize: '11-50', relevanceScore: 55, confidenceLevel: 'likely',
    aiInsight: 'Moderate fit — real estate VC, may benefit from automated investor outreach.',
    insightType: 'neutral', tags: ['Real Estate', 'VC', 'Asia'],
    avatarColor: '#818cf8', discoveredAt: '2h ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '8', businessName: 'SwiftRoute Logistics', website: 'swiftroute.com',
    industry: 'Logistics', contactEmail: 'ops@swiftroute.com', contactName: 'Fatima Al-Rashid',
    contactRole: 'Operations Director', phone: '+971 4 123 4567', location: 'Dubai, UAE',
    companySize: '201-500', relevanceScore: 48, confidenceLevel: 'unverified',
    aiInsight: 'Low confidence data — email may be outdated. Verify before outreach.',
    insightType: 'warning', tags: ['Logistics', 'Enterprise', 'MENA'],
    avatarColor: '#22d3ee', discoveredAt: '3h ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '9', businessName: 'Cortex AI Labs', website: 'cortexai.dev',
    industry: 'AI/ML', contactEmail: 'founders@cortexai.dev', contactName: 'Ravi Shankar',
    contactRole: 'CTO & Co-Founder', location: 'Bangalore, India',
    companySize: '1-10', relevanceScore: 91, confidenceLevel: 'verified',
    aiInsight: 'Excellent match — AI startup building LLM tools, perfect for automation pitch.',
    insightType: 'positive', tags: ['AI/ML', 'Deep Tech', 'Seed'],
    avatarColor: '#34d399', discoveredAt: '4h ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '10', businessName: 'VaultSec Systems', website: 'vaultsec.io',
    industry: 'Cybersecurity', contactEmail: 'sales@vaultsec.io', contactName: 'Chris Novak',
    contactRole: 'VP Sales', phone: '+1 (312) 555-0198', location: 'Chicago, IL',
    companySize: '51-200', relevanceScore: 83, confidenceLevel: 'verified',
    aiInsight: 'Strong outreach candidate — cybersecurity firm with active sales team expansion.',
    insightType: 'positive', tags: ['Cybersecurity', 'Enterprise', 'B2B'],
    avatarColor: '#c084fc', discoveredAt: '5h ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '11', businessName: 'Bloom Retail Tech', website: 'bloomretail.tech',
    industry: 'E-Commerce', contactEmail: 'cmo@bloomretail.tech', contactName: 'Yuki Tanaka',
    contactRole: 'CMO', location: 'Tokyo, Japan',
    companySize: '51-200', relevanceScore: 62, confidenceLevel: 'likely',
    aiInsight: 'Decent fit — retail tech company exploring B2B SaaS tools for their clients.',
    insightType: 'neutral', tags: ['Retail', 'Asia-Pacific', 'Mid-Market'],
    avatarColor: '#fbbf24', discoveredAt: '6h ago', savedForLater: false, addedToLeads: false,
  },
  {
    id: '12', businessName: 'DataBridge Analytics', website: 'databridge.io',
    industry: 'SaaS', contactEmail: 'growth@databridge.io', contactName: 'Amara Diallo',
    contactRole: 'Head of Growth', location: 'Berlin, Germany',
    companySize: '11-50', relevanceScore: 79, confidenceLevel: 'verified',
    aiInsight: 'High potential — data analytics SaaS scaling in EU market, needs outreach automation.',
    insightType: 'positive', tags: ['SaaS', 'Data', 'EU Market'],
    avatarColor: '#f472b6', discoveredAt: '8h ago', savedForLater: true, addedToLeads: false,
  },
];

export const INDUSTRIES: ResearchIndustry[] = [
  'SaaS', 'FinTech', 'E-Commerce', 'HealthTech', 'EdTech',
  'Marketing', 'Real Estate', 'Logistics', 'AI/ML', 'Cybersecurity',
];

export const COMPANY_SIZES = ['1-10', '11-50', '51-200', '201-500', '500+'] as const;
