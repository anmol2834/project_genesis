export type MemberRole = 'owner' | 'admin' | 'member';
export type MemberStatus = 'active' | 'invited' | 'suspended';

export interface Permission {
  key: string;
  label: string;
  description: string;
  group: 'outreach' | 'intelligence' | 'workspace';
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: MemberRole;
  status: MemberStatus;
  avatarColor: string;
  joinedAt: string;
  lastActive: string;
  permissions: string[];
  activityCount: number;
  campaignsManaged: number;
  emailsSent: number;
  aiActionsTriggered: number;
}

export interface ActivityEvent {
  id: string;
  memberId: string;
  memberName: string;
  action: string;
  target: string;
  timestamp: string;
  type: 'campaign' | 'email' | 'ai' | 'lead' | 'settings' | 'invite';
}

export const ROLE_CONFIG: Record<MemberRole, {
  label: string; color: string; bg: string; darkBg: string; description: string;
}> = {
  owner:  { label: 'Owner',  color: '#818cf8', bg: 'rgba(129,140,248,0.1)',  darkBg: 'rgba(129,140,248,0.15)', description: 'Full control over workspace' },
  admin:  { label: 'Admin',  color: '#c084fc', bg: 'rgba(192,132,252,0.1)',  darkBg: 'rgba(192,132,252,0.15)', description: 'Manage campaigns, leads & team' },
  member: { label: 'Member', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)',  darkBg: 'rgba(148,163,184,0.15)', description: 'Limited access to assigned features' },
};

export const STATUS_CONFIG: Record<MemberStatus, {
  label: string; color: string; bg: string;
}> = {
  active:    { label: 'Active',    color: '#34d399', bg: 'rgba(52,211,153,0.1)'  },
  invited:   { label: 'Invited',   color: '#60a5fa', bg: 'rgba(96,165,250,0.1)'  },
  suspended: { label: 'Suspended', color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
};

export const ALL_PERMISSIONS: Permission[] = [
  // Outreach
  { key: 'inbox',           label: 'Access Inbox',        description: 'Read & reply to emails',          group: 'outreach'     },
  { key: 'campaigns',       label: 'Manage Campaigns',    description: 'Create, edit, run campaigns',     group: 'outreach'     },
  { key: 'leads',           label: 'Manage Leads',        description: 'Add, edit, delete leads',         group: 'outreach'     },
  { key: 'email_accounts',  label: 'Email Accounts',      description: 'Connect & manage email accounts', group: 'outreach'     },
  // Intelligence
  { key: 'ai_control',      label: 'Control AI',          description: 'Trigger & configure AI actions',  group: 'intelligence' },
  { key: 'research',        label: 'Research',            description: 'Run business research queries',   group: 'intelligence' },
  { key: 'my_data',         label: 'My Data',             description: 'View & edit business data',       group: 'intelligence' },
  { key: 'automation',      label: 'Automation',          description: 'Build & manage automations',      group: 'intelligence' },
  // Workspace
  { key: 'analytics',       label: 'View Analytics',      description: 'Access reports & dashboards',     group: 'workspace'    },
  { key: 'team',            label: 'Manage Team',         description: 'Invite & manage team members',    group: 'workspace'    },
  { key: 'integrations',    label: 'Integrations',        description: 'Connect third-party tools',       group: 'workspace'    },
  { key: 'billing',         label: 'Billing',             description: 'View & manage subscription',      group: 'workspace'    },
];

export const PERMISSION_GROUP_CONFIG = {
  outreach:     { label: 'Outreach',     color: '#34d399' },
  intelligence: { label: 'Intelligence', color: '#c084fc' },
  workspace:    { label: 'Workspace',    color: '#60a5fa' },
};

// Default permissions per role
export const ROLE_DEFAULT_PERMISSIONS: Record<MemberRole, string[]> = {
  owner:  ALL_PERMISSIONS.map(p => p.key),
  admin:  ['inbox', 'campaigns', 'leads', 'email_accounts', 'ai_control', 'research', 'my_data', 'automation', 'analytics'],
  member: ['inbox', 'campaigns', 'leads'],
};

export const TEAM_MEMBERS: TeamMember[] = [
  {
    id: 'm1', name: 'Alex Rivera', email: 'alex@company.com',
    role: 'owner', status: 'active', avatarColor: '#818cf8',
    joinedAt: 'Jan 2024', lastActive: 'Just now',
    permissions: ROLE_DEFAULT_PERMISSIONS.owner,
    activityCount: 284, campaignsManaged: 12, emailsSent: 4820, aiActionsTriggered: 156,
  },
  {
    id: 'm2', name: 'Sarah Chen', email: 'sarah@company.com',
    role: 'admin', status: 'active', avatarColor: '#c084fc',
    joinedAt: 'Feb 2024', lastActive: '2h ago',
    permissions: ROLE_DEFAULT_PERMISSIONS.admin,
    activityCount: 142, campaignsManaged: 7, emailsSent: 2340, aiActionsTriggered: 89,
  },
  {
    id: 'm3', name: 'Marcus Johnson', email: 'marcus@company.com',
    role: 'member', status: 'active', avatarColor: '#34d399',
    joinedAt: 'Mar 2024', lastActive: '1d ago',
    permissions: ['inbox', 'campaigns', 'leads', 'analytics'],
    activityCount: 67, campaignsManaged: 3, emailsSent: 890, aiActionsTriggered: 12,
  },
  {
    id: 'm4', name: 'Priya Sharma', email: 'priya@company.com',
    role: 'member', status: 'active', avatarColor: '#fbbf24',
    joinedAt: 'Apr 2024', lastActive: '3h ago',
    permissions: ['inbox', 'leads', 'research'],
    activityCount: 53, campaignsManaged: 1, emailsSent: 420, aiActionsTriggered: 8,
  },
  {
    id: 'm5', name: 'Tom Wallace', email: 'tom@company.com',
    role: 'admin', status: 'active', avatarColor: '#22d3ee',
    joinedAt: 'Mar 2024', lastActive: '5h ago',
    permissions: ROLE_DEFAULT_PERMISSIONS.admin,
    activityCount: 98, campaignsManaged: 5, emailsSent: 1650, aiActionsTriggered: 44,
  },
  {
    id: 'm6', name: 'Nina Patel', email: 'nina@company.com',
    role: 'member', status: 'invited', avatarColor: '#f472b6',
    joinedAt: '—', lastActive: 'Never',
    permissions: ['inbox', 'campaigns'],
    activityCount: 0, campaignsManaged: 0, emailsSent: 0, aiActionsTriggered: 0,
  },
  {
    id: 'm7', name: 'David Kim', email: 'david@company.com',
    role: 'member', status: 'suspended', avatarColor: '#fb923c',
    joinedAt: 'Feb 2024', lastActive: '2w ago',
    permissions: [],
    activityCount: 21, campaignsManaged: 0, emailsSent: 180, aiActionsTriggered: 3,
  },
];

export const ACTIVITY_LOG: ActivityEvent[] = [
  { id: 'a1',  memberId: 'm1', memberName: 'Alex Rivera',    action: 'Launched campaign',    target: 'Q4 Enterprise Outreach',    timestamp: '2m ago',  type: 'campaign' },
  { id: 'a2',  memberId: 'm2', memberName: 'Sarah Chen',     action: 'Triggered AI reply',   target: 'mike@ventures.io',          timestamp: '18m ago', type: 'ai'       },
  { id: 'a3',  memberId: 'm5', memberName: 'Tom Wallace',    action: 'Added 24 leads',       target: 'SaaS Decision Makers',      timestamp: '1h ago',  type: 'lead'     },
  { id: 'a4',  memberId: 'm3', memberName: 'Marcus Johnson', action: 'Sent email sequence',  target: 'Cold Outbound — Series B',  timestamp: '2h ago',  type: 'email'    },
  { id: 'a5',  memberId: 'm4', memberName: 'Priya Sharma',   action: 'Ran research query',   target: 'FinTech companies, London', timestamp: '3h ago',  type: 'ai'       },
  { id: 'a6',  memberId: 'm2', memberName: 'Sarah Chen',     action: 'Paused campaign',      target: 'SaaS Decision Makers',      timestamp: '5h ago',  type: 'campaign' },
  { id: 'a7',  memberId: 'm1', memberName: 'Alex Rivera',    action: 'Invited member',       target: 'nina@company.com',          timestamp: '1d ago',  type: 'invite'   },
  { id: 'a8',  memberId: 'm5', memberName: 'Tom Wallace',    action: 'Updated AI settings',  target: 'Reply tone: Professional',  timestamp: '1d ago',  type: 'settings' },
  { id: 'a9',  memberId: 'm3', memberName: 'Marcus Johnson', action: 'Created campaign',     target: 'Startup Founders Q1',       timestamp: '2d ago',  type: 'campaign' },
  { id: 'a10', memberId: 'm1', memberName: 'Alex Rivera',    action: 'Connected inbox',      target: 'alex@company.com',          timestamp: '3d ago',  type: 'settings' },
];
