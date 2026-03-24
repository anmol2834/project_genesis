export type LeadStatus = 'new' | 'contacted' | 'engaged' | 'unresponsive';
export type LeadTag = 'hot' | 'warm' | 'cold' | 'vip' | 'decision-maker' | 'technical';

export interface Lead {
  id: string;
  name: string;
  email: string;
  company: string;
  role: string;
  status: LeadStatus;
  tags: LeadTag[];
  campaign: string | null;
  lastActivity: string;
  addedAt: string;
  avatarColor: string;
  score: number; // 0–100
}

export const STATUS_CONFIG: Record<LeadStatus, { label: string; color: string; bg: string; darkBg: string }> = {
  new:          { label: 'New',          color: '#60a5fa', bg: 'rgba(96,165,250,0.1)',  darkBg: 'rgba(96,165,250,0.15)'  },
  contacted:    { label: 'Contacted',    color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',  darkBg: 'rgba(251,191,36,0.15)'  },
  engaged:      { label: 'Engaged',      color: '#34d399', bg: 'rgba(52,211,153,0.1)',  darkBg: 'rgba(52,211,153,0.15)'  },
  unresponsive: { label: 'Unresponsive', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', darkBg: 'rgba(148,163,184,0.12)' },
};

export const TAG_CONFIG: Record<LeadTag, { color: string; bg: string }> = {
  hot:             { color: '#ef4444', bg: 'rgba(239,68,68,0.12)'   },
  warm:            { color: '#f97316', bg: 'rgba(249,115,22,0.12)'  },
  cold:            { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)'  },
  vip:             { color: '#c084fc', bg: 'rgba(192,132,252,0.12)' },
  'decision-maker':{ color: '#fbbf24', bg: 'rgba(251,191,36,0.12)'  },
  technical:       { color: '#34d399', bg: 'rgba(52,211,153,0.12)'  },
};

export const LEADS: Lead[] = [
  { id:'1',  name:'Sarah Anderson',   email:'sarah@techcorp.com',      company:'TechCorp',        role:'VP of Sales',        status:'engaged',      tags:['hot','vip'],              campaign:'Q4 Enterprise Outreach', lastActivity:'2m ago',    addedAt:'Oct 1',  avatarColor:'#818cf8', score:92 },
  { id:'2',  name:'Mike Torres',      email:'mike@ventures.io',        company:'Ventures IO',     role:'CEO',                status:'engaged',      tags:['hot','decision-maker'],   campaign:'SaaS Decision Makers',   lastActivity:'18m ago',   addedAt:'Oct 3',  avatarColor:'#c084fc', score:88 },
  { id:'3',  name:'Lisa Ventures',    email:'lisa@lv.capital',         company:'LV Capital',      role:'Partner',            status:'contacted',    tags:['warm','vip'],             campaign:'Q4 Enterprise Outreach', lastActivity:'1h ago',    addedAt:'Sep 28', avatarColor:'#22d3ee', score:74 },
  { id:'4',  name:'James Dev',        email:'james@devteam.co',        company:'DevTeam Co',      role:'CTO',                status:'engaged',      tags:['warm','technical'],       campaign:'SaaS Decision Makers',   lastActivity:'2h ago',    addedAt:'Sep 25', avatarColor:'#34d399', score:81 },
  { id:'5',  name:'Priya Rajan',      email:'priya@growth.in',         company:'Growth Inc',      role:'Head of Growth',     status:'contacted',    tags:['warm'],                   campaign:'Q4 Enterprise Outreach', lastActivity:'3h ago',    addedAt:'Sep 20', avatarColor:'#fbbf24', score:67 },
  { id:'6',  name:'Alex Chen',        email:'alex@startup.xyz',        company:'Startup XYZ',     role:'Founder',            status:'new',          tags:['cold'],                   campaign:null,                     lastActivity:'5h ago',    addedAt:'Oct 10', avatarColor:'#f472b6', score:45 },
  { id:'7',  name:'David Kim',        email:'david@enterprise.com',    company:'Enterprise Co',   role:'Director of IT',     status:'new',          tags:['cold','technical'],       campaign:null,                     lastActivity:'1d ago',    addedAt:'Oct 12', avatarColor:'#818cf8', score:38 },
  { id:'8',  name:'Emma Wilson',      email:'emma@scale.io',           company:'Scale IO',        role:'CMO',                status:'contacted',    tags:['warm','decision-maker'],  campaign:'SaaS Decision Makers',   lastActivity:'1d ago',    addedAt:'Sep 15', avatarColor:'#34d399', score:71 },
  { id:'9',  name:'Ryan Patel',       email:'ryan@b2b.co',             company:'B2B Solutions',   role:'Sales Manager',      status:'unresponsive', tags:['cold'],                   campaign:'Cold Outbound — Series B',lastActivity:'3d ago',   addedAt:'Sep 5',  avatarColor:'#fbbf24', score:22 },
  { id:'10', name:'Sophia Lee',       email:'sophia@fintech.io',       company:'FinTech IO',      role:'CFO',                status:'engaged',      tags:['hot','vip','decision-maker'],campaign:'Q4 Enterprise Outreach',lastActivity:'30m ago',  addedAt:'Oct 5',  avatarColor:'#c084fc', score:95 },
  { id:'11', name:'Carlos Mendez',    email:'carlos@saas.mx',          company:'SaaS MX',         role:'Product Lead',       status:'new',          tags:['warm'],                   campaign:null,                     lastActivity:'2d ago',    addedAt:'Oct 14', avatarColor:'#22d3ee', score:51 },
  { id:'12', name:'Nina Johansson',   email:'nina@nordic.se',          company:'Nordic Tech',     role:'CEO',                status:'contacted',    tags:['warm','decision-maker'],  campaign:'SaaS Decision Makers',   lastActivity:'4h ago',    addedAt:'Sep 30', avatarColor:'#f472b6', score:63 },
  { id:'13', name:'Tom Bradley',      email:'tom@growth.uk',           company:'Growth UK',       role:'Head of Sales',      status:'unresponsive', tags:['cold'],                   campaign:'Cold Outbound — Series B',lastActivity:'5d ago',   addedAt:'Aug 28', avatarColor:'#818cf8', score:18 },
  { id:'14', name:'Aisha Okonkwo',    email:'aisha@africa.tech',       company:'Africa Tech',     role:'CTO',                status:'new',          tags:['hot','technical'],        campaign:null,                     lastActivity:'6h ago',    addedAt:'Oct 15', avatarColor:'#34d399', score:58 },
  { id:'15', name:'Lucas Ferreira',   email:'lucas@latam.io',          company:'LatAm IO',        role:'VP Engineering',     status:'engaged',      tags:['warm','technical'],       campaign:'SaaS Decision Makers',   lastActivity:'45m ago',   addedAt:'Oct 2',  avatarColor:'#fbbf24', score:77 },
];
