export type TimeRange = '7d' | '30d' | '90d';

export interface DayPoint { date: string; value: number }
export interface CampaignStat {
  id: string; name: string; color: string;
  sent: number; opened: number; replied: number; converted: number;
  openRate: number; replyRate: number; convRate: number;
  trend: number[]; // 7 sparkline points
}
export interface AccountStat {
  id: string; name: string; provider: 'gmail' | 'outlook';
  sent: number; replied: number; replyRate: number; health: number;
  color: string;
}
export interface AIInsight {
  id: string; type: 'positive' | 'warning' | 'neutral';
  title: string; body: string; delta?: string;
}

// ── Time-series data ──────────────────────────────────────────────────────────
function makeSeries(base: number, len: number, variance: number, trend = 0): DayPoint[] {
  const labels7  = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const labels30 = Array.from({ length: 30 }, (_, i) => `D${i + 1}`);
  const labels90 = Array.from({ length: 90 }, (_, i) => `D${i + 1}`);
  const labels = len === 7 ? labels7 : len === 30 ? labels30 : labels90;
  let v = base;
  return labels.map((date, i) => {
    v = Math.max(0, v + (Math.random() - 0.45) * variance + trend * i * 0.3);
    return { date, value: Math.round(v) };
  });
}

export const SERIES: Record<TimeRange, {
  emailsSent: DayPoint[];
  replies: DayPoint[];
  opens: DayPoint[];
  aiReplies: DayPoint[];
  manualReplies: DayPoint[];
}> = {
  '7d': {
    emailsSent:    makeSeries(320, 7, 60, 2),
    replies:       makeSeries(48,  7, 12, 1),
    opens:         makeSeries(140, 7, 30, 1.5),
    aiReplies:     makeSeries(32,  7, 8,  1),
    manualReplies: makeSeries(16,  7, 5,  0),
  },
  '30d': {
    emailsSent:    makeSeries(280, 30, 80, 1.5),
    replies:       makeSeries(42,  30, 14, 0.8),
    opens:         makeSeries(120, 30, 35, 1),
    aiReplies:     makeSeries(28,  30, 9,  0.8),
    manualReplies: makeSeries(14,  30, 6,  0),
  },
  '90d': {
    emailsSent:    makeSeries(240, 90, 100, 1),
    replies:       makeSeries(36,  90, 16,  0.5),
    opens:         makeSeries(100, 90, 40,  0.7),
    aiReplies:     makeSeries(24,  90, 10,  0.6),
    manualReplies: makeSeries(12,  90, 7,   0),
  },
};

// ── KPI summary ───────────────────────────────────────────────────────────────
export const KPI: Record<TimeRange, {
  emailsSent: number; openRate: number; replyRate: number; convRate: number;
  aiSuccessRate: number; aiVsManual: number; avgResponseTime: string;
  deltaEmails: number; deltaOpen: number; deltaReply: number; deltaConv: number;
}> = {
  '7d':  { emailsSent: 2184, openRate: 43.2, replyRate: 14.8, convRate: 3.1, aiSuccessRate: 78, aiVsManual: 67, avgResponseTime: '4.2h', deltaEmails: 12, deltaOpen: 3.4, deltaReply: 1.8, deltaConv: 0.4 },
  '30d': { emailsSent: 8940, openRate: 41.7, replyRate: 13.2, convRate: 2.8, aiSuccessRate: 74, aiVsManual: 63, avgResponseTime: '5.1h', deltaEmails: 8,  deltaOpen: 2.1, deltaReply: 0.9, deltaConv: 0.2 },
  '90d': { emailsSent: 24600, openRate: 39.4, replyRate: 11.9, convRate: 2.4, aiSuccessRate: 71, aiVsManual: 58, avgResponseTime: '6.3h', deltaEmails: 5,  deltaOpen: 1.2, deltaReply: 0.5, deltaConv: 0.1 },
};

// ── Campaign stats ────────────────────────────────────────────────────────────
export const CAMPAIGN_STATS: CampaignStat[] = [
  { id: 'c1', name: 'Q4 Enterprise Outreach', color: '#818cf8', sent: 1240, opened: 582, replied: 198, converted: 44, openRate: 46.9, replyRate: 15.9, convRate: 3.5, trend: [12,18,15,22,19,28,24] },
  { id: 'c2', name: 'SaaS Decision Makers',   color: '#34d399', sent: 890,  opened: 374, replied: 112, converted: 28, openRate: 42.0, replyRate: 12.6, convRate: 3.1, trend: [8,10,9,14,12,16,15]  },
  { id: 'c3', name: 'Cold Outbound — Series B',color: '#fbbf24', sent: 560,  opened: 196, replied: 67,  converted: 11, openRate: 35.0, replyRate: 12.0, convRate: 2.0, trend: [6,7,5,8,7,9,8]    },
  { id: 'c4', name: 'Startup Founders Q1',    color: '#c084fc', sent: 320,  opened: 118, replied: 38,  converted: 7,  openRate: 36.9, replyRate: 11.9, convRate: 2.2, trend: [3,4,3,5,4,6,5]    },
];

// ── Account stats ─────────────────────────────────────────────────────────────
export const ACCOUNT_STATS: AccountStat[] = [
  { id: 'a1', name: 'alex@company.com',  provider: 'gmail',   sent: 1840, replied: 298, replyRate: 16.2, health: 94, color: '#818cf8' },
  { id: 'a2', name: 'sarah@company.com', provider: 'gmail',   sent: 1120, replied: 156, replyRate: 13.9, health: 88, color: '#34d399' },
  { id: 'a3', name: 'tom@company.com',   provider: 'outlook', sent: 780,  replied: 98,  replyRate: 12.6, health: 82, color: '#fbbf24' },
  { id: 'a4', name: 'outreach@co.com',   provider: 'gmail',   sent: 440,  replied: 48,  replyRate: 10.9, health: 76, color: '#c084fc' },
];

// ── AI insights ───────────────────────────────────────────────────────────────
export const AI_INSIGHTS: AIInsight[] = [
  { id: 'i1', type: 'positive', title: 'Reply rate up 15%',         body: 'AI-personalized subject lines are driving higher engagement this week.',                delta: '+15%' },
  { id: 'i2', type: 'positive', title: 'Best send time: 9–11 AM',   body: 'Emails sent between 9–11 AM EST have 2.3× higher open rates.',                        delta: '2.3×' },
  { id: 'i3', type: 'warning',  title: 'Cold Outbound underperforming', body: 'Reply rate dropped to 12% — consider refreshing the email copy or targeting.',    delta: '-3.2%' },
  { id: 'i4', type: 'positive', title: 'AI replies outperform manual', body: '67% of positive responses came from AI-generated replies vs 33% manual.',          delta: '+67%' },
  { id: 'i5', type: 'neutral',  title: 'Avg response time: 4.2h',   body: 'Leads respond fastest on Tuesday mornings. Schedule follow-ups accordingly.',         delta: '4.2h' },
  { id: 'i6', type: 'warning',  title: 'tom@company.com warming up', body: 'Inbox health at 82% — reduce daily send volume to avoid spam filters.',              delta: '82%' },
];

// ── Lead engagement distribution ─────────────────────────────────────────────
export const LEAD_ENGAGEMENT = [
  { label: 'Replied',      value: 14.8, color: '#34d399' },
  { label: 'Opened only',  value: 28.4, color: '#818cf8' },
  { label: 'No open',      value: 56.8, color: '#334155' },
];

// ── AI tone performance ───────────────────────────────────────────────────────
export const AI_TONE_PERF = [
  { tone: 'Professional', replyRate: 16.2, color: '#818cf8' },
  { tone: 'Friendly',     replyRate: 14.8, color: '#34d399' },
  { tone: 'Concise',      replyRate: 13.1, color: '#22d3ee' },
  { tone: 'Persuasive',   replyRate: 11.4, color: '#fbbf24' },
  { tone: 'Casual',       replyRate: 9.2,  color: '#f472b6' },
];
