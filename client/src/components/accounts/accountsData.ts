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

// No mock data — accounts are loaded from the email-service API
export const ACCOUNTS: EmailAccount[] = [];
