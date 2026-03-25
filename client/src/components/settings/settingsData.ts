export type SettingSection =
  | 'profile'
  | 'account'
  | 'email'
  | 'ai'
  | 'automation'
  | 'notifications'
  | 'security'
  | 'team'
  | 'data'
  | 'about';

export interface NavItem {
  id: SettingSection;
  label: string;
  icon: string;
  color: string;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'profile',       label: 'Profile',        icon: 'person',         color: '#818cf8', description: 'Name, photo, business info' },
  { id: 'account',       label: 'Account',         icon: 'manage',         color: '#22d3ee', description: 'Password, sessions, 2FA' },
  { id: 'email',         label: 'Email Accounts',  icon: 'email',          color: '#34d399', description: 'Connected accounts, sync' },
  { id: 'ai',            label: 'AI Settings',     icon: 'ai',             color: '#c084fc', description: 'Tone, behavior, instructions' },
  { id: 'automation',    label: 'Automation',      icon: 'bolt',           color: '#fbbf24', description: 'Rules, triggers, sequences' },
  { id: 'notifications', label: 'Notifications',   icon: 'bell',           color: '#f87171', description: 'Alerts, digests, activity' },
  { id: 'security',      label: 'Security',        icon: 'shield',         color: '#fb923c', description: 'Access, audit log, tokens' },
  { id: 'team',          label: 'Team',            icon: 'group',          color: '#60a5fa', description: 'Members, roles, permissions' },
  { id: 'data',          label: 'Data & Privacy',  icon: 'storage',        color: '#a3e635', description: 'Export, usage, deletion' },
  { id: 'about',         label: 'About & Legal',   icon: 'info',           color: '#94a3b8', description: 'Version, terms, privacy' },
];

export const CONNECTED_ACCOUNTS = [
  { id: '1', email: 'outreach@company.com',  provider: 'Google',    status: 'active',  sent: 1240, health: 98 },
  { id: '2', email: 'sales@company.com',     provider: 'Microsoft', status: 'active',  sent: 870,  health: 94 },
  { id: '3', email: 'support@company.com',   provider: 'Google',    status: 'warning', sent: 340,  health: 71 },
];

export const ACTIVE_SESSIONS = [
  { id: '1', device: 'Chrome on macOS',    location: 'New York, US',    time: 'Active now',   current: true },
  { id: '2', device: 'Safari on iPhone',   location: 'New York, US',    time: '2 hours ago',  current: false },
  { id: '3', device: 'Firefox on Windows', location: 'London, UK',      time: '3 days ago',   current: false },
];

export const AI_TONES = [
  { id: 'professional', label: 'Professional',  desc: 'Formal, business-focused tone' },
  { id: 'friendly',     label: 'Friendly',      desc: 'Warm, approachable, conversational' },
  { id: 'concise',      label: 'Concise',       desc: 'Short, direct, no fluff' },
  { id: 'persuasive',   label: 'Persuasive',    desc: 'Compelling, action-oriented' },
  { id: 'empathetic',   label: 'Empathetic',    desc: 'Understanding, human-first' },
];

export const AUTOMATION_RULES = [
  { id: '1', name: 'Auto-reply to warm leads',    enabled: true,  trigger: 'Reply received',    action: 'AI draft response' },
  { id: '2', name: 'Follow-up after 3 days',      enabled: true,  trigger: 'No reply in 3d',    action: 'Send follow-up' },
  { id: '3', name: 'Pause on out-of-office',      enabled: true,  trigger: 'OOO detected',      action: 'Pause sequence' },
  { id: '4', name: 'Escalate hot leads',          enabled: false, trigger: 'Positive intent',   action: 'Notify team' },
];
