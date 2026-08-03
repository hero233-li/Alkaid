import { Button, Descriptions, Modal, Space, Tag } from 'antd';
import type { LoanAction, LoanResultRecord, LoanVoucher } from '../types';

const money = (value: number) => `¥${Number(value).toFixed(2)}`;
const voucherActions: { value: LoanAction; label: string }[] = [
  { value: 'repayment', label: '还款' },
  { value: 'overdue-repayment', label: '逾期还款' },
  { value: 'maturity-repayment', label: '到期还款' },
];

export default function LoanVoucherModal({
  record,
  voucher,
  open,
  busy,
  onClose,
  onAction,
}: {
  record: LoanResultRecord | null;
  voucher: LoanVoucher | null;
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onAction: (action: LoanAction) => void;
}) {
  const disabled = (action: LoanAction) =>
    busy ||
    !record ||
    !voucher ||
    voucher.status === '已结清' ||
    (action === 'maturity-repayment' && voucher.nextRepaymentDate !== record.accountingDate) ||
    (action === 'overdue-repayment' && voucher.status !== '逾期');
  return (
    <Modal
      title="借款凭证操作"
      open={open && Boolean(record && voucher)}
      width={680}
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      {record && voucher && (
        <>
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="合同号" span={2}>
              {record.contractNo}
            </Descriptions.Item>
            <Descriptions.Item label="借款凭证号" span={2}>
              {voucher.voucherNo}
            </Descriptions.Item>
            <Descriptions.Item label="凭证状态">
              <Tag
                color={
                  voucher.status === '逾期'
                    ? 'error'
                    : voucher.status === '已结清'
                      ? 'default'
                      : 'success'
                }
              >
                {voucher.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="下一期还款日">{voucher.nextRepaymentDate}</Descriptions.Item>
            <Descriptions.Item label="当前会计日">{record.accountingDate}</Descriptions.Item>
            <Descriptions.Item label="提款金额">{money(voucher.drawAmount)}</Descriptions.Item>
            <Descriptions.Item label="未还金额">
              {money(voucher.outstandingAmount)}
            </Descriptions.Item>
            <Descriptions.Item label="逾期金额" span={2}>
              {money(voucher.overdueAmount)}
            </Descriptions.Item>
          </Descriptions>
          <div className="loan-status-voucher-actions">
            <Space wrap>
              {voucherActions.map((item) => (
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
        </>
      )}
    </Modal>
  );
}
