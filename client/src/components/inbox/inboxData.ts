export type MessageRole = 'received' | 'sent';
export type ConvStatus = 'active' | 'replied' | 'waiting';
export type FilterTab = 'all' | 'unread' | 'hot';
export type LeadTag = 'hot' | 'warm' | 'cold';

export interface Message {
  id: string;
  role: MessageRole;
  text: string;
  time: string;
  status?: 'sent' | 'delivered' | 'read';
  // Draft fields (populated on incoming messages with AI drafts)
  draft_message?: string;
  message_id?: string;
  message_state?: 'received' | 'drafted' | 'queued' | 'sent' | 'failed';
}

export interface Conversation {
  id: string;
  name: string;
  email: string;
  avatar: string;
  avatarColor: string;
  subject: string;
  snippet: string;
  time: string;
  unread: number;
  status: ConvStatus;
  leadTag: LeadTag;
  priority: 'high' | 'medium' | 'low';
  draft?: string;
  // For send-draft API call
  draftMessageId?: string;
  messages: Message[];
}

const LEAD_ORDER: Record<LeadTag, number> = { hot: 0, warm: 1, cold: 2 };

export const CONVERSATIONS: Conversation[] = ([
  {
    id: '1',
    name: 'Sarah Anderson',
    email: 'sarah@techcorp.com',
    avatar: 'SA',
    avatarColor: '#818cf8',
    subject: 'Q4 Proposal Review',
    snippet: 'Hi, I wanted to follow up on the proposal we discussed...',
    time: '2m ago',
    unread: 3,
    status: 'waiting',
    leadTag: 'hot',
    priority: 'high',
    draft: 'Thursday at 3 PM works perfectly for me. I\'ll send a calendar invite shortly.',
    messages: [
      { id: 'm1', role: 'received', text: 'Hi! I wanted to follow up on the Q4 proposal we discussed last week. Have you had a chance to review it?', time: '10:02 AM' },
      { id: 'm2', role: 'sent', text: 'Hey Sarah! Yes, I reviewed it yesterday. Overall it looks great. I have a few minor points to discuss.', time: '10:15 AM', status: 'read' },
      { id: 'm3', role: 'received', text: 'Perfect! Can we schedule a quick call this week to go over those points? I\'m free Thursday or Friday afternoon.', time: '10:18 AM' },
      { id: 'm4', role: 'received', text: 'Also, I\'ve attached the updated budget breakdown for your reference.', time: '10:19 AM' },
    ],
  },
  {
    id: '2',
    name: 'Mike Torres',
    email: 'mike@ventures.io',
    avatar: 'MT',
    avatarColor: '#c084fc',
    subject: 'Partnership Opportunity',
    snippet: 'We have an exciting opportunity that aligns perfectly...',
    time: '14m ago',
    unread: 1,
    status: 'active',
    leadTag: 'hot',
    priority: 'high',
    draft: 'Sounds great, Mike! Looking forward to reviewing the deck. Let\'s connect early next week to discuss further.',
    messages: [
      { id: 'm1', role: 'received', text: 'We have an exciting partnership opportunity that aligns perfectly with your platform\'s goals. Would love to connect!', time: '9:45 AM' },
      { id: 'm2', role: 'sent', text: 'Thank you for reaching out, Mike! This sounds very interesting. Could you share more details about the partnership structure you have in mind?', time: '9:46 AM', status: 'read' },
      { id: 'm3', role: 'received', text: 'Absolutely! We\'re thinking a revenue-share model. I\'ll send over a detailed deck by EOD.', time: '9:52 AM' },
    ],
  },
  {
    id: '3',
    name: 'Lisa Ventures',
    email: 'lisa@lv.capital',
    avatar: 'LV',
    avatarColor: '#22d3ee',
    subject: 'Follow-up on our call',
    snippet: 'Great speaking with you! As discussed, attaching the deck...',
    time: '1h ago',
    unread: 0,
    status: 'replied',
    leadTag: 'warm',
    priority: 'medium',
    messages: [
      { id: 'm1', role: 'received', text: 'Great speaking with you today! As discussed, I\'m attaching the investment deck for your review.', time: '8:30 AM' },
      { id: 'm2', role: 'sent', text: 'Thanks Lisa! I\'ll go through it this evening and get back to you by tomorrow morning.', time: '8:45 AM', status: 'read' },
      { id: 'm3', role: 'received', text: 'Perfect. Let me know if you have any questions. Looking forward to your thoughts!', time: '8:47 AM' },
    ],
  },
  {
    id: '4',
    name: 'James Dev',
    email: 'james@devteam.co',
    avatar: 'JD',
    avatarColor: '#34d399',
    subject: 'API Integration — Urgent',
    snippet: 'Quick question about the API integration we are working on...',
    time: '2h ago',
    unread: 0,
    status: 'replied',
    leadTag: 'warm',
    priority: 'high',
    messages: [
      { id: 'm1', role: 'received', text: 'Quick question about the API integration — we\'re getting a 401 on the webhook endpoint. Is there a new auth header required?', time: '7:15 AM' },
      { id: 'm2', role: 'sent', text: 'Yes! We updated the auth last week. You need to pass X-API-Key in the header. I\'ll send the updated docs.', time: '7:22 AM', status: 'read' },
      { id: 'm3', role: 'received', text: 'Got it, that fixed it! Thanks for the quick response.', time: '7:30 AM' },
    ],
  },
  {
    id: '5',
    name: 'Priya Rajan',
    email: 'priya@growth.in',
    avatar: 'PR',
    avatarColor: '#fbbf24',
    subject: 'Campaign Results — Q3',
    snippet: 'Sharing the final numbers from our Q3 outreach campaign...',
    time: '3h ago',
    unread: 0,
    status: 'replied',
    leadTag: 'cold',
    priority: 'medium',
    messages: [
      { id: 'm1', role: 'received', text: 'Sharing the final numbers from our Q3 outreach campaign. Open rate: 42%, Reply rate: 18%. Really happy with the results!', time: '6:00 AM' },
      { id: 'm2', role: 'sent', text: 'These are fantastic results, Priya! A 42% open rate is well above industry average. Would you like to schedule a debrief to plan Q4 strategy?', time: '6:01 AM', status: 'read' },
      { id: 'm3', role: 'received', text: 'Yes! Let\'s do that. I\'ll send a calendar invite for next week.', time: '6:05 AM' },
    ],
  },
  {
    id: '6',
    name: 'Alex Chen',
    email: 'alex@startup.xyz',
    avatar: 'AC',
    avatarColor: '#f472b6',
    subject: 'Demo Request',
    snippet: 'We\'d love to see a live demo of your automation platform...',
    time: '5h ago',
    unread: 2,
    status: 'waiting',
    leadTag: 'cold',
    priority: 'medium',
    draft: 'Hi Alex! Yes, our Growth plan at $1,999/month covers up to 50 seats. Happy to schedule a live demo — what time works for your team?',
    messages: [
      { id: 'm1', role: 'received', text: 'We\'d love to see a live demo of your automation platform. We\'re evaluating tools for our sales team of 50 people.', time: '4:00 AM' },
      { id: 'm2', role: 'received', text: 'Our budget is around $2k/month. Does that work for your enterprise plan?', time: '4:02 AM' },
    ],
  },
] as Conversation[]).sort((a, b) => LEAD_ORDER[a.leadTag] - LEAD_ORDER[b.leadTag]);
