import { chatClient } from '../lib/axios';
import type { CapabilitiesResponse, ChatRequest, ChatResponse, SessionHistoryResponse } from '../types/api';

export const chatApi = {
  sendMessage: (body: ChatRequest) =>
    chatClient.post<ChatResponse>('/api/chat/message', body).then((r) => r.data),

  capabilities: () =>
    chatClient.get<CapabilitiesResponse>('/api/chat/capabilities').then((r) => r.data),

  sessionHistory: (session_id: string) =>
    chatClient.get<SessionHistoryResponse>(`/api/chat/session/${encodeURIComponent(session_id)}/history`).then((r) => r.data),
};
