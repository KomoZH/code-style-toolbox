// fetch 封装：统一响应解包 {code,message,data}，code!=0 抛 ApiError（架构 §8）
import type {
  ConvertResponse,
  DetectResult,
  ExampleGroup,
  HistorySummary,
  ProfileSummary,
  RestoreResponse,
  SampleItem,
  StyleProfile,
} from '../types';

export class ApiError extends Error {
  code: number;

  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    throw new ApiError(resp.status, `HTTP ${resp.status}: ${await resp.text()}`);
  }
  const envelope = (await resp.json()) as { code: number; message: string; data: T };
  if (envelope.code !== 0) {
    throw new ApiError(envelope.code, envelope.message);
  }
  return envelope.data;
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),

  detect: (code: string, filename?: string) =>
    request<DetectResult>('/detect', {
      method: 'POST',
      body: JSON.stringify({ code, filename }),
    }),

  extract: (samples: SampleItem[], profileName: string, language?: string) =>
    request<StyleProfile>('/extract', {
      method: 'POST',
      body: JSON.stringify({ samples, profile_name: profileName, language }),
    }),

  listProfiles: () => request<ProfileSummary[]>('/profiles'),

  getProfile: (pid: string) => request<StyleProfile>(`/profiles/${pid}`),

  saveProfile: (profile: StyleProfile) =>
    request<StyleProfile>(`/profiles/${profile.id}`, {
      method: 'PUT',
      body: JSON.stringify(profile),
    }),

  deleteProfile: (pid: string) =>
    request<{ deleted: boolean }>(`/profiles/${pid}`, { method: 'DELETE' }),

  importProfile: (yamlText: string) =>
    request<StyleProfile>('/profiles/import', {
      method: 'POST',
      body: JSON.stringify({ yaml_text: yamlText }),
    }),

  exportUrl: (pid: string) => `/api/profiles/${pid}/export`,

  listPresets: () => request<StyleProfile[]>('/presets'),

  convert: (profileId: string, items: SampleItem[], language?: string) =>
    request<ConvertResponse>('/convert', {
      method: 'POST',
      body: JSON.stringify({ profile_id: profileId, items, language }),
    }),

  listHistory: () => request<HistorySummary[]>('/history'),

  restoreHistory: (hid: string) =>
    request<RestoreResponse>(`/history/${hid}/restore`, { method: 'POST' }),

  listExamples: () => request<ExampleGroup[]>('/examples'),
};
