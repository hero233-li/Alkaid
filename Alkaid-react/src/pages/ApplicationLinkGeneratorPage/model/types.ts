import type { JobActivityStatus, JobSnapshot } from '../../../types/jobs';

export type LinkCategory = '太阳码' | '动态链接';

export interface ApplicationLinkApiResponse<T> {
  ok: boolean;
  data: T;
  message?: string;
}

export interface ProductLinkConfig {
  label: string;
  value: string;
  routes: ApplicationLinkRouteConfig[];
}

export interface ApplicationLinkOption {
  label: string;
  value: string;
}

export interface ApplicationLinkRouteConfig {
  environment: string;
  category: LinkCategory;
  requiredFields: string[];
}

export interface ApplicationLinkBackendConfig {
  environments: ApplicationLinkOption[];
  products: ProductLinkConfig[];
  cooperationProjects: ApplicationLinkOption[];
}

export interface ApplicationLinkConfig extends ApplicationLinkBackendConfig {
  loanTypes: string[];
}

export interface ApplicationLinkFormValues {
  environment?: string;
  product?: string;
  category?: LinkCategory;
  cooperationProjectId?: string;
  requestJson?: string;
  loanType?: string;
  restoreStatus?: string;
  spcode?: string;
}

export interface ApplicationLinkSubmission {
  env: string;
  product: string;
  category: LinkCategory;
  cooperationProjectId?: string;
  payload: Record<string, unknown>;
}

export interface ApplicationLinkResult {
  internalUrl: string;
  externalUrl: string;
  generatedAt: string;
}

export type ApplicationLinkJobStatus = JobActivityStatus;
export type ApplicationLinkJob = JobSnapshot<{ links?: ApplicationLinkResult }>;

export interface ApplicationLinkActivity {
  jobId?: number;
  status: ApplicationLinkJobStatus;
  progress: number;
  label: string;
}
