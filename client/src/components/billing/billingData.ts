export interface Plan {
  id: string; name: string; price: number; period: string;
  color: string; features: string[]; popular?: boolean;
}

export interface Invoice {
  id: string; date: string; amount: number; status: 'paid' | 'pending' | 'failed';
  description: string; downloadUrl: string;
}

export interface PaymentMethod {
  id: string; brand: string; last4: string; expiry: string; isDefault: boolean;
}

export interface UsageStat {
  label: string; used: number; limit: number; color: string; unit: string;
}

export const PLANS: Plan[] = [
  {
    id: 'starter', name: 'Starter', price: 29, period: 'month', color: '#34d399',
    features: ['2,000 emails/month', '500 leads', '1 email account', 'Basic AI replies', 'CSV import'],
  },
  {
    id: 'pro', name: 'Pro', price: 79, period: 'month', color: '#818cf8', popular: true,
    features: ['10,000 emails/month', '5,000 leads', '5 email accounts', 'Advanced AI', 'CRM integrations', 'Analytics'],
  },
  {
    id: 'business', name: 'Business', price: 199, period: 'month', color: '#c084fc',
    features: ['50,000 emails/month', 'Unlimited leads', '20 email accounts', 'Full AI suite', 'All integrations', 'Priority support', 'Custom AI training'],
  },
];

export const CURRENT_PLAN = {
  id: 'pro', name: 'Pro', price: 79, period: 'month', color: '#818cf8',
  nextBillingDate: 'April 15, 2026', startDate: 'March 15, 2026', status: 'active',
};

export const USAGE_STATS: UsageStat[] = [
  { label: 'Emails Sent',    used: 7240,  limit: 10000, color: '#818cf8', unit: 'emails' },
  { label: 'Leads',          used: 3180,  limit: 5000,  color: '#34d399', unit: 'leads'  },
  { label: 'Email Accounts', used: 3,     limit: 5,     color: '#22d3ee', unit: 'accounts' },
  { label: 'AI Replies',     used: 1840,  limit: 3000,  color: '#c084fc', unit: 'replies' },
  { label: 'Campaigns',      used: 8,     limit: 20,    color: '#fbbf24', unit: 'active'  },
  { label: 'Team Members',   used: 4,     limit: 10,    color: '#f87171', unit: 'members' },
];

export const INVOICES: Invoice[] = [
  { id: 'inv-001', date: 'Mar 15, 2026', amount: 79, status: 'paid',    description: 'Pro Plan — March 2026',   downloadUrl: '#' },
  { id: 'inv-002', date: 'Feb 15, 2026', amount: 79, status: 'paid',    description: 'Pro Plan — February 2026', downloadUrl: '#' },
  { id: 'inv-003', date: 'Jan 15, 2026', amount: 79, status: 'paid',    description: 'Pro Plan — January 2026',  downloadUrl: '#' },
  { id: 'inv-004', date: 'Dec 15, 2025', amount: 29, status: 'paid',    description: 'Starter Plan — Dec 2025',  downloadUrl: '#' },
  { id: 'inv-005', date: 'Nov 15, 2025', amount: 29, status: 'failed',  description: 'Starter Plan — Nov 2025',  downloadUrl: '#' },
];

export const PAYMENT_METHODS: PaymentMethod[] = [
  { id: 'pm-1', brand: 'Visa',       last4: '4242', expiry: '12/27', isDefault: true  },
  { id: 'pm-2', brand: 'Mastercard', last4: '8888', expiry: '09/26', isDefault: false },
];

export const COST_INSIGHTS = [
  { label: 'Estimated next bill',  value: '$79.00',  color: '#818cf8', trend: 'stable'  },
  { label: 'Avg monthly spend',    value: '$75.40',  color: '#34d399', trend: 'down'    },
  { label: 'Cost per lead',        value: '$0.025',  color: '#22d3ee', trend: 'down'    },
  { label: 'Cost per email',       value: '$0.0079', color: '#fbbf24', trend: 'stable'  },
];
