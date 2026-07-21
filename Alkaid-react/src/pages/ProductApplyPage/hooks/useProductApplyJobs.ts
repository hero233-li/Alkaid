import { useCallback, useEffect, useMemo, useState } from 'react';
import { message } from 'antd';
import { cancelJob, getJobDetail, retryJob, streamJobLogs } from '../../../api/jobs';
import { executeProductApplication } from '../api/productApplicationApi';
import type { ProductApplicationResult, ProductApplicationSubmission } from '../model/types';
import { activeStatuses, mergeJobDetail, terminalStatuses } from '../model/jobModel';
import { persistResultSummaries, readResultSummaries, resultCacheKey } from '../model/cache';

export function useProductApplyJobs(pageInstanceKey: string) {
  const cacheKey = resultCacheKey(pageInstanceKey);
  const [results, setResults] = useState<ProductApplicationResult[]>(() =>
    readResultSummaries(cacheKey),
  );
  const [selectedResult, setSelectedResult] = useState<ProductApplicationResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const updateResult = useCallback(
    (id: number, updater: (current: ProductApplicationResult) => ProductApplicationResult) => {
      setResults((currentResults) => {
        const nextResults = currentResults.map((item) => (item.id === id ? updater(item) : item));
        persistResultSummaries(cacheKey, nextResults);
        return nextResults;
      });
      setSelectedResult((current) => (current?.id === id ? updater(current) : current));
    },
    [cacheKey],
  );

  useEffect(() => {
    const cachedResults = readResultSummaries(cacheKey);
    setResults(cachedResults);
    setSelectedResult(null);
    let active = true;
    void Promise.all(cachedResults.map((result) => getJobDetail(result.id).catch(() => null))).then(
      (details) => {
        if (!active) {
          return;
        }
        details.forEach((detail) => {
          if (detail) {
            updateResult(detail.id, (current) => mergeJobDetail(current, detail));
          }
        });
      },
    );
    return () => {
      active = false;
    };
  }, [cacheKey, updateResult]);

  const activeJobIds = useMemo(
    () => results.filter((item) => activeStatuses.has(item.status)).map((item) => item.id),
    [results],
  );
  const activeJobKey = activeJobIds.join(',');

  useEffect(() => {
    if (!activeJobIds.length) {
      return;
    }
    let active = true;
    const refresh = async () => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      const details = await Promise.all(
        activeJobIds.map((id) => getJobDetail(id).catch(() => null)),
      );
      if (!active) {
        return;
      }
      details.forEach((detail) => {
        if (detail) {
          updateResult(detail.id, (current) => mergeJobDetail(current, detail));
        }
      });
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeJobKey, updateResult]);

  useEffect(() => {
    if (!selectedResult) {
      return;
    }
    let active = true;
    void getJobDetail(selectedResult.id)
      .then((detail) => {
        if (active) {
          updateResult(detail.id, (current) => mergeJobDetail(current, detail));
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [selectedResult?.id, updateResult]);

  useEffect(() => {
    if (!selectedResult) {
      return;
    }
    const selectedId = selectedResult.id;
    const controller = new AbortController();
    const afterId = Math.max(0, ...selectedResult.logs.map((log) => log.id || 0));
    let lastLogId = afterId;
    const connect = async () => {
      for (let attempt = 1; attempt <= 3 && !controller.signal.aborted; attempt += 1) {
        try {
          const streamResult = await streamJobLogs(
            selectedId,
            lastLogId,
            {
              onLog: (log) => {
                lastLogId = Math.max(lastLogId, log.id || 0);
                updateResult(selectedId, (current) => {
                  if (log.id && current.logs.some((item) => item.id === log.id)) {
                    return current;
                  }
                  return { ...current, logs: [...current.logs, log] };
                });
              },
              onStatus: (status) =>
                updateResult(selectedId, (current) => ({
                  ...current,
                  status: status.status,
                  progress: status.progress,
                  stage:
                    status.status === 'success'
                      ? 'completed'
                      : terminalStatuses.has(status.status)
                        ? status.status
                        : current.stage,
                })),
            },
            controller.signal,
          );
          lastLogId = streamResult.lastLogId;
          if (streamResult.terminalStatusReceived || controller.signal.aborted) {
            return;
          }
          throw new Error('日志流在任务结束前断开');
        } catch (streamError) {
          if (controller.signal.aborted) {
            return;
          }
          if (attempt === 3) {
            console.warn(streamError);
            return;
          }
          await new Promise((resolve) => window.setTimeout(resolve, attempt * 1000));
        }
      }
    };
    void connect();
    return () => controller.abort();
  }, [selectedResult?.id, updateResult]);

  const submit = useCallback(
    async (submission: ProductApplicationSubmission) => {
      setSubmitting(true);
      try {
        const result = await executeProductApplication(submission);
        setResults((currentResults) => {
          const nextResults = [result, ...currentResults];
          persistResultSummaries(cacheKey, nextResults);
          return nextResults;
        });
        setSelectedResult(result);
        message.success('产品申请已提交，正在后台执行');
      } catch (submitError) {
        message.error(submitError instanceof Error ? submitError.message : '产品申请执行失败');
      } finally {
        setSubmitting(false);
      }
    },
    [cacheKey],
  );

  const retry = useCallback(
    async (result: ProductApplicationResult) => {
      try {
        const detail = await retryJob(result.id);
        updateResult(result.id, (current) => mergeJobDetail(current, detail));
        message.success(`已提交第 ${detail.attemptCount} 次执行`);
      } catch (retryError) {
        message.error(retryError instanceof Error ? retryError.message : '重试失败');
      }
    },
    [updateResult],
  );

  const cancel = useCallback(
    async (result: ProductApplicationResult) => {
      try {
        const detail = await cancelJob(result.id);
        updateResult(result.id, (current) => mergeJobDetail(current, detail));
        message.success('Job 已取消');
      } catch (cancelError) {
        message.error(cancelError instanceof Error ? cancelError.message : '取消失败');
      }
    },
    [updateResult],
  );

  return {
    results,
    selectedResult,
    submitting,
    selectResult: setSelectedResult,
    closeDetail: () => setSelectedResult(null),
    submit,
    retry,
    cancel,
  };
}
