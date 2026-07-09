import type {Dayjs} from 'dayjs';

export interface HighFrequencySearchValues {
    environment: string;
    useDefaultParams: boolean;
    cardNo?: string;
    startDate?: Dayjs;
    endDate?: Dayjs
}

export interface HighFrequencyQueryPayload {
    environment: string;
    cardNo?: string;
    queryStartDate?: string;
    queryEndDate?: string
}

export interface Risk050009Detail {
    cardNo: string;
    counterparty: string;
    counterpartyCardNo: string;
    transactionTime: string;
    tellerName: string;
    transferScope: string;
    organizationNo: string
}

export interface DynamicResultColumn {
    key: string;
    title: string;
    type?: 'text' | 'tag' | 'action';
    tagColors?: Record<string, string>;
    actionLabel?: string
}

export interface DynamicQueryResult {
    title: string;
    functionCode: string;
    functionName: string;
    head: DynamicResultColumn[];
    body: Record<string, unknown>[];
    columns?: DynamicResultColumn[];
    rows?: Record<string, unknown>[]
}

export interface ApiResponse<T> {
    ok: boolean;
    data: T;
    message?: string
}

export type JobStatus =
    'submitting'
    | 'pending'
    | 'running'
    | 'retrying'
    | 'success'
    | 'failed'
    | 'cancelled'
    | 'timed_out';

export interface JobSubmission {
    id: number;
    status: JobStatus;
    progress: number
}

export interface WorkflowJob {
    id: number;
    status: JobStatus;
    progress: number;
    currentStep?: string;
    result: Record<string, unknown>;
    errorMessage?: string
}

export interface WorkflowActivity {
    jobId?: number;
    label: string;
    status: JobStatus;
    progress: number;
    currentStep?: string
}
