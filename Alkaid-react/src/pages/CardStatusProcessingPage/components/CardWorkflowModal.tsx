import {Modal, Progress, Space, Tag, Typography} from 'antd';
import type {CardActivity} from '../types';

export default function CardWorkflowModal({activity}: { activity: CardActivity | null }) {
    return <Modal title="卡状态处理" open={Boolean(activity)} centered closable={false} keyboard={false}
                  maskClosable={false} footer={null} zIndex={1200}>{activity && <><Space
        style={{display: 'flex', justifyContent: 'space-between', marginBottom: 18}}><Typography.Text
        strong>{activity.label}</Typography.Text><Tag color="processing">{activity.status}</Tag></Space><Progress
        percent={activity.progress || 5} status="active" strokeWidth={13}/>{activity.currentStep &&
        <Typography.Text type="secondary">当前岗位：{activity.currentStep}</Typography.Text>}</>}</Modal>
}
