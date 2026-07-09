import type { ApiResponse, ReleaseNote } from '../types';
import { apiClient } from './client';

function unwrap<T>(response: ApiResponse<T>, fallbackMessage: string) {
  if (!response.ok) {
    throw new Error(response.message || fallbackMessage);
  }
  return response.data;
}

export async function listReleaseNotes() {
  const { data } = await apiClient.get<ApiResponse<ReleaseNote[]>>('/portal/releases');
  return unwrap(data, '获取版本记录失败');
}

export async function createReleaseNote(payload: { version: string; content: string }) {
  const { data } = await apiClient.post<ApiResponse<ReleaseNote>>('/portal/releases', payload);
  return unwrap(data, '新增版本失败');
}

export async function updateReleaseNote(id: number, payload: { version: string; content: string }) {
  const { data } = await apiClient.put<ApiResponse<ReleaseNote>>(`/portal/releases/${id}`, payload);
  return unwrap(data, '修改版本失败');
}

export async function deleteReleaseNote(id: number) {
  const { data } = await apiClient.delete<ApiResponse<void>>(`/portal/releases/${id}`);
  return unwrap(data, '删除版本失败');
}

export async function getHomeShortcutKeys() {
  const { data } = await apiClient.get<ApiResponse<string[]>>('/portal/home-shortcuts');
  return unwrap(data, '获取首页入口失败');
}

export async function saveHomeShortcutKeys(menuKeys: string[]) {
  const { data } = await apiClient.put<ApiResponse<string[]>>('/portal/home-shortcuts', { menuKeys });
  return unwrap(data, '保存首页入口失败');
}
