import { Button, Card, Col, Form, Input, Row, Select, type FormInstance } from 'antd';
import { Search } from 'lucide-react';
import { loanStatusConfig } from '../config/loanStatusConfig';
import type { LoanSearchValues } from '../types';
export default function LoanSearchForm({
  form,
  busy,
  onSubmit,
}: {
  form: FormInstance<LoanSearchValues>;
  busy: boolean;
  onSubmit: (v: LoanSearchValues) => void;
}) {
  return (
    <Card title="贷款状态查询">
      <Form
        form={form}
        layout="vertical"
        disabled={busy}
        initialValues={{ environment: loanStatusConfig.environments[0] }}
        onFinish={onSubmit}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="environment" label="环境">
              <Select
                options={loanStatusConfig.environments.map((value) => ({ value, label: value }))}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="customerNo" label="客户号" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          </Col>
        </Row>
        <div className="loan-status-actions">
          <Button type="primary" htmlType="submit" icon={<Search size={16} />}>
            查询
          </Button>
        </div>
      </Form>
    </Card>
  );
}
