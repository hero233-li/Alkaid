import type { JobLog, JobStatus } from '../../../types/jobs';

export type ProductApplicationFormValue = string | boolean | undefined;
export type ProductApplicationFormValues = Record<string, ProductApplicationFormValue>;
export type ProductFieldControl = 'input' | 'select' | 'switch';

export interface ProductOption {
  label: string;
  value: string;
}

export interface ProductFieldConfig {
  name: string;
  label: string;
  control: ProductFieldControl;
  span: number;
  required?: boolean;
  editable?: boolean;
  submit?: boolean;
  searchable?: boolean;
  placeholder?: string;
  defaultValue?: ProductApplicationFormValue;
  options?: ProductOption[];
  checkedLabel?: string;
  uncheckedLabel?: string;
  switchWidth?: number;
  persistDraft: boolean;
}

export interface ProductBranchConfig extends ProductOption {
  outlets: ProductOption[];
}

export interface ProductLocationConfig extends ProductOption {
  branches: ProductBranchConfig[];
}

export interface ProductDefinitionConfig extends ProductOption {
  environments: string[];
  locations: ProductLocationConfig[];
  fieldSets: string[];
  requiredFields: string[];
}

export interface ProductApplicationConfig {
  id: string;
  version: number;
  environments: ProductOption[];
  products: ProductDefinitionConfig[];
  fields: ProductFieldConfig[];
  fieldSets: Record<string, string[]>;
  cascadeResetMap: Record<string, string[]>;
}

export interface ProductApplicationResult {
  id: number;
  name: string;
  product: string;
  status: JobStatus;
  stage: string;
  progress: number;
  createdAt: string;
  payload: Record<string, unknown>;
  logs: JobLog[];
  errorMessage?: string;
  traceId: string;
  idempotencyKey: string;
  attemptCount: number;
  deadlineAt?: string;
}

export interface ProductApplicationSubmission {
  name: string;
  product: string;
  payload: Record<string, unknown>;
}

export interface ProductApplyPageProps {
  pageInstanceKey: string;
}
