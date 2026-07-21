import { Col, Form, InputNumber, Row, Select } from 'antd';
import type { ApplicationDataConfig } from '../types';

export default function EnterpriseDataSection({ config }: { config: ApplicationDataConfig }) {
  return (
    <>
      <div className="application-data-section-title">企业数据生成</div>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="companyType" label="主体类型" rules={[{ required: true }]}>
            <Select options={config.companyTypes} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="count" label="生成数量" rules={[{ required: true }]}>
            <InputNumber min={1} max={config.maxCount} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>
    </>
  );
}
