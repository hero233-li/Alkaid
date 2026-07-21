import type {
  ApplicationLinkConfig,
  ApplicationLinkFormValues,
  ApplicationLinkOption,
  LinkCategory,
  ProductLinkConfig,
} from './types';

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

export function findProduct(config: ApplicationLinkConfig, productCode?: string) {
  return config.products.find((item) => item.value === productCode);
}

export function productsForEnvironment(config: ApplicationLinkConfig, environment?: string) {
  return environment
    ? config.products.filter((item) =>
        item.routes.some((route) => route.environment === environment),
      )
    : [];
}

export function categoriesForProduct(
  product: ProductLinkConfig | undefined,
  environment: string | undefined,
) {
  return environment && product
    ? product.routes
        .filter((route) => route.environment === environment)
        .map((route) => route.category)
    : [];
}

export function categoriesForEnvironment(config: ApplicationLinkConfig, environment?: string) {
  const supportedCategories = new Set(
    productsForEnvironment(config, environment).flatMap((product) =>
      categoriesForProduct(product, environment),
    ),
  );
  return categoryOrder.filter((category) => supportedCategories.has(category));
}

export function productsForEnvironmentAndCategory(
  config: ApplicationLinkConfig,
  environment: string | undefined,
  category?: LinkCategory,
) {
  return productsForEnvironment(config, environment).filter((product) =>
    category ? categoriesForProduct(product, environment).includes(category) : true,
  );
}

function firstCategoryForEnvironment(config: ApplicationLinkConfig, environment?: string) {
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
  const environment = config.environments[0]?.value;
  const category = firstCategoryForEnvironment(config, environment);
  const product = firstProductForEnvironmentAndCategory(config, environment, category);
  return {
    environment,
    product: product?.value,
    category,
    cooperationProjectId: config.cooperationProjects[0]?.value,
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
  const route = product?.routes.find(
    (item) => item.environment === environment && item.category === category,
  );

  return {
    environment,
    product,
    category,
    dynamic: isDynamicApplicationLink(category),
    showRestoreStatus: Boolean(route?.requiredFields.includes('restoreStatus')),
    showSpcode: Boolean(route?.requiredFields.includes('spcode')),
    environmentOptions: config.environments,
    productOptions: products.map(({ label, value }) => ({ label, value })),
    categoryOptions: toOptions(categories),
    cooperationProjectOptions: config.cooperationProjects,
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
      product: product?.value,
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
      product: product?.value,
      requestJson: undefined,
      restoreStatus: restoreStatusValues[0],
    };
  }

  if (Object.prototype.hasOwnProperty.call(changedValues, 'product')) {
    return { restoreStatus: restoreStatusValues[0] };
  }

  return {};
}
