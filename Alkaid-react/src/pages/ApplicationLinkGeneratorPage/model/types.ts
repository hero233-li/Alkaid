export type LinkCategory = '太阳码' | '动态链接';

export interface ApplicationLinkApiResponse<T> {
  ok: boolean;
  data: T;
  message?: string;
}

export interface ProductLinkConfig {
  name: string;
  environments: string[];
  categoriesByEnvironment: Record<string, LinkCategory[]>;
  extraFields?: Array<'restoreStatus' | 'spcode'>;
}

export interface ApplicationLinkConfig {
  environments: string[];
  cooperationProjects: string[];
  loanTypes: string[];
  products: ProductLinkConfig[];
}

export interface ApplicationLinkFormValues {
  environment?: string;
  product?: string;
  category?: LinkCategory;
  cooperationProject?: string;
  requestJson?: string;
  loanType?: string;
  restoreStatus?: string;
  spcode?: string;
}

export interface ApplicationLinkSubmission {
  environment: string;
  product: string;
  category: LinkCategory;
  cooperationProject: string;
  loanType: string;
  recommender?: string;
  recommenderPhone?: string;
  requestJson?: Record<string, unknown>;
  restoreStatus?: string;
  spcode?: string;
}

export interface ApplicationLinkResult {
  internalUrl: string;
  externalUrl: string;
  generatedAt: string;
}

export type ApplicationLinkJobStatus =
  | 'submitting'
  | 'pending'
  | 'running'
  | 'retrying'
  | 'success'
  | 'failed'
  | 'cancelled'
  | 'timed_out';

export interface ApplicationLinkJob {
  id: number;
  status: ApplicationLinkJobStatus;
  progress: number;
  result: Record<string, unknown>;
  errorMessage?: string;
}

export interface ApplicationLinkActivity {
  jobId?: number;
  status: ApplicationLinkJobStatus;
  progress: number;
  label: string;
}
