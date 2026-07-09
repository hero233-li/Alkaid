import { useCallback, useEffect, useState } from 'react';
import { Button, Form, Input, Modal, Popconfirm, Space, Table, Typography, message } from 'antd';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { createReleaseNote, deleteReleaseNote, listReleaseNotes, updateReleaseNote } from '../api/portal';
import type { ReleaseNote } from '../types';
import { PORTAL_CONTENT_CHANGED_EVENT } from './WelcomePage';

interface ReleaseFormValues {
  version: string;
  content: string;
}

function formatDate(value: string) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '-';
}

export default function ReleaseManagementPage() {
  const [form] = Form.useForm<ReleaseFormValues>();
  const [items, setItems] = useState<ReleaseNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingItem, setEditingItem] = useState<ReleaseNote | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listReleaseNotes());
    } catch (error) {
      message.error(error instanceof Error ? error.message : '获取版本记录失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (item: ReleaseNote) => {
    setEditingItem(item);
    form.setFieldsValue({ version: item.version, content: item.content });
    setModalOpen(true);
  };

  const saveItem = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editingItem) {
        await updateReleaseNote(editingItem.id, values);
        message.success('版本内容已修改');
      } else {
        await createReleaseNote(values);
        message.success('版本已发布，首页将展示这条最新说明');
      }
      setModalOpen(false);
      setEditingItem(null);
      form.resetFields();
      await loadItems();
      window.dispatchEvent(new Event(PORTAL_CONTENT_CHANGED_EVENT));
    } catch (error) {
      message.error(error instanceof Error ? error.message : editingItem ? '修改版本失败' : '新增版本失败');
    } finally {
      setSaving(false);
    }
  };

  const removeItem = async (id: number) => {
    try {
      await deleteReleaseNote(id);
      message.success('版本记录已删除');
      await loadItems();
      window.dispatchEvent(new Event(PORTAL_CONTENT_CHANGED_EVENT));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除版本失败');
    }
  };

  return (
    <div className="page-surface">
      <div className="page-title-row">
        <div>
          <Typography.Title level={3}>版本管理</Typography.Title>
          <Typography.Text type="secondary">维护首页展示的版本更新说明</Typography.Text>
        </div>
        <Button type="primary" icon={<Plus size={16} />} onClick={openCreateModal}>
          新增版本
        </Button>
      </div>

      <Table<ReleaseNote>
        rowKey="id"
        loading={loading}
        dataSource={items}
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        columns={[
          { title: '版本', dataIndex: 'version', width: 150, render: (value: string) => <Typography.Text strong>{value}</Typography.Text> },
          { title: '版本说明', dataIndex: 'content', render: (value: string) => <Typography.Paragraph className="release-table-content" ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}>{value}</Typography.Paragraph> },
          { title: '发布时间', dataIndex: 'createdAt', width: 190, render: (value: string) => formatDate(value) },
          {
            title: '操作',
            key: 'actions',
            width: 170,
            render: (_, record) => (
              <Space size={4}>
                <Button type="text" icon={<Pencil size={15} />} onClick={() => openEditModal(record)}>修改</Button>
                <Popconfirm title="确认删除这条版本记录？" onConfirm={() => removeItem(record.id)}>
                  <Button type="text" danger icon={<Trash2 size={15} />}>删除</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingItem ? '修改版本' : '新增版本'}
        open={modalOpen}
        confirmLoading={saving}
        onOk={saveItem}
        onCancel={() => {
          setModalOpen(false);
          setEditingItem(null);
          form.resetFields();
        }}
        okText={editingItem ? '保存' : '发布'}
        cancelText="取消"
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.Item name="version" label="版本号" rules={[{ required: true, message: '请输入版本号' }, { max: 100 }]}>
            <Input placeholder="例如：v0.2.0" autoFocus />
          </Form.Item>
          <Form.Item name="content" label="版本说明" rules={[{ required: true, message: '请输入版本说明' }]}>
            <Input.TextArea rows={7} placeholder="填写本次版本更新的内容" showCount maxLength={5000} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
