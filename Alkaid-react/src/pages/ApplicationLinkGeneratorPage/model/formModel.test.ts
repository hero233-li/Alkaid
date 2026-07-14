import { describe, expect, it } from 'vitest';

import { buildApplicationLinkFormModel, getInitialApplicationLinkValues } from './formModel';
import { buildApplicationLinkSubmission } from './submission';
import type { ApplicationLinkConfig } from './types';

const config: ApplicationLinkConfig = {
  environments: [{ label: '内网环境', value: 'env-internal' }],
  products: [{
    label: '产品 B',
    value: 'product-b',
    routes: [{ environment: 'env-internal', category: '太阳码', requiredFields: ['spcode'] }],
  }],
  cooperationProjects: ['合作项目一'],
  loanTypes: ['首贷'],
};

describe('application link form model', () => {
  it('keeps backend product and environment codes through cascade and submission', () => {
    const values = { ...getInitialApplicationLinkValues(config), spcode: 'SP001' };
    const model = buildApplicationLinkFormModel(config, values);
    const submission = buildApplicationLinkSubmission(config, values);

    expect(model.productOptions).toEqual([{ label: '产品 B', value: 'product-b' }]);
    expect(model.showSpcode).toBe(true);
    expect(submission).toMatchObject({
      environment: 'env-internal',
      product: 'product-b',
      category: '太阳码',
      spcode: 'SP001',
    });
  });
});
