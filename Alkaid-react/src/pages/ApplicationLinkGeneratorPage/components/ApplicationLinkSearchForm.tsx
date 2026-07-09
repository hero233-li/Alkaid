import { Button, Card, Col, Form, Input, Row, Select, type FormInstance } from 'antd';
import { Link2 } from 'lucide-react';
import { applicationLinkConfig } from '../config/applicationLinkConfig';
import type { ApplicationLinkFormValues } from '../types';

const options = (items: string[] = []) => items.map((value) => ({ value, label: value }));

export default function ApplicationLinkSearchForm({
  form,
  busy,
  onSubmit,
}: {
  form: FormInstance<ApplicationLinkFormValues>;
  busy: boolean;
  onSubmit: (values: ApplicationLinkFormValues) => void;
}) {
  const defaultEnvironment = applicationLinkConfig.environments[0];
  const defaultProduct = applicationLinkConfig.products.find((item) => item.environments.includes(defaultEnvironment));
  const defaultCategory = defaultProduct?.categoriesByEnvironment[defaultEnvironment]?.[0];
  const environment = Form.useWatch('environment', form);
  const productName = Form.useWatch('product', form);
  const category = Form.useWatch('category', form);
  const products = environment
    ? applicationLinkConfig.products.filter((item) => item.environments.includes(environment))
    : [];
  const product = applicationLinkConfig.products.find((item) => item.name === productName);
  const categories = environment && product ? product.categoriesByEnvironment[environment] ?? [] : [];
  const dynamic = category === '动态链接';

  return (
    <Card title="申请链接配置">
      <Form
        form={form}
        layout="vertical"
        disabled={busy}
        onFinish={onSubmit}
        initialValues={{
          environment: defaultEnvironment,
          product: defaultProduct?.name,
          category: defaultCategory,
          cooperationProject: applicationLinkConfig.cooperationProjects[0],
          recommender: applicationLinkConfig.recommenders[0],
          recommenderPhone: applicationLinkConfig.recommenderPhones[0],
          loanType: applicationLinkConfig.loanTypes[0],
          restoreStatus: '正常',
        }}
        onValuesChange={(changed) => {
          if ('environment' in changed) {
            const nextEnvironment = String(changed.environment ?? '');
            const nextProduct = applicationLinkConfig.products.find((item) => item.environments.includes(nextEnvironment));
            form.setFieldsValue({
              product: nextProduct?.name,
              category: nextProduct?.categoriesByEnvironment[nextEnvironment]?.[0],
            });
          }
          if ('product' in changed) {
            const nextProduct = applicationLinkConfig.products.find((item) => item.name === changed.product);
            form.setFieldsValue({
              category: environment && nextProduct
                ? nextProduct.categoriesByEnvironment[environment]?.[0]
                : undefined,
              restoreStatus: '正常',
            });
          }
        }}
      >
        <Row gutter={16}>
          <Col span={8}><Form.Item name="environment" label="环境" rules={[{ required: true }]}><Select options={options(applicationLinkConfig.environments)} /></Form.Item></Col>
          <Col span={8}><Form.Item name="product" label="产品" rules={[{ required: true }]}><Select disabled={!environment} options={options(products.map((item) => item.name))} /></Form.Item></Col>
          <Col span={8}><Form.Item name="category" label="类别" rules={[{ required: true }]}><Select disabled={!productName} options={options(categories)} /></Form.Item></Col>
          <Col span={8}><Form.Item name="cooperationProject" label="合作项目" rules={[{ required: true }]}><Select options={options(applicationLinkConfig.cooperationProjects)} /></Form.Item></Col>
          {dynamic && <>
            <Col span={8}><Form.Item name="customerName" label="客户名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="customerPhone" label="客户手机" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="customerCertificateNo" label="客户证件号" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="customerCompanyName" label="客户企业名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="customerCompanyCode" label="客户企业代码" rules={[{ required: true }]}><Input /></Form.Item></Col>
          </>}
          <Col span={8}><Form.Item name="recommender" label="推荐人" rules={[{ required: true }]}><Select options={options(applicationLinkConfig.recommenders)} /></Form.Item></Col>
          <Col span={8}><Form.Item name="recommenderPhone" label="推荐人手机号码" rules={[{ required: true }]}><Select options={options(applicationLinkConfig.recommenderPhones)} /></Form.Item></Col>
          <Col span={8}><Form.Item name="loanType" label="首贷续贷" rules={[{ required: true }]}><Select options={options(applicationLinkConfig.loanTypes)} /></Form.Item></Col>
          {product?.extraFields?.includes('restoreStatus') && <Col span={8}><Form.Item name="restoreStatus" label="还原状况" rules={[{ required: true }]}><Select options={options(['正常', '已还原', '待还原'])} /></Form.Item></Col>}
          {product?.extraFields?.includes('spcode') && <Col span={8}><Form.Item name="spcode" label="企业代码 spcode" rules={[{ required: true }]}><Input /></Form.Item></Col>}
        </Row>
        <div className="application-link-actions"><Button type="primary" htmlType="submit" icon={<Link2 size={16} />}>生成申请链接</Button></div>
      </Form>
    </Card>
  );
}
