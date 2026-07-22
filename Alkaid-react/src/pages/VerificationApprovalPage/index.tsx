import { Alert, message } from 'antd';
import VerificationActionModal from './components/VerificationActionModal';
import VerificationSearchForm from './components/VerificationSearchForm';
import VerificationTaskPanel from './components/VerificationTaskPanel';
import VerificationWorkflowModal from './components/VerificationWorkflowModal';
import { useVerificationApproval } from './hooks/useVerificationApproval';
import { useVerificationApprovalForm } from './hooks/useVerificationApprovalForm';
import type { VerificationSearchValues } from './types';
import './styles.css';

export default function VerificationApprovalPage() {
  const approvalForm = useVerificationApprovalForm();
  const approval = useVerificationApproval();

  const search = (values: VerificationSearchValues) => {
    try {
      void approval.search(approvalForm.createSubmission(values));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '搜索条件不完整');
    }
  };

  const reset = () => {
    approvalForm.reset();
    approval.clear();
  };

  return (
    <div className="page-surface verification-approval-page">
      <div className="verification-approval-stack">
        {approvalForm.configError && (
          <Alert
            type="error"
            showIcon
            message="核实审批配置加载失败"
            description={approvalForm.configError}
          />
        )}
        <VerificationSearchForm
          form={approvalForm.form}
          initialValues={approvalForm.initialValues}
          searching={approval.searching || approval.refreshing || approval.updating}
          configLoading={approvalForm.configLoading}
          environmentOptions={approvalForm.options.environmentOptions}
          categoryOptions={approvalForm.options.categoryOptions}
          onSearch={search}
          onReset={reset}
        />
        <VerificationTaskPanel
          task={approval.task}
          hasSearched={approval.hasSearched}
          allCompleted={approval.allCompleted}
          busy={approval.refreshing || approval.updating}
          onClaim={approval.claim}
          onReturn={approval.returnToPool}
          onRefresh={approval.refresh}
          onItemChange={approval.setItemCompleted}
          onAction={approval.openAction}
        />
      </div>
      <VerificationActionModal
        action={approval.pendingAction}
        confirming={approval.updating}
        onConfirm={approval.confirmAction}
        onCancel={approval.closeAction}
      />
      <VerificationWorkflowModal
        active={approval.searching || approval.refreshing || approval.updating}
        label={approval.activity?.label ?? '正在处理核实审批任务'}
        progress={approval.activity?.progress ?? 5}
      />
    </div>
  );
}
