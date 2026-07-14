import type { ApiResponse } from '../../../types';
import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import type { ProductApplicationResult, ProductApplicationSubmission } from '../model/types';

export async function getProductApplicationConfigDto(): Promise<unknown> {
  const { data } = await apiClient.get<ApiResponse<unknown>>('/product-data/applications/config');
  if (!data.ok) {
    throw new Error(data.message || '获取产品申请配置失败');
  }
  return data.data;
}

export async function executeProductApplication(payload: ProductApplicationSubmission) {
  const { data } = await apiClient.post<ApiResponse<ProductApplicationResult>>(
    '/product-data/applications',
    payload,
    {
      headers: createWorkflowHeaders(),
    },
  );
  if (!data.ok) {
    throw new Error(data.message || '产品申请执行失败');
  }
  return data.data;
}
