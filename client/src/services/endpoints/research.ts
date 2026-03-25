import { get, post } from '../apiClient';

export interface ResearchQuery {
  id: string; query: string; status: 'pending' | 'running' | 'done' | 'failed';
  result?: string; sources?: string[]; createdAt: string; completedAt?: string;
}

export interface ResearchParams { page?: number; limit?: number; }

export const researchApi = {
  list:   (params?: ResearchParams) => get<ResearchQuery[]>('/research', { params }),
  get:    (id: string)              => get<ResearchQuery>(`/research/${id}`),
  run:    (query: string)           => post<ResearchQuery>('/research', { query }),
  delete: (id: string)              => post<void>(`/research/${id}/delete`),
};
