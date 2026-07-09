import type { ReactNode } from 'react';
import { Drawer, Modal, type DrawerProps, type ModalProps } from 'antd';

export type DetailPresentation = 'drawer' | 'modal';

export interface DetailOverlayProps {
  presentation: DetailPresentation;
  title: ReactNode;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: number | string;
  drawerProps?: Omit<DrawerProps, 'title' | 'open' | 'onClose' | 'width' | 'children'>;
  modalProps?: Omit<ModalProps, 'title' | 'open' | 'onCancel' | 'width' | 'children'>;
}

export default function DetailOverlay({
  presentation,
  title,
  open,
  onClose,
  children,
  width = 720,
  drawerProps,
  modalProps,
}: DetailOverlayProps) {
  if (presentation === 'modal') {
    return (
      <Modal
        {...modalProps}
        title={title}
        open={open}
        onCancel={onClose}
        width={width}
        footer={modalProps?.footer ?? null}
      >
        {children}
      </Modal>
    );
  }

  return (
    <Drawer {...drawerProps} title={title} open={open} onClose={onClose} width={width}>
      {children}
    </Drawer>
  );
}
