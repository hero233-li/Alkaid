import { Button, Card, Descriptions, Drawer, Empty, Space, Table, Tag } from 'antd';
import { loanStatusConfig } from '../config/loanStatusConfig';
import type { LoanAction, LoanResultRecord, LoanVoucher } from '../types';

const money = (value: number) => `¥${Number(value).toFixed(2)}`;
const contractActions = new Set<LoanAction>(['contract-sign', 'loan-draw', 'freeze', 'unfreeze']);

export default function LoanDetailDrawer({
  record,
  busy,
  onClose,
  onAction,
  onVoucherOpen,
  onPlanOpen,
}: {
  record: LoanResultRecord | null;
  busy: boolean;
  onClose: () => void;
  onAction: (action: LoanAction) => void;
  onVoucherOpen: (voucher: LoanVoucher) => void;
  onPlanOpen: (voucher: LoanVoucher) => void;
}) {
  const disabled = (action: LoanAction) =>
    busy ||
    !record ||
    (action === 'contract-sign'
      ? record.loanStatus !== '未签署'
      : record.loanStatus !== '已生效') ||
    (action === 'freeze' && record.freezeStatus === '是') ||
    (action === 'unfreeze' && record.freezeStatus !== '是');
  const actions = loanStatusConfig.actions.filter((item) => contractActions.has(item.value));
  return (
    <Drawer
      title="贷款详情与操作"
      open={Boolean(record)}
      width={820}
      onClose={onClose}
      destroyOnClose
    >
      {record && (
        <div className="loan-status-drawer-sections">
          <Card title="合同信息" size="small">
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="环境">{record.environment}</Descriptions.Item>
              <Descriptions.Item label="客户号">{record.customerNo}</Descriptions.Item>
              <Descriptions.Item label="客户名称">{record.customerName}</Descriptions.Item>
              <Descriptions.Item label="客户证件号">{record.certificateNo}</Descriptions.Item>
              <Descriptions.Item label="客户卡号">{record.cardNo}</Descriptions.Item>
              <Descriptions.Item label="客户手机号">{record.phone}</Descriptions.Item>
              <Descriptions.Item label="卡余额">{money(record.balance)}</Descriptions.Item>
              <Descriptions.Item label="合同号">
                {record.contractNo || '无关联合同信息'}
              </Descriptions.Item>
              <Descriptions.Item label="额度编号">{record.quotaNo}</Descriptions.Item>
              <Descriptions.Item label="签署日期">{record.signDate}</Descriptions.Item>
              <Descriptions.Item label="机构号">{record.organizationNo}</Descriptions.Item>
              <Descriptions.Item label="管护客户经理">
                {record.relationshipManager}
              </Descriptions.Item>
              <Descriptions.Item label="当前会计日">{record.accountingDate}</Descriptions.Item>
              <Descriptions.Item label="当前宽限日">{record.graceDays} 天</Descriptions.Item>
              <Descriptions.Item label="核心利率">{record.coreRate.toFixed(2)}%</Descriptions.Item>
              <Descriptions.Item label="当前通用会计日">
                {record.generalAccountingDate}
              </Descriptions.Item>
              <Descriptions.Item label="当前参数会计日" span={2}>
                {record.parameterAccountingDate}
              </Descriptions.Item>
              <Descriptions.Item label="贷款状态">
                <Tag
                  color={
                    record.loanStatus === '已生效'
                      ? 'success'
                      : record.loanStatus === '未签署'
                        ? 'warning'
                        : 'default'
                  }
                >
                  {record.loanStatus}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="冻结状态">
                <Tag
                  color={
                    record.freezeStatus === '是'
                      ? 'error'
                      : record.freezeStatus === '否'
                        ? 'success'
                        : 'default'
                  }
                >
                  {record.freezeStatus}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="逾期状态">
                <Tag
                  color={
                    record.overdueStatus === '是'
                      ? 'error'
                      : record.overdueStatus === '否'
                        ? 'success'
                        : 'default'
                  }
                >
                  {record.overdueStatus}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="授信额度">
                {record.loanStatus === '未签署' ? '-' : money(record.creditLimit)}
              </Descriptions.Item>
              <Descriptions.Item label="已用额度">
                {record.loanStatus === '未签署' ? '-' : money(record.usedCredit)}
              </Descriptions.Item>
              <Descriptions.Item label="可用额度">
                {record.loanStatus === '未签署' ? '-' : money(record.availableCredit)}
              </Descriptions.Item>
            </Descriptions>
            <div className="loan-status-contract-actions">
              <Space wrap>
                {actions.map((item) => (
                  <Button
                    key={item.value}
                    disabled={disabled(item.value)}
                    onClick={() => onAction(item.value)}
                  >
                    {item.label}
                  </Button>
                ))}
              </Space>
            </div>
          </Card>
          <Card title="凭证信息" size="small">
            {record.vouchers.length ? (
              <Table
                rowKey="voucherNo"
                size="small"
                pagination={false}
                dataSource={record.vouchers}
                columns={[
                  { title: '借款凭证号', dataIndex: 'voucherNo' },
                  { title: '下一期还款日', dataIndex: 'nextRepaymentDate', width: 130 },
                  {
                    title: '凭证状态',
                    dataIndex: 'status',
                    width: 100,
                    render: (value) => (
                      <Tag
                        color={
                          value === '逾期' ? 'error' : value === '已结清' ? 'default' : 'success'
                        }
                      >
                        {value}
                      </Tag>
                    ),
                  },
                  {
                    title: '操作',
                    width: 210,
                    render: (_, voucher) => (
                      <Space size={4}>
                        <Button type="link" disabled={busy} onClick={() => onVoucherOpen(voucher)}>
                          操作
                        </Button>
                        <Button type="link" disabled={busy} onClick={() => onPlanOpen(voucher)}>
                          查询还款计划
                        </Button>
                      </Space>
                    ),
                  },
                ]}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  record.loanStatus === '未签署' ? '合同签署并提用后生成借款凭证' : '暂无借款凭证'
                }
              />
            )}
          </Card>
        </div>
      )}
    </Drawer>
  );
}
