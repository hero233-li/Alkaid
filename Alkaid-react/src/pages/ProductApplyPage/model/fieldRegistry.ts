import type { ProductFieldConfig } from './types';

type FieldPresentation = Pick<
  ProductFieldConfig,
  | 'label'
  | 'control'
  | 'span'
  | 'searchable'
  | 'placeholder'
  | 'checkedLabel'
  | 'uncheckedLabel'
  | 'switchWidth'
  | 'persistDraft'
>;

export const productFieldRegistry: Record<string, FieldPresentation> = {
  environment: { label: '环境', control: 'select', span: 5, searchable: true, persistDraft: true },
  product: { label: '产品', control: 'select', span: 5, searchable: true, persistDraft: true },
  location: { label: '地区', control: 'select', span: 5, searchable: true, persistDraft: true },
  branch: { label: '机构', control: 'select', span: 5, searchable: true, persistDraft: true },
  outlet: { label: '网点', control: 'select', span: 4, searchable: true, persistDraft: true },
  personName: {
    label: '客户姓名',
    control: 'input',
    span: 4,
    placeholder: '请输入客户姓名',
    persistDraft: false,
  },
  certificateNo: {
    label: '证件号码',
    control: 'input',
    span: 4,
    placeholder: '请输入证件号码',
    persistDraft: false,
  },
  phone: {
    label: '手机号码',
    control: 'input',
    span: 4,
    placeholder: '请输入手机号码',
    persistDraft: false,
  },
  cardNo: {
    label: '卡号',
    control: 'input',
    span: 4,
    placeholder: '请输入卡号',
    persistDraft: false,
  },
  companyName: {
    label: '企业名称',
    control: 'input',
    span: 4,
    placeholder: '请输入企业名称',
    persistDraft: false,
  },
  creditCode: { label: '统一社会信用代码', control: 'input', span: 4, persistDraft: false },
  legalPerson: {
    label: '客户类型',
    control: 'switch',
    span: 3,
    checkedLabel: '法人',
    uncheckedLabel: '股东',
    switchWidth: 64,
    persistDraft: true,
  },
  whitelistEnabled: {
    label: '白名单',
    control: 'switch',
    span: 3,
    checkedLabel: '开启',
    uncheckedLabel: '关闭',
    switchWidth: 64,
    persistDraft: true,
  },
  redShieldEnabled: {
    label: '红盾',
    control: 'switch',
    span: 3,
    checkedLabel: '开启',
    uncheckedLabel: '关闭',
    switchWidth: 64,
    persistDraft: true,
  },
  creditEnabled: {
    label: '征信',
    control: 'switch',
    span: 3,
    checkedLabel: '开启',
    uncheckedLabel: '关闭',
    switchWidth: 64,
    persistDraft: true,
  },
};
