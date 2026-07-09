export type JobStatus =
  | 'pending'
  | 'running'
  | 'retrying'
  | 'success'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'
  | 'timed_out';

export interface JobLog {
  id?: number;
  jobId?: number;
  taskId?: string;
  attempt?: number;
  level: string;
  step?: string;
  stepId?: string;
  message: string;
  createdAt: string;
}

export interface JobDetail {
  id: number;
  name: string;
  workflowId: string;
  status: JobStatus;
  stage: string;
  progress: number;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  errorMessage?: string;
  traceId: string;
  idempotencyKey: string;
  attemptCount: number;
  timeoutSeconds: number;
  deadlineAt?: string;
  createdAt: string;
}

export interface JobStreamStatus {
  status: JobStatus;
  progress: number;
}
