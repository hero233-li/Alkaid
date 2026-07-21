import { useCallback, useRef, useState } from 'react';
import { message } from 'antd';
import {
  invalidateBusinessAccess,
  listBusinessAccessNotifications,
  pollBusinessAccessJob,
  pushBusinessAccessNotification,
  searchBusinessAccess,
} from '../api/businessAccess';
import {
  buildBusinessAccessWorkflowActivity,
  extractBusinessAccessNotifications,
  extractBusinessAccessRecord,
  extractBusinessAccessRecords,
  extractNotificationPushResult,
} from '../model/jobModel';
import type {
  BusinessAccessJobSubmission,
  BusinessAccessNotification,
  BusinessAccessOperation,
  BusinessAccessRecord,
  BusinessAccessSearchSubmission,
  BusinessAccessWorkflowActivity,
  NotificationVersionType,
} from '../types';

export function useBusinessAccess() {
  const [results, setResults] = useState<BusinessAccessRecord[]>([]);
  const [activity, setActivity] = useState<BusinessAccessWorkflowActivity | null>(null);
  const [invalidatingId, setInvalidatingId] = useState<number | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<BusinessAccessRecord | null>(null);
  const [notifications, setNotifications] = useState<BusinessAccessNotification[]>([]);
  const [pushingKey, setPushingKey] = useState<string | null>(null);
  const runningRef = useRef(false);

  const runWorkflow = useCallback(
    async (
      operation: BusinessAccessOperation,
      label: string,
      submit: () => Promise<BusinessAccessJobSubmission>,
    ) => {
      if (runningRef.current) {
        throw new Error('已有业务准入任务正在执行，请稍候');
      }
      runningRef.current = true;
      setActivity(buildBusinessAccessWorkflowActivity(operation, label, 'submitting', 0));
      try {
        const submitted = await submit();
        setActivity(
          buildBusinessAccessWorkflowActivity(
            operation,
            label,
            submitted.status,
            submitted.progress,
            submitted.id,
          ),
        );
        return await pollBusinessAccessJob(submitted.id, (detail) => {
          setActivity(
            buildBusinessAccessWorkflowActivity(
              operation,
              label,
              detail.status,
              detail.progress,
              detail.id,
            ),
          );
        });
      } finally {
        runningRef.current = false;
        setActivity(null);
      }
    },
    [],
  );

  const search = useCallback(
    async (values: BusinessAccessSearchSubmission) => {
      setResults([]);
      setSelectedRecord(null);
      setNotifications([]);
      try {
        const detail = await runWorkflow('search', '正在查询业务准入结果', () =>
          searchBusinessAccess(values),
        );
        const records = extractBusinessAccessRecords(detail);
        setResults(records);
        message.success(`查询完成，共返回 ${records.length} 条记录`);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '查询失败');
      }
    },
    [runWorkflow],
  );

  const invalidate = useCallback(
    async (record: BusinessAccessRecord) => {
      setInvalidatingId(record.id);
      try {
        const detail = await runWorkflow('invalidate', `正在将 ${record.businessNo} 设为失效`, () =>
          invalidateBusinessAccess(record.id),
        );
        const updated = extractBusinessAccessRecord(detail);
        setResults((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        setSelectedRecord((current) => (current?.id === updated.id ? updated : current));
        message.success(`${record.businessNo} 已失效`);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '失效操作失败');
      } finally {
        setInvalidatingId(null);
      }
    },
    [runWorkflow],
  );

  const openNotifications = useCallback(
    async (record: BusinessAccessRecord) => {
      setSelectedRecord(record);
      setNotifications([]);
      try {
        const detail = await runWorkflow(
          'notifications',
          `正在加载 ${record.businessNo} 的通知记录`,
          () => listBusinessAccessNotifications(record.id),
        );
        setNotifications(extractBusinessAccessNotifications(detail));
      } catch (error) {
        setSelectedRecord(null);
        message.error(error instanceof Error ? error.message : '获取通知记录失败');
      }
    },
    [runWorkflow],
  );

  const pushNotification = useCallback(
    async (notification: BusinessAccessNotification, versionType: NotificationVersionType) => {
      if (!selectedRecord) {
        return;
      }
      const key = `${notification.id}:${versionType}`;
      setPushingKey(key);
      try {
        const detail = await runWorkflow('push', `正在推送 ${notification.notificationNo}`, () =>
          pushBusinessAccessNotification(selectedRecord.id, notification.id, versionType),
        );
        const result = extractNotificationPushResult(detail);
        message.success(result.message);
      } catch (error) {
        message.error(error instanceof Error ? error.message : '通知推送失败');
      } finally {
        setPushingKey(null);
      }
    },
    [runWorkflow, selectedRecord],
  );

  const busy = activity !== null;
  return {
    results,
    activity,
    busy,
    invalidatingId,
    selectedRecord,
    notifications,
    pushingKey,
    search,
    invalidate,
    openNotifications,
    closeNotifications: () => {
      if (!runningRef.current) {
        setSelectedRecord(null);
      }
    },
    pushNotification,
  };
}
