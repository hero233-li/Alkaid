import { describe, expect, it } from 'vitest';
import { adaptProductApplicationConfig, buildProductApplicationFields } from './configAdapter';
import { buildProductSubmission } from './submission';

const location = {
  label: '地区',
  value: 'location',
  branches: [
    {
      label: '机构',
      value: 'branch',
      outlets: [{ label: '网点', value: 'outlet' }],
    },
  ],
};

function config() {
  return adaptProductApplicationConfig({
    id: 'product-application-test',
    version: 8,
    environments: [{ label: 'UAT1', value: 'UAT1' }],
    products: [
      {
        label: '产品A',
        value: 'product-a',
        cooperationProjectId: 'PROJECT-001',
        environments: ['UAT1'],
        locations: [location],
        fieldSets: ['selection'],
        requiredFields: ['environment', 'product', 'location', 'branch', 'outlet'],
      },
      {
        label: '产品B',
        value: 'product-b',
        cooperationProjectId: 'PROJECT-002',
        environments: ['UAT1'],
        locations: [location],
        fieldSets: ['selection'],
        requiredFields: ['environment', 'product', 'location', 'branch', 'outlet'],
      },
    ],
    fields: ['environment', 'product', 'location', 'branch', 'outlet'].map((name) => ({
      name,
      label: name,
      control: 'select',
    })),
    fieldSets: {
      selection: ['environment', 'product', 'location', 'branch', 'outlet'],
    },
    cascadeResetMap: {},
  });
}

describe('buildProductSubmission', () => {
  it('submits the selected product cooperation project without rendering a field', () => {
    const adapted = config();
    const values = {
      environment: 'UAT1',
      product: 'product-b',
      location: 'location',
      branch: 'branch',
      outlet: 'outlet',
    };

    expect(
      buildProductApplicationFields(adapted, values).some(
        (field) => field.name === 'cooperationProjectId',
      ),
    ).toBe(false);
    expect(buildProductSubmission(adapted, values).payload.cooperationProjectId).toBe(
      'PROJECT-002',
    );
  });
});
