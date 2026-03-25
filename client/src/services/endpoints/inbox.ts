import { get, post } from '../apiClient';

export interface Message {
  id: string;
  sender: string;
  content: string;
  timestamp: string;
  isAI: boolean;
}

export interface Conversation {
  id: string;
  name: string;
  email: string;
  lastMessage: string;
  timestamp: string;
  unread: number;
  status: 'replied' | 'unreplied' | 'ai-handled';
  aiHandled: boolean;
  messages: Message[];
}

export interface ConversationsParams {
  filter?: 'all' | 'unread' | 'replied' | 'ai-handled';
  search?: string;
  page?:   number;
  limit?:  number;
}

export interface SendReplyPayload {
  threadId:    string;
  content:     string;
  attachments?: string[];
}

export const inboxApi = {
  conversations: (params?: ConversationsParams)  => get<Conversation[]>('/inbox/conversations', { params }),
  thread:        (threadId: string)              => get<Conversation>(`/inbox/conversations/${threadId}`),
  sendReply:     (payload: SendReplyPayload)     => post<Message>('/inbox/reply', payload),
  markRead:      (threadId: string)              => post<void>(`/inbox/conversations/${threadId}/read`),
};
