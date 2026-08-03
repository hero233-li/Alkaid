import { categoriesForProduct, findProduct, isDynamicApplicationLink } from './formModel';
import type {
  ApplicationLinkConfig,
  ApplicationLinkFormValues,
  ApplicationLinkSubmission,
  LinkCategory,
} from './types';

function trimOptional(value: unknown) {
  const trimmed = String(value ?? '').trim();
  return trimmed || undefined;
}

function requiredText(value: unknown, message: string) {
  const trimmed = trimOptional(value);
  if (!trimmed) {
    throw new Error(message);
  }
  return trimmed;
}

function requiredCategory(value: unknown): LinkCategory {
  if (value === '太阳码' || value === '动态链接') {
    return value;
  }
  throw new Error('请选择类别');
}

function parseDynamicLinkRequestJson(value: unknown): Record<string, unknown> {
  const text = requiredText(value, '请输入动态链接 JSON 参数');
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('动态链接 JSON 参数格式不正确');
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('动态链接 JSON 参数必须是一个对象');
  }
  return parsed as Record<string, unknown>;
}

export function buildApplicationLinkSubmission(
  config: ApplicationLinkConfig,
  values: ApplicationLinkFormValues,
): ApplicationLinkSubmission {
  const environment = requiredText(values.environment, '请选择环境');
  const productCode = requiredText(values.product, '请选择产品');
  const product = findProduct(config, productCode);
  const category = requiredCategory(values.category);

  if (!product || !product.routes.some((route) => route.environment === environment)) {
    throw new Error('当前环境下没有该产品');
  }
  if (!categoriesForProduct(product, environment).includes(category)) {
    throw new Error('当前产品在该环境下没有该类别');
  }

  const submission: ApplicationLinkSubmission = {
    env: environment,
    product: productCode,
    category,
    payload: {
      loanType: requiredText(values.loanType, '请选择首贷续贷'),
    },
  };

  const cooperationProjectId = trimOptional(values.cooperationProjectId);
  if (config.cooperationProjects.length && !cooperationProjectId) {
    throw new Error('请选择合作项目');
  }
  if (cooperationProjectId) submission.cooperationProjectId = cooperationProjectId;

  if (isDynamicApplicationLink(category)) {
    Object.assign(submission.payload, parseDynamicLinkRequestJson(values.requestJson));
  }

  const route = product.routes.find(
    (item) => item.environment === environment && item.category === category,
  );
  if (route?.requiredFields.includes('restoreStatus')) {
    submission.payload.restoreStatus = requiredText(values.restoreStatus, '请选择还原状况');
  }
  if (route?.requiredFields.includes('spcode')) {
    submission.payload.spcode = requiredText(values.spcode, '请输入企业代码 spcode');
  }

  return submission;
}
