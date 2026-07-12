import type {
  VerificationApprovalConfig,
  VerificationSearchSubmission,
  VerificationSearchValues,
} from '../types';

function requiredText(value: unknown, message: string) {
  const text = String(value ?? '').trim();
  if (!text) {
    throw new Error(message);
  }
  return text;
}

export function getInitialVerificationSearchValues(
  config: VerificationApprovalConfig | null,
): VerificationSearchValues {
  return {
    environment: config?.environments[0],
    category: config?.categories[0],
  };
}

export function getVerificationSearchOptions(config: VerificationApprovalConfig | null) {
  return {
    environmentOptions: (config?.environments ?? []).map((value) => ({ value, label: value })),
    categoryOptions: (config?.categories ?? []).map((value) => ({ value, label: value })),
  };
}

export function buildVerificationSearchSubmission(
  values: VerificationSearchValues,
): VerificationSearchSubmission {
  return {
    environment: requiredText(values.environment, '请选择环境'),
    category: requiredText(values.category, '请选择类别'),
    contractNo: requiredText(values.contractNo, '请输入合同号'),
  };
}
