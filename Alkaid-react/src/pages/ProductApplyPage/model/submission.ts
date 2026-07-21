import { buildProductApplicationFields, getOptionLabel } from './configAdapter';
import type {
  ProductApplicationConfig,
  ProductApplicationFormValues,
  ProductApplicationSubmission,
} from './types';

export function buildProductSubmission(
  config: ProductApplicationConfig,
  values: ProductApplicationFormValues,
): ProductApplicationSubmission {
  const activeFields = buildProductApplicationFields(config, values);
  const productCode = String(values.product || '');
  if (!productCode) {
    throw new Error('请选择产品');
  }
  const payload = Object.fromEntries(
    activeFields
      .filter((field) => field.submit !== false && values[field.name] !== undefined)
      .map((field) => [field.name, values[field.name]]),
  );
  const companyName = String(values.companyName || '').trim();
  payload.customerType = companyName
    ? values.legalPerson === false
      ? 'shareholder'
      : 'legal_person'
    : 'farmer';
  const productField = activeFields.find((field) => field.name === 'product');
  const productLabel = getOptionLabel(productField, productCode);
  return {
    name: `${productLabel}-产品申请`,
    product: productCode,
    payload,
  };
}
