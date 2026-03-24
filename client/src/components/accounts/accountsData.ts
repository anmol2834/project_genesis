export type AccountStatus = 'connected' | 'syncing' | 'paused';
export type AccountProvider = 'gmail' | 'outlook' | 'custom';

export interface EmailAccount {
  id: string;
  email: string;
  name: string;
  provider: AccountProvider;
  status: AccountStatus;
  automationEnabled: boolean;
  lastSync: string;
  emailsProcessed: number;
  emailsSentToday: number;
  replyRate: number;
  insight: string;
  insightType: 'positive' | 'warning' | 'neutral';
  connectedAt: string;
  dailyLimit: number;
  dailyUsed: number;
}

export const STATUS_CONFIG: Record<AccountStatus, { label: string; color: string; bg: string; darkBg: string }> = {
  connected: { label: 'Connected', color: '#34d399', bg: 'rgba(52,211,153,0.1)',  darkBg: 'rgba(52,211,153,0.15)'  },
  syncing:   { label: 'Syncing',   color: '#60a5fa', bg: 'rgba(96,165,250,0.1)',  darkBg: 'rgba(96,165,250,0.15)'  },
  paused:    { label: 'Paused',    color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',  darkBg: 'rgba(251,191,36,0.15)'  },
};

export const ACCOUNTS: EmailAccount[] = [
  {
    id: '1', email: 'alex@techcorp.com', name: 'Alex Johnson',
    provider: 'gmail', status: 'connected', automationEnabled: true,
    lastSync: '2m ago', emailsProcessed: 2847, emailsSentToday: 142,
    replyRate: 24, insight: 'High reply rate — this account is performing well.',
    insightType: 'positive', connectedAt: 'Oct 1, 2025', dailyLimit: 500, dailyUsed: 142,
  },
  {
    id: '2', email: 'sales@mycompany.io', name: 'Sales Team',
    provider: 'outlook', status: 'connected', automationEnabled: true,
    lastSync: '8m ago', emailsProcessed: 1420, emailsSentToday: 98,
    replyRate: 18, insight: 'Steady performance. AI follow-ups active.',
    insightType: 'neutral', connectedAt: 'Sep 20, 2025', dailyLimit: 300, dailyUsed: 98,
  },
  {
    id: '3', email: 'outreach@domain.com', name: 'Outreach Account',
    provider: 'gmail', status: 'syncing', automationEnabled: true,
    lastSync: 'Syncing...', emailsProcessed: 870, emailsSentToday: 0,
    replyRate: 11, insight: 'Sync in progress — new emails being indexed.',
    insightType: 'neutral', connectedAt: 'Oct 10, 2025', dailyLimit: 200, dailyUsed: 0,
  },
  {
    id: '4', email: 'support@startup.xyz', name: 'Support Inbox',
    provider: 'outlook', status: 'paused', automationEnabled: false,
    lastSync: '3h ago', emailsProcessed: 340, emailsSentToday: 0,
    replyRate: 6, insight: 'Automation paused — resume to continue outreach.',
    insightType: 'warning', connectedAt: 'Sep 5, 2025', dailyLimit: 150, dailyUsed: 0,
  },
  {
    id: '5', email: 'newsletter@brand.co', name: 'Newsletter',
    provider: 'gmail', status: 'paused', automationEnabled: false,
    lastSync: '1d ago', emailsProcessed: 560, emailsSentToday: 0,
    replyRate: 8, insight: 'Automation paused by user. Resume when ready.',
    insightType: 'warning', connectedAt: 'Aug 15, 2025', dailyLimit: 400, dailyUsed: 0,
  },
];
