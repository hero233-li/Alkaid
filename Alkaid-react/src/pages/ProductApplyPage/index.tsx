import { Alert, Button, Card, Spin, message } from 'antd';
import DynamicSearchForm from './components/DynamicSearchForm';
import JobDetailOverlay from './components/JobDetailOverlay';
import JobResultList from './components/JobResultList';
import ProductApplicationWorkflowModal from './components/ProductApplicationWorkflowModal';
import { useProductApplicationForm } from './hooks/useProductApplicationForm';
import { useProductApplyJobs } from './hooks/useProductApplyJobs';
import { useProductConfig } from './hooks/useProductConfig';
import type { ProductApplicationFormValues, ProductApplyPageProps } from './model/types';

export default function ProductApplyPage({ pageInstanceKey }: ProductApplyPageProps) {
  const configQuery = useProductConfig();
  const applicationForm = useProductApplicationForm(configQuery.config, pageInstanceKey);
  const jobs = useProductApplyJobs(pageInstanceKey);

  const submit = (values: ProductApplicationFormValues) => {
    try {
      void jobs.submit(applicationForm.createSubmission(values));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '产品申请配置尚未加载');
    }
  };

  if (!configQuery.config) {
    return (
      <div className="page-surface product-application-page">
        <Card>
          {configQuery.error ? (
            <Alert
              type="error"
              showIcon
              message="产品申请配置加载失败"
              description={configQuery.error}
              action={
                <Button size="small" onClick={configQuery.retry}>
                  重新加载
                </Button>
              }
            />
          ) : (
            <div className="product-config-loading">
              <Spin spinning={configQuery.loading} tip="正在加载产品配置...">
                <span aria-hidden="true" />
              </Spin>
            </div>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="page-surface product-application-page">
      <div className="product-application-stack">
        <DynamicSearchForm
          form={applicationForm.form}
          fields={applicationForm.fields}
          submitting={jobs.submitting}
          onValuesChange={applicationForm.handleValuesChange}
          onSubmit={submit}
          onReset={applicationForm.reset}
        />
        <JobResultList
          results={jobs.results}
          onDetail={jobs.selectResult}
          onRetry={(result) => void jobs.retry(result)}
          onCancel={(result) => void jobs.cancel(result)}
        />
      </div>
      <JobDetailOverlay
        result={jobs.selectedResult}
        onClose={jobs.closeDetail}
        presentation="drawer"
      />
      <ProductApplicationWorkflowModal active={jobs.submitting} />
    </div>
  );
}
