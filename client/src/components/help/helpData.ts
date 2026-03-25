export const HELP_CATEGORIES = [
  { id: 'start', label: 'Getting Started', color: '#818cf8', articles: 12 },
  { id: 'campaign', label: 'Campaigns & Automation', color: '#c084fc', articles: 18 },
  { id: 'inbox', label: 'Inbox & Emails', color: '#22d3ee', articles: 9 },
  { id: 'leads', label: 'Leads & Data', color: '#34d399', articles: 14 },
  { id: 'integrations', label: 'Integrations', color: '#fbbf24', articles: 11 },
  { id: 'settings', label: 'Account & Settings', color: '#f87171', articles: 8 },
];

export const HELP_ARTICLES = [
  { id: 'a1', title: 'How to connect your Gmail account', cat: 'inbox', reads: 2840, mins: 3, popular: true },
  { id: 'a2', title: 'Setting up your first email campaign', cat: 'campaign', reads: 1920, mins: 5, popular: true },
  { id: 'a3', title: 'Importing leads from CSV', cat: 'leads', reads: 1540, mins: 4, popular: true },
  { id: 'a4', title: 'Understanding AI reply automation', cat: 'campaign', reads: 1380, mins: 6, popular: true },
  { id: 'a5', title: 'Connecting HubSpot CRM integration', cat: 'integrations', reads: 980, mins: 4, popular: false },
  { id: 'a6', title: 'Managing team roles and permissions', cat: 'settings', reads: 760, mins: 3, popular: false },
  { id: 'a7', title: 'Email warm-up and deliverability tips', cat: 'inbox', reads: 1120, mins: 7, popular: true },
  { id: 'a8', title: 'Using Google Sheets as a lead source', cat: 'integrations', reads: 890, mins: 5, popular: false },
];

export const HELP_TICKETS = [
  { id: 't1', subject: 'Gmail sync not working after reconnect', status: 'open', time: '2h ago', color: '#fbbf24' },
  { id: 't2', subject: 'Campaign paused unexpectedly', status: 'resolved', time: '1 day ago', color: '#34d399' },
  { id: 't3', subject: 'CSV import showing duplicate error', status: 'resolved', time: '3 days ago', color: '#34d399' },
];

export const SYSTEM_STATUS = [
  { label: 'API', status: 'operational', uptime: '99.98%' },
  { label: 'Email Sending', status: 'operational', uptime: '99.95%' },
  { label: 'AI Engine', status: 'operational', uptime: '99.91%' },
  { label: 'Webhooks', status: 'degraded', uptime: '98.20%' },
];

export const SEARCH_SUGGESTIONS = [
  'How to connect Gmail', 'Campaign not sending', 'Import leads CSV',
  'AI reply setup', 'Billing and plans', 'Reset password',
  'HubSpot integration', 'Email deliverability',
];

export const AI_QUICK_PROMPTS = [
  'Why is my campaign paused?',
  'How do I improve open rates?',
  'Set up AI auto-reply',
  'Fix email sync issues',
];

export const VIDEO_TUTORIALS = [
  { title: 'Setting up your first campaign', dur: '3:24', color: '#818cf8' },
  { title: 'Connecting Gmail and Outlook', dur: '2:10', color: '#34d399' },
  { title: 'AI reply automation walkthrough', dur: '5:48', color: '#c084fc' },
  { title: 'Importing and managing leads', dur: '4:02', color: '#fbbf24' },
];
