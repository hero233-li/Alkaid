import { Alert, message } from 'antd';
import BusinessAccessResultList from './components/BusinessAccessResultList';
import BusinessAccessSearchForm from './components/BusinessAccessSearchForm';
import BusinessAccessWorkflowModal from './components/BusinessAccessWorkflowModal';
import NotificationPushOverlay from './components/NotificationPushOverlay';
import { useBusinessAccess } from './hooks/useBusinessAccess';
import { useBusinessAccessForm } from './hooks/useBusinessAccessForm';
import type { BusinessAccessSearchValues } from './types';

export default function BusinessAccessPage() {
  const businessAccessForm = useBusinessAccessForm();
  const businessAccess = useBusinessAccess();

  const submit = (values: BusinessAccessSearchValues) => {
    try {
      void businessAccess.search(businessAccessForm.createSubmission(values));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '查询条件不完整');
    }
  };

  return (
    <div className="page-surface business-access-page">
      <div className="business-access-stack">
        {businessAccessForm.configError && (
          <Alert
            type="error"
            showIcon
            message="业务准入配置加载失败"
            description={businessAccessForm.configError}
          />
        )}
        <BusinessAccessSearchForm
          form={businessAccessForm.form}
          initialValues={businessAccessForm.initialValues}
          busy={businessAccess.busy}
          searching={businessAccess.activity?.operation === 'search'}
          configLoading={businessAccessForm.configLoading}
          environmentOptions={businessAccessForm.environmentOptions}
          onSearch={submit}
          onReset={businessAccessForm.reset}
        />
        <BusinessAccessResultList
          results={businessAccess.results}
          invalidatingId={businessAccess.invalidatingId}
          busy={businessAccess.busy}
          searching={businessAccess.activity?.operation === 'search'}
          onInvalidate={(record) => void businessAccess.invalidate(record)}
          onNotification={(record) => void businessAccess.openNotifications(record)}
        />
      </div>
      <NotificationPushOverlay
        record={businessAccess.selectedRecord}
        notifications={businessAccess.notifications}
        loading={businessAccess.activity?.operation === 'notifications'}
        busy={businessAccess.busy}
        pushingKey={businessAccess.pushingKey}
        onClose={businessAccess.closeNotifications}
        onPush={(notification, versionType) =>
          void businessAccess.pushNotification(notification, versionType)
        }
      />
      <BusinessAccessWorkflowModal activity={businessAccess.activity} />
    </div>
  );
}
