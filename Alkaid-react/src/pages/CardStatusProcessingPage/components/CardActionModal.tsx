import { useEffect } from 'react';
import { Button, Col, Form, Input, InputNumber, Modal, Row } from 'antd';
import { cardActionLabel, cardStatusConfig } from '../config/cardStatusConfig';
import type { CardAction, CardActionValues, CardRecord } from '../types';

export default function CardActionModal({
  card,
  action,
  onClose,
  onSubmit,
}: {
  card: CardRecord | null;
  action: CardAction | null;
  onClose: () => void;
  onSubmit: (values: CardActionValues) => void;
}) {
  const [form] = Form.useForm<CardActionValues>();

  useEffect(() => {
    if (!card || !action) return;
    form.resetFields();
    form.setFieldsValue({
      environment: card.environment,
      customerNo: card.customerNo,
      certificateNo: card.certificateNo,
      cardNo: card.cardNo,
      tellerNo: cardStatusConfig.defaultTellerNo,
      amount: 1000,
      targetCard: undefined,
    });
  }, [action, card, form]);

  if (!card || !action) return null;
  const money = ['deposit', 'withdraw', 'transfer'].includes(action);

  return (
    <Modal title={cardActionLabel(action)} open footer={null} onCancel={onClose} destroyOnClose>
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
          <Col span={12}>
            <Form.Item name="cardNo" label="卡号">
              <Input readOnly />
            </Form.Item>
          </Col>
          {action === 'card-pin-reset' && (
            <Col span={12}>
              <Form.Item name="certificateNo" label="证件号">
                <Input readOnly />
              </Form.Item>
            </Col>
          )}
          {money && (
            <Col span={12}>
              <Form.Item
                name="amount"
                label={`${cardActionLabel(action)}金额`}
                rules={[{ required: true }]}
              >
                <InputNumber min={0.01} precision={2} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          )}
          {money && (
            <Col span={12}>
              <Form.Item
                name="tellerNo"
                label={`${cardActionLabel(action)}柜员`}
                rules={[{ required: true }]}
              >
                <Input />
              </Form.Item>
            </Col>
          )}
          {action === 'transfer' && (
            <Col span={12}>
              <Form.Item name="targetCard" label="转账卡" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
          )}
        </Row>
        <div className="card-status-actions">
          <Button type="primary" htmlType="submit">
            确认{cardActionLabel(action)}
          </Button>
        </div>
      </Form>
    </Modal>
  );
}
