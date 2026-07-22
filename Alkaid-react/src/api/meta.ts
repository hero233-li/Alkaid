import type { ApiResponse } from '../types';
import { apiClient } from './client';

export interface FeatureCapability {
  enabled: boolean;
  reason: string;
}

export interface DeploymentCapabilities {
  externalSystemMode: 'mock' | 'real';
  features: Record<string, FeatureCapability>;
}

export async function getDeploymentCapabilities() {
  const { data } = await apiClient.get<ApiResponse<DeploymentCapabilities>>('/meta/capabilities');
  if (!data.ok) {
    throw new Error(data.message || '获取后端能力失败');
  }
  return data.data;
}
