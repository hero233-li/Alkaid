import { productFieldRegistry } from './fieldRegistry';
import type {
  ProductApplicationConfig,
  ProductApplicationFormValues,
  ProductBranchConfig,
  ProductDefinitionConfig,
  ProductFieldConfig,
  ProductFieldControl,
  ProductLocationConfig,
  ProductOption,
} from './types';

function asRecord(value: unknown, context: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${context}格式错误`);
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown, context: string) {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`${context}不能为空`);
  }
  return value;
}

function asStringArray(value: unknown, context: string) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error(`${context}格式错误`);
  }
  return value as string[];
}

function asOptions(value: unknown, context: string): ProductOption[] {
  if (!Array.isArray(value)) {
    throw new Error(`${context}格式错误`);
  }
  return value.map((item, index) => {
    const option = asRecord(item, `${context}[${index}]`);
    return {
      label: asString(option.label, `${context}[${index}].label`),
      value: asString(option.value, `${context}[${index}].value`),
    };
  });
}

function asBranches(value: unknown, context: string): ProductBranchConfig[] {
  if (!Array.isArray(value)) {
    throw new Error(`${context}格式错误`);
  }
  return value.map((item, index) => {
    const branch = asRecord(item, `${context}[${index}]`);
    return {
      label: asString(branch.label, `${context}[${index}].label`),
      value: asString(branch.value, `${context}[${index}].value`),
      outlets: asOptions(branch.outlets, `${context}[${index}].outlets`),
    };
  });
}

function asLocations(value: unknown, context: string): ProductLocationConfig[] {
  if (!Array.isArray(value)) {
    throw new Error(`${context}格式错误`);
  }
  return value.map((item, index) => {
    const location = asRecord(item, `${context}[${index}]`);
    return {
      label: asString(location.label, `${context}[${index}].label`),
      value: asString(location.value, `${context}[${index}].value`),
      branches: asBranches(location.branches, `${context}[${index}].branches`),
    };
  });
}

function asProducts(value: unknown): ProductDefinitionConfig[] {
  if (!Array.isArray(value) || !value.length) {
    throw new Error('产品配置不能为空');
  }
  return value.map((item, index) => {
    const product = asRecord(item, `products[${index}]`);
    return {
      label: asString(product.label, `products[${index}].label`),
      value: asString(product.value, `products[${index}].value`),
      environments: asStringArray(product.environments, `products[${index}].environments`),
      locations: asLocations(product.locations, `products[${index}].locations`),
      fieldSets: product.fieldSets == null
        ? []
        : asStringArray(product.fieldSets, `products[${index}].fieldSets`),
      requiredFields: asStringArray(product.requiredFields, `products[${index}].requiredFields`),
    };
  });
}

function optionalBoolean(value: unknown) {
  return typeof value === 'boolean' ? value : undefined;
}

function optionalString(value: unknown) {
  return typeof value === 'string' ? value : undefined;
}

function optionalFormValue(value: unknown) {
  return typeof value === 'string' || typeof value === 'boolean' ? value : undefined;
}

function legacyControl(value: unknown): ProductFieldControl {
  return value === 'select' || value === 'switch' || value === 'input' ? value : 'input';
}

function asFields(value: unknown): ProductFieldConfig[] {
  if (!Array.isArray(value) || !value.length) {
    throw new Error('字段配置不能为空');
  }
  const names = new Set<string>();
  return value.map((item, index) => {
    const source = asRecord(item, `fields[${index}]`);
    const name = asString(source.name, `fields[${index}].name`);
    if (names.has(name)) {
      throw new Error(`字段配置重复：${name}`);
    }
    names.add(name);

    const presentation = productFieldRegistry[name];
    const sourceOptions = source.options == null ? undefined : asOptions(source.options, `fields[${index}].options`);
    return {
      name,
      label: presentation?.label ?? optionalString(source.label) ?? name,
      control: presentation?.control ?? legacyControl(source.control),
      span: presentation?.span ?? (typeof source.span === 'number' ? source.span : 8),
      required: optionalBoolean(source.required),
      editable: optionalBoolean(source.editable),
      submit: optionalBoolean(source.submit),
      searchable: presentation?.searchable ?? optionalBoolean(source.searchable),
      placeholder: presentation?.placeholder ?? optionalString(source.placeholder),
      defaultValue: optionalFormValue(source.defaultValue),
      options: sourceOptions,
      checkedLabel: presentation?.checkedLabel ?? optionalString(source.checkedLabel),
      uncheckedLabel: presentation?.uncheckedLabel ?? optionalString(source.uncheckedLabel),
      switchWidth: presentation?.switchWidth ?? (typeof source.switchWidth === 'number' ? source.switchWidth : undefined),
      persistDraft: presentation?.persistDraft ?? false,
    };
  });
}

function asFieldSets(value: unknown) {
  const source = asRecord(value, 'fieldSets');
  return Object.fromEntries(
    Object.entries(source).map(([name, fieldNames]) => [
      name,
      asStringArray(fieldNames, `fieldSets.${name}`),
    ]),
  );
}

function buildLegacyFieldSets(
  rawFields: unknown,
  products: ProductDefinitionConfig[],
) {
  if (!Array.isArray(rawFields)) {
    throw new Error('字段配置不能为空');
  }
  const sharedFields: string[] = [];
  const productFields = Object.fromEntries(products.map((product) => [product.value, [] as string[]]));

  rawFields.forEach((item, index) => {
    const field = asRecord(item, `fields[${index}]`);
    const fieldName = asString(field.name, `fields[${index}].name`);
    const boundProducts = field.products == null
      ? []
      : asStringArray(field.products, `fields[${index}].products`);
    if (!boundProducts.length) {
      sharedFields.push(fieldName);
      return;
    }
    boundProducts.forEach((product) => {
      if (productFields[product]) {
        productFields[product].push(fieldName);
      }
    });
  });

  const fieldSets: Record<string, string[]> = { __legacy_shared__: sharedFields };
  const nextProducts = products.map((product) => {
    const productSetName = `__legacy_product_${product.value}`;
    fieldSets[productSetName] = productFields[product.value];
    return { ...product, fieldSets: ['__legacy_shared__', productSetName] };
  });
  return { fieldSets, products: nextProducts };
}

function asCascadeResetMap(value: unknown, fieldNames: Set<string>) {
  if (value === undefined) {
    return {};
  }
  const source = asRecord(value, 'cascadeResetMap');
  return Object.fromEntries(
    Object.entries(source).map(([name, targets]) => {
      if (!fieldNames.has(name)) {
        throw new Error(`级联配置引用了未知字段：${name}`);
      }
      const targetNames = asStringArray(targets, `cascadeResetMap.${name}`);
      const unknownTarget = targetNames.find((target) => !fieldNames.has(target));
      if (unknownTarget) {
        throw new Error(`级联配置引用了未知字段：${unknownTarget}`);
      }
      return [name, targetNames];
    }),
  );
}

function validateConfigReferences(
  environments: ProductOption[],
  products: ProductDefinitionConfig[],
  fields: ProductFieldConfig[],
  fieldSets: Record<string, string[]>,
) {
  const environmentValues = new Set(environments.map((environment) => environment.value));
  const fieldNames = new Set(fields.map((field) => field.name));
  const fieldSetNames = new Set(Object.keys(fieldSets));
  for (const [fieldSetName, enabledFields] of Object.entries(fieldSets)) {
    const unknownField = enabledFields.find((field) => !fieldNames.has(field));
    if (unknownField) {
      throw new Error(`字段组 ${fieldSetName} 引用了未知字段：${unknownField}`);
    }
  }
  for (const product of products) {
    const unknownEnvironment = product.environments.find((environment) => !environmentValues.has(environment));
    if (unknownEnvironment) {
      throw new Error(`产品 ${product.value} 引用了未知环境：${unknownEnvironment}`);
    }
    const unknownFieldSet = product.fieldSets.find((fieldSet) => !fieldSetNames.has(fieldSet));
    if (unknownFieldSet) {
      throw new Error(`产品 ${product.value} 引用了未知字段组：${unknownFieldSet}`);
    }
    const enabledFields = new Set(product.fieldSets.flatMap((fieldSet) => fieldSets[fieldSet] || []));
    const unknownRequiredField = product.requiredFields.find((field) => (
      !fieldNames.has(field) || (!ALWAYS_VISIBLE_FIELD_NAMES.has(field) && !enabledFields.has(field))
    ));
    if (unknownRequiredField) {
      throw new Error(`产品 ${product.value} 的必填字段未启用：${unknownRequiredField}`);
    }
  }
  const environmentWithoutProduct = environments.find(
    (environment) => !products.some((product) => product.environments.includes(environment.value)),
  );
  if (environmentWithoutProduct) {
    throw new Error(`环境 ${environmentWithoutProduct.value} 没有可用产品`);
  }
}

export function adaptProductApplicationConfig(value: unknown): ProductApplicationConfig {
  const source = asRecord(value, '产品申请配置');
  const environments = asOptions(source.environments, 'environments');
  if (!environments.length) {
    throw new Error('环境配置不能为空');
  }
  let products = asProducts(source.products);
  const fields = asFields(source.fields);
  let fieldSets: Record<string, string[]>;
  if (source.fieldSets == null) {
    const legacyConfig = buildLegacyFieldSets(source.fields, products);
    products = legacyConfig.products;
    fieldSets = legacyConfig.fieldSets;
  } else {
    fieldSets = asFieldSets(source.fieldSets);
  }
  const fieldNames = new Set(fields.map((field) => field.name));
  validateConfigReferences(environments, products, fields, fieldSets);
  const version = source.version;
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    throw new Error('配置版本无效');
  }

  return {
    id: asString(source.id, '配置 ID'),
    version,
    environments,
    products,
    fields,
    fieldSets,
    cascadeResetMap: asCascadeResetMap(source.cascadeResetMap, fieldNames),
  };
}

const ALWAYS_VISIBLE_FIELD_NAMES = new Set([
  'environment',
  'product',
  'location',
  'branch',
  'outlet',
]);

function getEnabledFieldNames(
  config: ProductApplicationConfig,
  product: ProductDefinitionConfig,
) {
  return new Set([
    ...ALWAYS_VISIBLE_FIELD_NAMES,
    ...product.fieldSets.flatMap((fieldSet) => config.fieldSets[fieldSet] || []),
  ]);
}

function chooseValue(value: unknown, options: ProductOption[]) {
  return options.some((option) => option.value === value) ? String(value) : options[0]?.value || '';
}

function copyOptions(items: ProductOption[]): ProductOption[] {
  return items.map(({ value, label }) => ({ value, label }));
}

export function buildProductApplicationFields(
  config: ProductApplicationConfig,
  values: Record<string, unknown> = {},
): ProductFieldConfig[] {
  const environment = chooseValue(values.environment, config.environments);
  const availableProducts = config.products.filter((product) => product.environments.includes(environment));
  const productOptions = copyOptions(availableProducts);
  const productValue = chooseValue(values.product, productOptions);
  const product = availableProducts.find((item) => item.value === productValue) || availableProducts[0] || config.products[0];

  const locationOptions = copyOptions(product.locations);
  const locationValue = chooseValue(values.location, locationOptions);
  const location = product.locations.find((item) => item.value === locationValue) || product.locations[0];
  const branchOptions = copyOptions(location?.branches || []);
  const branchValue = chooseValue(values.branch, branchOptions);
  const branch = location?.branches.find((item) => item.value === branchValue) || location?.branches[0];
  const outletOptions = copyOptions(branch?.outlets || []);
  const enabledFieldNames = getEnabledFieldNames(config, product);

  const hierarchyOptions: Record<string, { options: ProductOption[]; value: string }> = {
    environment: { options: config.environments, value: environment },
    product: { options: productOptions, value: productValue },
    location: { options: locationOptions, value: locationValue },
    branch: { options: branchOptions, value: branchValue },
    outlet: { options: outletOptions, value: chooseValue(values.outlet, outletOptions) },
  };

  return config.fields
    .filter((field) => enabledFieldNames.has(field.name))
    .map((sourceField) => {
    const hierarchy = hierarchyOptions[sourceField.name];
    if (hierarchy) {
      return { ...sourceField, options: hierarchy.options, defaultValue: hierarchy.value };
    }
    if (sourceField.name === 'legalPerson' && !String(values.companyName || '').trim()) {
      return {
        ...sourceField,
        editable: false,
        defaultValue: true,
        checkedLabel: '农户',
        uncheckedLabel: '农户',
      };
    }
    return { ...sourceField, required: sourceField.required || product.requiredFields.includes(sourceField.name) };
    });
}

export function normalizeProductApplicationValues(
  config: ProductApplicationConfig,
  values: ProductApplicationFormValues = {},
) {
  const normalizedValues: ProductApplicationFormValues = { ...values };
  const activeFields = buildProductApplicationFields(config, normalizedValues);
  const activeFieldNames = new Set(activeFields.map((field) => field.name));
  config.fields.forEach((field) => {
    if (!activeFieldNames.has(field.name)) {
      delete normalizedValues[field.name];
    }
  });
  for (const field of activeFields) {
    if (field.control === 'select') {
      normalizedValues[field.name] = field.defaultValue;
    } else if (normalizedValues[field.name] === undefined && field.defaultValue !== undefined) {
      normalizedValues[field.name] = field.defaultValue;
    }
  }
  if (!String(normalizedValues.companyName || '').trim()) {
    normalizedValues.legalPerson = true;
  }
  return normalizedValues;
}

export function getInitialProductApplicationValues(config: ProductApplicationConfig) {
  return normalizeProductApplicationValues(config);
}

export function getOptionLabel(field: ProductFieldConfig | undefined, value: unknown) {
  return field?.options?.find((option) => option.value === value)?.label || String(value || '-');
}
