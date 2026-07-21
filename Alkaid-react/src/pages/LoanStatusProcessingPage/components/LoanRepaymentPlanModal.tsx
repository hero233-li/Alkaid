import { Descriptions, Modal, Table, Tag } from 'antd';
import type { LoanRepaymentPlanItem, LoanResultRecord, LoanVoucher } from '../types';

const money = (value: number) => `¥${Number(value).toFixed(2)}`;
const statusTag = (value: string) => (
  <Tag color={value === '逾期' ? 'error' : value === '已结清' ? 'default' : 'processing'}>
    {value}
  </Tag>
);

export default function LoanRepaymentPlanModal({
  record,
  voucher,
  onClose,
}: {
  record: LoanResultRecord | null;
  voucher: LoanVoucher | null;
  onClose: () => void;
}) {
  return (
    <Modal
      title="还款计划"
      open={Boolean(record && voucher)}
      width={900}
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      {record && voucher && (
        <>
          <Descriptions title="当前状态" bordered column={2} size="small">
            <Descriptions.Item label="合同号">{record.contractNo}</Descriptions.Item>
            <Descriptions.Item label="借款凭证号">{voucher.voucherNo}</Descriptions.Item>
            <Descriptions.Item label="凭证状态">{statusTag(voucher.status)}</Descriptions.Item>
            <Descriptions.Item label="下一期还款日">{voucher.nextRepaymentDate}</Descriptions.Item>
          </Descriptions>
          <Descriptions title="还款详情" bordered column={2} size="small" style={{ marginTop: 20 }}>
            <Descriptions.Item label="已还本金">{money(voucher.repaidPrincipal)}</Descriptions.Item>
            <Descriptions.Item label="已还利息">{money(voucher.repaidInterest)}</Descriptions.Item>
            <Descriptions.Item label="未还本金">
              {money(voucher.outstandingPrincipal)}
            </Descriptions.Item>
            <Descriptions.Item label="未还利息">
              {money(voucher.outstandingInterest)}
            </Descriptions.Item>
          </Descriptions>
          <Table<LoanRepaymentPlanItem>
            title={() => '还款计划'}
            rowKey="installmentNo"
            size="small"
            pagination={false}
            style={{ marginTop: 20 }}
            dataSource={voucher.repaymentPlan}
            columns={[
              { title: '期次', dataIndex: 'installmentNo', width: 80 },
              { title: '还款日', dataIndex: 'repaymentDate' },
              { title: '应还本金', dataIndex: 'principal', render: money },
              { title: '应还利息', dataIndex: 'interest', render: money },
              { title: '应还合计', dataIndex: 'totalAmount', render: money },
              { title: '状态', dataIndex: 'status', render: statusTag },
            ]}
          />
        </>
      )}
    </Modal>
  );
}
