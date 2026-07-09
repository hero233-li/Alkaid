import type { ApplicationLinkConfig } from '../model/types';

export const applicationLinkConfig: ApplicationLinkConfig = {
  environments: ['环境1', '环境2', '环境3'],
  cooperationProjects: ['合作项目一', '合作项目二', '合作项目三'],
  loanTypes: ['首贷', '续贷'],
  products: [
    {
      name: '产品A',
      environments: ['环境1', '环境2', '环境3'],
      categoriesByEnvironment: {
        环境1: ['动态链接'],
        环境2: ['动态链接'],
        环境3: ['太阳码'],
      },
    },
    {
      name: '产品B',
      environments: ['环境1', '环境2', '环境3'],
      categoriesByEnvironment: {
        环境1: ['太阳码'],
        环境2: ['太阳码'],
        环境3: ['太阳码'],
      },
    },
    {
      name: '产品C',
      environments: ['环境1', '环境2', '环境3'],
      categoriesByEnvironment: {
        环境1: ['动态链接'],
        环境2: ['动态链接'],
        环境3: ['动态链接'],
      },
      extraFields: ['restoreStatus', 'spcode'],
    },
  ],
};
