import type {
  ApplicationLinkConfig,
  ApplicationLinkFormValues,
  LinkCategory,
  ProductLinkConfig,
} from './types';

export interface ApplicationLinkOption {
  value: string;
  label: string;
}

export interface ApplicationLinkFormModel {
  environment?: string;
  product?: ProductLinkConfig;
  category?: LinkCategory;
  dynamic: boolean;
  showRestoreStatus: boolean;
  showSpcode: boolean;
  environmentOptions: ApplicationLinkOption[];
  productOptions: ApplicationLinkOption[];
  categoryOptions: ApplicationLinkOption[];
  cooperationProjectOptions: ApplicationLinkOption[];
  loanTypeOptions: ApplicationLinkOption[];
  restoreStatusOptions: ApplicationLinkOption[];
}

export const restoreStatusValues = ['正常', '已还原', '待还原'];
const categoryOrder: LinkCategory[] = ['太阳码', '动态链接'];

export function toOptions(items: string[] = []): ApplicationLinkOption[] {
  return items.map((value) => ({ value, label: value }));
}

export function isDynamicApplicationLink(category?: LinkCategory) {
  return category === '动态链接';
}

export function findProduct(config: ApplicationLinkConfig, productName?: string) {
  return config.products.find((item) => item.name === productName);
}

export function productsForEnvironment(config: ApplicationLinkConfig, environment?: string) {
  return environment
    ? config.products.filter((item) => item.environments.includes(environment))
    : [];
}

export function categoriesForProduct(
  product: ProductLinkConfig | undefined,
  environment: string | undefined,
) {
  return environment && product ? product.categoriesByEnvironment[environment] ?? [] : [];
}

export function categoriesForEnvironment(
  config: ApplicationLinkConfig,
  environment?: string,
) {
  const supportedCategories = new Set(
    productsForEnvironment(config, environment).flatMap((product) => (
      categoriesForProduct(product, environment)
    )),
  );
  return categoryOrder.filter((category) => supportedCategories.has(category));
}

export function productsForEnvironmentAndCategory(
  config: ApplicationLinkConfig,
  environment: string | undefined,
  category?: LinkCategory,
) {
  return productsForEnvironment(config, environment).filter((product) => (
    category ? categoriesForProduct(product, environment).includes(category) : true
  ));
}

function firstCategoryForEnvironment(
  config: ApplicationLinkConfig,
  environment?: string,
) {
  return categoriesForEnvironment(config, environment)[0];
}

function firstProductForEnvironmentAndCategory(
  config: ApplicationLinkConfig,
  environment?: string,
  category?: LinkCategory,
) {
  return productsForEnvironmentAndCategory(config, environment, category)[0];
}

export function getInitialApplicationLinkValues(
  config: ApplicationLinkConfig,
): ApplicationLinkFormValues {
  const environment = config.environments[0];
  const category = firstCategoryForEnvironment(config, environment);
  const product = firstProductForEnvironmentAndCategory(config, environment, category);
  return {
    environment,
    product: product?.name,
    category,
    cooperationProject: config.cooperationProjects[0],
    loanType: config.loanTypes[0],
    restoreStatus: restoreStatusValues[0],
  };
}

export function buildApplicationLinkFormModel(
  config: ApplicationLinkConfig,
  values: ApplicationLinkFormValues,
): ApplicationLinkFormModel {
  const environment = values.environment;
  const category = values.category;
  const products = productsForEnvironmentAndCategory(config, environment, category);
  const product = findProduct(config, values.product);
  const categories = categoriesForEnvironment(config, environment);

  return {
    environment,
    product,
    category,
    dynamic: isDynamicApplicationLink(category),
    showRestoreStatus: Boolean(product?.extraFields?.includes('restoreStatus')),
    showSpcode: Boolean(product?.extraFields?.includes('spcode')),
    environmentOptions: toOptions(config.environments),
    productOptions: toOptions(products.map((item) => item.name)),
    categoryOptions: toOptions(categories),
    cooperationProjectOptions: toOptions(config.cooperationProjects),
    loanTypeOptions: toOptions(config.loanTypes),
    restoreStatusOptions: toOptions(restoreStatusValues),
  };
}

export function getApplicationLinkCascadeUpdates(
  config: ApplicationLinkConfig,
  changedValues: Partial<ApplicationLinkFormValues>,
  allValues: ApplicationLinkFormValues,
): Partial<ApplicationLinkFormValues> {
  if (Object.prototype.hasOwnProperty.call(changedValues, 'environment')) {
    const environment = String(allValues.environment ?? '');
    const category = firstCategoryForEnvironment(config, environment);
    const product = firstProductForEnvironmentAndCategory(config, environment, category);
    return {
      category,
      product: product?.name,
      requestJson: undefined,
    };
  }

  if (Object.prototype.hasOwnProperty.call(changedValues, 'category')) {
    const product = firstProductForEnvironmentAndCategory(
      config,
      allValues.environment,
      allValues.category,
    );
    return {
      product: product?.name,
      requestJson: undefined,
      restoreStatus: restoreStatusValues[0],
    };
  }

  if (Object.prototype.hasOwnProperty.call(changedValues, 'product')) {
    return { restoreStatus: restoreStatusValues[0] };
  }

  return {};
}
