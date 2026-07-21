import { Modal, QRCode, Typography } from 'antd';
export default function ApplicationLinkQrModal({
  value,
  onClose,
}: {
  value: string;
  onClose: () => void;
}) {
  return (
    <Modal title="申请二维码" open={Boolean(value)} onCancel={onClose} footer={null} centered>
      <div className="application-link-qrcode">
        <QRCode value={value || 'about:blank'} size={240} />
        <Typography.Text copyable>{value}</Typography.Text>
      </div>
    </Modal>
  );
}
