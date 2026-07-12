import type {
  BusinessAccessConfig,
  BusinessAccessSearchSubmission,
  BusinessAccessSearchValues,
} from '../types';

export interface BusinessAccessOption {
  value: string;
  label: string;
}

function optionalTrimmedText(value: unknown) {
  const text = String(value ?? '').trim();
  return text || undefined;
}

function requiredTrimmedText(value: unknown, message: string) {
  const text = optionalTrimmedText(value);
  if (!text) {
    throw new Error(message);
  }
  return text;
}

export function getInitialBusinessAccessSearchValues(
  config: BusinessAccessConfig | null,
): BusinessAccessSearchValues {
  return { environment: config?.environments[0] };
}

export function getBusinessAccessEnvironmentOptions(
  config: BusinessAccessConfig | null,
): BusinessAccessOption[] {
  return (config?.environments ?? []).map((value) => ({ value, label: value }));
}

export function validateBusinessAccessSearchCriteria(values: BusinessAccessSearchValues) {
  if (!optionalTrimmedText(values.name) && !optionalTrimmedText(values.certificateNo)) {
    throw new Error('姓名和身份证号至少填写一个');
  }
}

export function buildBusinessAccessSearchSubmission(
  values: BusinessAccessSearchValues,
): BusinessAccessSearchSubmission {
  validateBusinessAccessSearchCriteria(values);
  return {
    environment: requiredTrimmedText(values.environment, '请选择环境'),
    name: optionalTrimmedText(values.name),
    certificateNo: optionalTrimmedText(values.certificateNo),
  };
}
