import { Modal, Typography } from 'antd';
import type { VerificationActionDefinition } from '../types';

interface VerificationActionModalProps {
  action: VerificationActionDefinition | null;
  confirming: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function VerificationActionModal({
  action,
  confirming,
  onConfirm,
  onCancel,
}: VerificationActionModalProps) {
  return (
    <Modal
      title={action?.title}
      open={Boolean(action)}
      centered
      okText="确定"
      confirmLoading={confirming}
      cancelText="不确定"
      closable={!confirming}
      maskClosable={!confirming}
      cancelButtonProps={{ disabled: confirming }}
      onOk={onConfirm}
      onCancel={() => {
        if (!confirming) onCancel();
      }}
      destroyOnClose
    >
      <Typography.Paragraph className="verification-action-description">
        {action?.description}
      </Typography.Paragraph>
    </Modal>
  );
}
