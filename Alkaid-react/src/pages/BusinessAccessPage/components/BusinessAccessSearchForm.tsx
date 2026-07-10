import { Button, Card, Col, Form, Input, Row, Select, Space, type FormInstance } from 'antd';
import { RotateCcw, Search } from 'lucide-react';
import {
  getBusinessAccessEnvironmentOptions,
  validateBusinessAccessSearchCriteria,
} from '../model/searchModel';
import type { BusinessAccessSearchValues } from '../types';

interface BusinessAccessSearchFormProps {
  form: FormInstance<BusinessAccessSearchValues>;
  initialValues: BusinessAccessSearchValues;
  busy: boolean;
  searching: boolean;
  onSearch: (values: BusinessAccessSearchValues) => void;
  onReset: () => void;
}

export default function BusinessAccessSearchForm({
  form,
  initialValues,
  busy,
  searching,
  onSearch,
  onReset,
}: BusinessAccessSearchFormProps) {
  const environmentOptions = getBusinessAccessEnvironmentOptions();
  const validateSearchCriteria = ({ getFieldValue }: { getFieldValue: (name: string) => unknown }) => ({
    validator: () => {
      try {
        validateBusinessAccessSearchCriteria({
          name: String(getFieldValue('name') ?? ''),
          certificateNo: String(getFieldValue('certificateNo') ?? ''),
        });
        return Promise.resolve();
      } catch (error) {
        return Promise.reject(error);
      }
    },
  });

  return (
    <Card title="查询条件">
      <Form<BusinessAccessSearchValues>
        form={form}
        layout="vertical"
        disabled={busy}
        initialValues={initialValues}
        onFinish={onSearch}
      >
        <div className="business-access-search-form">
          <Row gutter={[16, 4]} justify="center">
            <Col xs={24} md={8}>
              <Form.Item
                name="environment"
                label="环境"
                rules={[{ required: true, message: '请选择环境' }]}
              >
                <Select options={environmentOptions} placeholder="请选择环境" allowClear={false} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="name"
                label="姓名"
                dependencies={['certificateNo']}
                rules={[validateSearchCriteria]}
              >
                <Input placeholder="请输入姓名" allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="certificateNo"
                label="身份证号"
                dependencies={['name']}
                rules={[validateSearchCriteria]}
              >
                <Input placeholder="请输入身份证号" maxLength={18} allowClear />
              </Form.Item>
            </Col>
          </Row>
        </div>
        <div className="common-form-actions">
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<Search size={16} />}
              loading={searching}
              disabled={busy}
            >
              查询
            </Button>
            <Button
              disabled={busy}
              icon={<RotateCcw size={16} />}
              onClick={onReset}
            >
              重置
            </Button>
          </Space>
        </div>
      </Form>
    </Card>
  );
}
