export type IntegrationStatus = 'connected' | 'disconnected' | 'error' | 'syncing';
export type CategoryId = 'email' | 'crm' | 'leads' | 'ads';

export interface Integration {
  id: string;
  name: string;
  description: string;
  category: CategoryId;
  status: IntegrationStatus;
  color: string;
  bgColor: string;
  popular?: boolean;
  new?: boolean;
  // connected state
  lastSync?: string;
  leadsImported?: number;
  automationsTriggered?: number;
  dataFlow?: string;
}

export interface Category {
  id: CategoryId;
  label: string;
  color: string;
  description: string;
}

export const CATEGORIES: Category[] = [
  { id: 'email', label: 'Email Providers', color: '#818cf8', description: 'Connect email accounts for sending' },
  { id: 'crm',   label: 'CRM Systems',     color: '#34d399', description: 'Sync contacts and deal data' },
  { id: 'leads', label: 'Lead Sources',    color: '#fbbf24', description: 'Import leads automatically' },
  { id: 'ads',   label: 'Ads & Social',    color: '#f472b6', description: 'Capture leads from ad platforms' },
];

export const INTEGRATIONS: Integration[] = [
  // Email — status is derived from accountsData at runtime; these are provider definitions only
  {
    id: 'gmail', name: 'Gmail', category: 'email', color: '#EA4335', bgColor: '#fef2f2',
    description: 'Send and receive emails via Google Workspace accounts.',
    status: 'connected', popular: true,
    lastSync: '2 min ago', leadsImported: 0, automationsTriggered: 312, dataFlow: 'Bidirectional',
  },
  {
    id: 'outlook', name: 'Outlook', category: 'email', color: '#0078D4', bgColor: '#eff6ff',
    description: 'Connect Microsoft 365 and Outlook accounts for outreach.',
    status: 'connected',
    lastSync: '5 min ago', leadsImported: 0, automationsTriggered: 187, dataFlow: 'Bidirectional',
  },
  {
    id: 'smtp', name: 'Custom SMTP', category: 'email', color: '#64748b', bgColor: '#f8fafc',
    description: 'Connect any email provider via SMTP/IMAP credentials.',
    status: 'disconnected',
  },

  // CRM
  {
    id: 'hubspot', name: 'HubSpot', category: 'crm', color: '#FF7A59', bgColor: '#fff7f5',
    description: 'Sync contacts, deals, and activities with HubSpot CRM.',
    status: 'connected', popular: true,
    lastSync: '15 min ago', leadsImported: 1240, automationsTriggered: 89, dataFlow: 'Bidirectional',
  },
  {
    id: 'salesforce', name: 'Salesforce', category: 'crm', color: '#00A1E0', bgColor: '#f0f9ff',
    description: 'Push leads and email activity into Salesforce CRM.',
    status: 'disconnected', popular: true,
  },
  {
    id: 'pipedrive', name: 'Pipedrive', category: 'crm', color: '#1A1F36', bgColor: '#f8fafc',
    description: 'Sync pipeline deals and contacts with Pipedrive.',
    status: 'disconnected',
  },
  {
    id: 'zoho', name: 'Zoho CRM', category: 'crm', color: '#E42527', bgColor: '#fef2f2',
    description: 'Connect Zoho CRM for contact and lead management.',
    status: 'disconnected',
  },

  // Lead Sources
  {
    id: 'csv', name: 'CSV Import', category: 'leads', color: '#34d399', bgColor: '#f0fdf4',
    description: 'Bulk import leads from CSV or Excel files. Import as many times as needed.',
    status: 'disconnected',
    leadsImported: 3420, automationsTriggered: 0, dataFlow: 'Inbound',
  },
  {
    id: 'gsheets', name: 'Google Sheets', category: 'leads', color: '#0F9D58', bgColor: '#f0fdf4',
    description: 'Auto-sync leads from a Google Sheets spreadsheet.',
    status: 'connected', popular: true,
    lastSync: '10 min ago', leadsImported: 892, automationsTriggered: 45, dataFlow: 'Inbound',
  },
  {
    id: 'apollo', name: 'Apollo.io', category: 'leads', color: '#6366f1', bgColor: '#eef2ff',
    description: 'Import verified B2B contacts directly from Apollo.',
    status: 'disconnected', new: true,
  },

  // Ads & Social
  {
    id: 'google-leads', name: 'Google Lead Forms', category: 'ads', color: '#4285F4', bgColor: '#eff6ff',
    description: 'Capture leads from Google Ads lead form extensions.',
    status: 'connected', popular: true,
    lastSync: '30 min ago', leadsImported: 567, automationsTriggered: 567, dataFlow: 'Inbound',
  },
  {
    id: 'fb-leads', name: 'Facebook Lead Ads', category: 'ads', color: '#1877F2', bgColor: '#eff6ff',
    description: 'Sync leads from Facebook and Instagram lead ad forms.',
    status: 'disconnected', popular: true,
  },
  {
    id: 'instagram', name: 'Instagram Leads', category: 'ads', color: '#E1306C', bgColor: '#fdf2f8',
    description: 'Capture leads from Instagram lead generation ads.',
    status: 'disconnected',
  },
  {
    id: 'linkedin', name: 'LinkedIn Lead Gen', category: 'ads', color: '#0A66C2', bgColor: '#eff6ff',
    description: 'Import leads from LinkedIn Lead Gen Forms automatically.',
    status: 'disconnected', popular: true, new: true,
  },
];

export const CONNECT_STEPS = [
  { id: 1, label: 'Overview',     desc: 'What this integration does' },
  { id: 2, label: 'Permissions',  desc: 'What access is required' },
  { id: 3, label: 'Authenticate', desc: 'Authorize your account' },
  { id: 4, label: 'Configure',    desc: 'Set sync preferences' },
];
