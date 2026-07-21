import type { Dayjs } from 'dayjs';
import type {
  JobActivityStatus,
  JobSnapshot,
  JobSubmission as SharedJobSubmission,
} from '../../types/jobs';

export interface HighFrequencySearchValues {
  environment: string;
  useDefaultParams: boolean;
  cardNo?: string;
  startDate?: Dayjs;
  endDate?: Dayjs;
}

export interface HighFrequencyQueryPayload {
  environment: string;
  cardNo?: string;
  queryStartDate?: string;
  queryEndDate?: string;
}

export interface Risk050009Detail {
  cardNo: string;
  counterparty: string;
  counterpartyCardNo: string;
  transactionTime: string;
  tellerName: string;
  transferScope: string;
  organizationNo: string;
}

export interface DynamicResultColumn {
  key: string;
  title: string;
  type?: 'text' | 'tag' | 'action';
  tagColors?: Record<string, string>;
  actionLabel?: string;
}

export interface DynamicQueryResult {
  title: string;
  functionCode: string;
  functionName: string;
  head: DynamicResultColumn[];
  body: Record<string, unknown>[];
  columns?: DynamicResultColumn[];
  rows?: Record<string, unknown>[];
}

export interface ApiResponse<T> {
  ok: boolean;
  data: T;
  message?: string;
}

export type JobStatus = JobActivityStatus;
export type JobSubmission = SharedJobSubmission;
export type WorkflowJob = JobSnapshot<{ queryResult?: DynamicQueryResult }>;

export interface WorkflowActivity {
  jobId?: number;
  label: string;
  status: JobStatus;
  progress: number;
  currentStep?: string;
}
