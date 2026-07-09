import { apiClient } from './client';
import type { ApiResponse, WorkbenchHistoryDetail, WorkbenchHistoryItem, WorkbenchRequestPayload, WorkbenchResponsePayload } from '../types';

export interface WorkbenchFilePart {
  partName: string;
  file: File;
}

export async function executeWorkbenchRequest(payload: WorkbenchRequestPayload, files: WorkbenchFilePart[] = []) {
  const timeout = Math.max(payload.timeoutSeconds * 1000 + 5000, 15000);
  if (files.length > 0) {
    const formData = new FormData();
    formData.append('payload', JSON.stringify(payload));
    files.forEach((item) => formData.append(item.partName, item.file, item.file.name));
    const response = await apiClient.post<ApiResponse<WorkbenchResponsePayload>>('/workbench/execute-multipart', formData, {
      timeout,
    });
    if (!response.data.ok) {
      throw new Error(response.data.message || '接口调用失败');
    }
    return response.data.data;
  }

  const response = await apiClient.post<ApiResponse<WorkbenchResponsePayload>>('/workbench/execute', payload, {
    timeout,
  });
  if (!response.data.ok) {
    throw new Error(response.data.message || '接口调用失败');
  }
  return response.data.data;
}

export async function fetchWorkbenchHistory(limit = 80) {
  const response = await apiClient.get<ApiResponse<WorkbenchHistoryItem[]>>('/workbench/history', {
    params: { limit },
  });
  if (!response.data.ok) {
    throw new Error(response.data.message || '请求历史获取失败');
  }
  return response.data.data;
}

export async function fetchWorkbenchHistoryDetail(id: number) {
  const response = await apiClient.get<ApiResponse<WorkbenchHistoryDetail>>(`/workbench/history/${id}`);
  if (!response.data.ok) {
    throw new Error(response.data.message || '请求历史详情获取失败');
  }
  return response.data.data;
}

export async function renameWorkbenchHistory(id: number, name: string) {
  const response = await apiClient.post<ApiResponse<WorkbenchHistoryItem>>(`/workbench/history/${id}/rename`, { name });
  if (!response.data.ok) {
    throw new Error(response.data.message || '请求名称修改失败');
  }
  return response.data.data;
}

export async function deleteWorkbenchHistory(id: number) {
  const response = await apiClient.delete<ApiResponse<void>>(`/workbench/history/${id}`);
  if (!response.data.ok) {
    throw new Error(response.data.message || '请求删除失败');
  }
}

export async function clearWorkbenchHistory() {
  const response = await apiClient.delete<ApiResponse<void>>('/workbench/history');
  if (!response.data.ok) {
    throw new Error(response.data.message || '请求历史清理失败');
  }
}
