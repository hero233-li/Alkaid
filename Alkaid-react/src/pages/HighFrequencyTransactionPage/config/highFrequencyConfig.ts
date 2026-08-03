export const highFrequencyConfig = {
  environments: ['UAT1', 'UAT2', 'UATC'],
  functionCodes: [
    { value: 'risk050009', label: 'risk050009 - 高频交易' },
    { value: 'risk050010', label: 'risk050010 - 账户频繁变更' },
    { value: 'risk050011', label: 'risk050011 - 夜间集中交易' },
    { value: 'risk050012', label: 'risk050012 - 跨区域异常交易' },
    { value: 'risk050013', label: 'risk050013 - 大额交易监测' },
  ],
};
