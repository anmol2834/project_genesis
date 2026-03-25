import { get, post, patch, del } from '../apiClient';

export type MemberRole   = 'owner' | 'admin' | 'member';
export type MemberStatus = 'active' | 'invited' | 'suspended';

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

export interface InviteMemberPayload  { email: string; role: MemberRole; permissions?: string[]; }
export interface UpdateMemberPayload  { role?: MemberRole; status?: MemberStatus; permissions?: string[]; }

export const teamApi = {
  list:    ()                                      => get<TeamMember[]>('/team/members'),
  invite:  (p: InviteMemberPayload)               => post<TeamMember>('/team/invite', p),
  update:  (id: string, p: UpdateMemberPayload)   => patch<TeamMember>(`/team/members/${id}`, p),
  remove:  (id: string)                           => del<void>(`/team/members/${id}`),
  activity: ()                                    => get<unknown[]>('/team/activity'),
};
