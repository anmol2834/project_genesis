import { get } from '../apiClient';

export type TimeRange = '7d' | '30d' | '90d';

export interface DayPoint { date: string; value: number; }

export interface AnalyticsKPI {
  emailsSent:      number;
  openRate:        number;
  replyRate:       number;
  convRate:        number;
  aiSuccessRate:   number;
  aiVsManual:      number;
  avgResponseTime: string;
  deltaEmails:     number;
  deltaOpen:       number;
  deltaReply:      number;
  deltaConv:       number;
}

export interface AnalyticsSeries {
  emailsSent:    DayPoint[];
  replies:       DayPoint[];
  opens:         DayPoint[];
  aiReplies:     DayPoint[];
  manualReplies: DayPoint[];
}

export interface AnalyticsResponse {
  kpi:    AnalyticsKPI;
  series: AnalyticsSeries;
}

export const analyticsApi = {
  overview: (range: TimeRange) => get<AnalyticsResponse>('/analytics/overview', { params: { range } }),
  campaigns: ()                => get<unknown[]>('/analytics/campaigns'),
  accounts:  ()                => get<unknown[]>('/analytics/accounts'),
};
