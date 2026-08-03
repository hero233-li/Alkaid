import { useEffect } from 'react';
import { Alert, Button, Col, Form, Input, InputNumber, Modal, Row, Select, Switch } from 'antd';
import { loanActionLabel, loanStatusConfig } from '../config/loanStatusConfig';
import type {
  LoanAction,
  LoanActionValues,
  LoanInterruptedFlow,
  LoanResultRecord,
  LoanVoucher,
} from '../types';
export default function LoanActionModal({
  card,
  voucher,
  action,
  interrupted,
  onClose,
  onSubmit,
  onResume,
}: {
  card: LoanResultRecord | null;
  voucher: LoanVoucher | null;
  action: LoanAction | null;
  interrupted: LoanInterruptedFlow | null;
  onClose: () => void;
  onSubmit: (v: LoanActionValues) => void;
  onResume: () => void;
}) {
  const [form] = Form.useForm<LoanActionValues>();
  useEffect(() => {
    if (!card || !action) return;
    form.resetFields();
    form.setFieldsValue({
      environment: card.environment,
      customerNo: card.customerNo,
      certificateNo: card.certificateNo,
      cardNo: card.cardNo,
      tellerNo: loanStatusConfig.defaultTellerNo,
      quotaNo: card.quotaNo,
      amount:
        action === 'overdue-repayment'
          ? (voucher?.overdueAmount ?? card.overdueDebt)
          : Math.min(voucher?.outstandingAmount ?? 1000, 1000),
      contractNo: card.contractNo,
      voucherNo: voucher?.voucherNo,
      simulateFailure: false,
      drawTerm: 12,
    });
  }, [card, voucher, action, form]);
  if (!card || !action) return null;
  const status = action === 'freeze' || action === 'unfreeze';
  const repayment = ['repayment', 'overdue-repayment', 'maturity-repayment'].includes(action);
  const noContract = !card.contractNo;
  const title =
    action === 'contract-sign' ? `合同签署（合同号：${card.contractNo}）` : loanActionLabel(action);
  return (
    <Modal title={title} open footer={null} width={720} onCancel={onClose} destroyOnClose>
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="environment" label="环境">
              <Input readOnly />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="customerNo" label="客户号">
              <Input readOnly />
            </Form.Item>
          </Col>
          {!status && (
            <Col span={12}>
              <Form.Item name="cardNo" label="卡号">
                <Input readOnly />
              </Form.Item>
            </Col>
          )}
          {action === 'contract-sign' && (
            <>
              <Col span={12}>
                <Form.Item label="姓名">
                  <Input value={card.customerName} readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="certificateNo" label="证件号">
                  <Input readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="手机号">
                  <Input value={card.phone} readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="contractNo" label="合同号">
                  <Input readOnly />
                </Form.Item>
              </Col>
            </>
          )}
          {action === 'loan-draw' && (
            <>
              <Col span={12}>
                <Form.Item name="counterparty" label="交易对手">
                  <Select
                    options={loanStatusConfig.counterparties.map((value) => ({
                      value,
                      label: value,
                    }))}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="bankName" label="开户行">
                  <Select
                    options={loanStatusConfig.banks.map((value) => ({ value, label: value }))}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="counterpartyType" label="交易对手类型">
                  <Select
                    options={loanStatusConfig.counterpartyTypes.map((value) => ({
                      value,
                      label: value,
                    }))}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="counterpartyAccount"
                  label="交易对手账号"
                  rules={[{ required: true }]}
                >
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="counterpartyName"
                  label="交易对手户名"
                  rules={[{ required: true }]}
                >
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="contractNo" label="合同号">
                  <Input readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="drawTerm" label="提款期限（月）">
                  <InputNumber min={1} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="amount"
                  label={`提款金额（可用额度 ¥${Number(card.availableCredit).toFixed(2)}）`}
                  rules={[{ required: true }]}
                >
                  <InputNumber
                    min={0.01}
                    max={card.availableCredit}
                    precision={2}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
              </Col>
            </>
          )}
          {repayment && (
            <>
              <Col span={12}>
                <Form.Item label="卡余额">
                  <Input value={card.balance} readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="contractNo" label="关联合同号">
                  <Input readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="voucherNo" label="借款凭证号">
                  <Input readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="凭证未还金额">
                  <Input value={voucher?.outstandingAmount ?? card.debt} readOnly />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="amount" label={`${loanActionLabel(action)}金额`}>
                  <InputNumber
                    disabled={action === 'overdue-repayment'}
                    min={0.01}
                    max={voucher?.outstandingAmount}
                    precision={2}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
              </Col>
            </>
          )}
          {status && (
            <>
              <Col span={12}>
                <Form.Item name="tellerNo" label="柜员号">
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="quotaNo" label="额度编号">
                  <Input readOnly />
                </Form.Item>
              </Col>
              <Col span={24}>
                <Form.Item name="simulateFailure" label="模拟流程中断" valuePropName="checked">
                  <Switch />
                </Form.Item>
              </Col>
            </>
          )}
        </Row>
        {noContract &&
          [
            'contract-sign',
            'loan-draw',
            'repayment',
            'overdue-repayment',
            'maturity-repayment',
          ].includes(action) && (
            <Alert type="warning" showIcon message="无关联合同信息" style={{ marginBottom: 16 }} />
          )}
        {interrupted && (
          <Alert
            type="warning"
            showIcon
            message={`流程当前岗位：${interrupted.currentStep ?? '未知岗位'}`}
            description={`Job #${interrupted.jobId} 可继续处理`}
            style={{ marginBottom: 16 }}
          />
        )}
        <div className="loan-status-actions">
          {interrupted ? (
            <Button type="primary" onClick={onResume}>
              继续处理
            </Button>
          ) : (
            <Button
              type="primary"
              htmlType="submit"
              disabled={
                noContract &&
                [
                  'contract-sign',
                  'loan-draw',
                  'repayment',
                  'overdue-repayment',
                  'maturity-repayment',
                ].includes(action)
              }
            >
              {status ? '发起' : loanActionLabel(action)}
            </Button>
          )}
        </div>
      </Form>
    </Modal>
  );
}
