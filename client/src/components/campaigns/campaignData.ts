export type CampaignStatus = 'running' | 'paused' | 'draft';

export interface Campaign {
  id: string;
  name: string;
  status: CampaignStatus;
  emailsSent: number;
  emailsTotal: number;
  openRate: number;
  replyRate: number;
  lastActivity: string;
  createdAt: string;
  accentColor: string;
  aiInsight: string;
  insightType: 'positive' | 'warning' | 'neutral';
  tags: string[];
}

export const CAMPAIGNS: Campaign[] = [
  {
    id: '1',
    name: 'Q4 Enterprise Outreach',
    status: 'running',
    emailsSent: 1240,
    emailsTotal: 2000,
    openRate: 48,
    replyRate: 22,
    lastActivity: '2m ago',
    createdAt: 'Oct 12, 2025',
    accentColor: '#34d399',
    aiInsight: 'Above average open rate — consider increasing send volume.',
    insightType: 'positive',
    tags: ['Enterprise', 'Q4'],
  },
  {
    id: '2',
    name: 'SaaS Decision Makers',
    status: 'running',
    emailsSent: 870,
    emailsTotal: 1500,
    openRate: 41,
    replyRate: 18,
    lastActivity: '18m ago',
    createdAt: 'Oct 8, 2025',
    accentColor: '#818cf8',
    aiInsight: 'Reply rate trending up — AI follow-ups are working well.',
    insightType: 'positive',
    tags: ['SaaS', 'B2B'],
  },
  {
    id: '3',
    name: 'Cold Outbound — Series B',
    status: 'paused',
    emailsSent: 430,
    emailsTotal: 800,
    openRate: 19,
    replyRate: 4,
    lastActivity: '2h ago',
    createdAt: 'Sep 28, 2025',
    accentColor: '#fbbf24',
    aiInsight: 'Low open rate detected — subject line may need optimization.',
    insightType: 'warning',
    tags: ['Investors', 'Series B'],
  },
  {
    id: '4',
    name: 'Product Launch — Nov',
    status: 'draft',
    emailsSent: 0,
    emailsTotal: 3000,
    openRate: 0,
    replyRate: 0,
    lastActivity: 'Not started',
    createdAt: 'Oct 20, 2025',
    accentColor: '#c084fc',
    aiInsight: 'AI has pre-generated 3 email sequences for this campaign.',
    insightType: 'neutral',
    tags: ['Product', 'Launch'],
  },
];

export const STATUS_CONFIG: Record<CampaignStatus, { label: string; color: string; bg: string; darkBg: string }> = {
  running: { label: 'Running', color: '#34d399', bg: 'rgba(52,211,153,0.1)',  darkBg: 'rgba(52,211,153,0.15)'  },
  paused:  { label: 'Paused',  color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',  darkBg: 'rgba(251,191,36,0.15)'  },
  draft:   { label: 'Draft',   color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', darkBg: 'rgba(148,163,184,0.12)' },
};
