import type { ApiResponse } from '../types';
import { apiClient } from './client';
import type { JobStatus } from '../types/jobs';

export interface WorkflowGuideItem {
  title: string;
  description: string;
  code: string;
}

export interface WorkflowLabGuide {
  title: string;
  summary: string;
  architecture: WorkflowGuideItem[];
  statuses: WorkflowGuideItem[];
  keyFiles: WorkflowGuideItem[];
  changeSteps: WorkflowGuideItem[];
  apis: WorkflowGuideItem[];
  definitionExample: string;
  documentPath: string;
}

export interface WorkflowRuntimeSnapshot {
  workerThreads: number;
  activeWorkers: number;
  queuedTasks: number;
  completedTasks: number;
  trackedJobs: number;
}

export interface WorkflowLabJob {
  id: number;
  name: string;
  status: JobStatus;
  stage: string;
  progress: number;
  traceId: string;
  idempotencyKey: string;
  attemptCount: number;
  createdAt: string;
  deadlineAt?: string;
}

export async function getWorkflowLabGuide() {
  const { data } = await apiClient.get<ApiResponse<WorkflowLabGuide>>('/workflow-lab/guide');
  if (!data.ok) {
    throw new Error(data.message || '获取 Workflow 指南失败');
  }
  return data.data;
}

export async function getWorkflowRuntime() {
  const { data } =
    await apiClient.get<ApiResponse<WorkflowRuntimeSnapshot>>('/workflow-lab/runtime');
  if (!data.ok) {
    throw new Error(data.message || '获取 Worker 运行状态失败');
  }
  return data.data;
}

export async function submitWorkflowLab(payload: {
  name: string;
  durationMs: number;
  simulateFailure: boolean;
}) {
  const requestId = crypto.randomUUID();
  const { data } = await apiClient.post<ApiResponse<WorkflowLabJob>>(
    '/workflow-lab/jobs',
    payload,
    {
      headers: {
        'X-Idempotency-Key': requestId,
        'X-Trace-ID': requestId.split('-').join(''),
      },
    },
  );
  if (!data.ok) {
    throw new Error(data.message || '提交 Workflow 实验失败');
  }
  return data.data;
}
