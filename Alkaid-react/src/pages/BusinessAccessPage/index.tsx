import { Form } from 'antd';
import type { BusinessAccessSearchValues } from '../../api/businessAccess';
import BusinessAccessResultList from './components/BusinessAccessResultList';
import BusinessAccessSearchForm from './components/BusinessAccessSearchForm';
import BusinessAccessWorkflowModal from './components/BusinessAccessWorkflowModal';
import NotificationPushOverlay from './components/NotificationPushOverlay';
import { useBusinessAccess } from './hooks/useBusinessAccess';

export default function BusinessAccessPage() {
  const [form] = Form.useForm<BusinessAccessSearchValues>();
  const businessAccess = useBusinessAccess();

  return (
    <div className="page-surface business-access-page">
      <div className="business-access-stack">
        <BusinessAccessSearchForm
          form={form}
          busy={businessAccess.busy}
          searching={businessAccess.activity?.operation === 'search'}
          onSearch={(values) => void businessAccess.search(values)}
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
        onPush={(notification, versionType) => void businessAccess.pushNotification(notification, versionType)}
      />
      <BusinessAccessWorkflowModal activity={businessAccess.activity} />
    </div>
  );
}
