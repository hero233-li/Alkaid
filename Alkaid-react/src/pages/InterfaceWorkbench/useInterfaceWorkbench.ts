import { useCallback, useEffect, useMemo, useState } from 'react';
import { message } from 'antd';

import {
  clearWorkbenchHistory,
  deleteWorkbenchHistory,
  executeWorkbenchRequest,
  fetchWorkbenchHistory,
  fetchWorkbenchHistoryDetail,
  renameWorkbenchHistory,
} from '../../api/workbench';
import type {
  WorkbenchBodyMode,
  WorkbenchHistoryItem,
  WorkbenchRequestPayload,
  WorkbenchResponsePayload,
} from '../../types';
import type { RequestCodeLanguage } from '../../utils/workbenchCodegen';
import { parseCurl } from './curlParser';
import { displayRequestName } from './presentation';
import {
  buildFileParts,
  buildFormFields,
  buildHeaders,
  buildUrlWithParams,
  createDefaultFormRows,
  createDefaultHeaders,
  formatJsonText,
  formFieldsToRows,
  recordToRows,
  splitUrlAndParams,
  type FormRow,
  type KeyValueRow,
} from './requestModel';

const SUPPORTED_METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD']);

export function useInterfaceWorkbench() {
  const [method, setMethod] = useState('GET');
  const [url, setUrl] = useState('');
  const [params, setParams] = useState<KeyValueRow[]>([]);
  const [headers, setHeaders] = useState<KeyValueRow[]>(createDefaultHeaders);
  const [cookies, setCookies] = useState<KeyValueRow[]>([]);
  const [authType, setAuthType] = useState('none');
  const [authToken, setAuthToken] = useState('');
  const [bodyMode, setBodyMode] = useState<WorkbenchBodyMode>('none');
  const [body, setBody] = useState('');
  const [formRows, setFormRows] = useState<FormRow[]>(createDefaultFormRows);
  const [response, setResponse] = useState<WorkbenchResponsePayload | null>(null);
  const [lastRequest, setLastRequest] = useState<WorkbenchRequestPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyItems, setHistoryItems] = useState<WorkbenchHistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null);
  const [historySearch, setHistorySearch] = useState('');
  const [curlModalOpen, setCurlModalOpen] = useState(false);
  const [curlText, setCurlText] = useState('');
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<WorkbenchHistoryItem | null>(null);
  const [renameName, setRenameName] = useState('');
  const [renameSaving, setRenameSaving] = useState(false);
  const [requestCodeLanguage, setRequestCodeLanguage] = useState<RequestCodeLanguage>('shell');

  const filteredHistory = useMemo(() => {
    const keyword = historySearch.trim().toLowerCase();
    return keyword
      ? historyItems.filter((item) =>
          `${item.method} ${displayRequestName(item)} ${item.url}`.toLowerCase().includes(keyword),
        )
      : historyItems;
  }, [historyItems, historySearch]);
  const selectedHistoryItem = useMemo(
    () => historyItems.find((item) => item.id === selectedHistoryId) || null,
    [historyItems, selectedHistoryId],
  );

  const loadHistory = useCallback(async (selectId?: number) => {
    setHistoryLoading(true);
    try {
      setHistoryItems(await fetchWorkbenchHistory());
      if (selectId) setSelectedHistoryId(selectId);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求历史获取失败');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => void loadHistory(), [loadHistory]);

  const resetRequest = () => {
    setMethod('GET');
    setUrl('');
    setParams([]);
    setHeaders(createDefaultHeaders());
    setCookies([]);
    setAuthType('none');
    setAuthToken('');
    setBodyMode('none');
    setBody('');
    setFormRows(createDefaultFormRows());
    setResponse(null);
    setLastRequest(null);
    setSelectedHistoryId(null);
  };

  const parseParamsFromUrl = () => {
    if (!url.includes('?')) return;
    const split = splitUrlAndParams(url);
    setUrl(split.url);
    setParams(split.params);
  };

  const sendRequest = async () => {
    if (!url.trim()) {
      message.warning('请先填写 URL');
      return;
    }
    const payload: WorkbenchRequestPayload = {
      method,
      url: buildUrlWithParams(url.trim(), params),
      headers: buildHeaders(headers, bodyMode, cookies, authType, authToken),
      bodyMode,
      body: bodyMode === 'none' ? '' : body,
      formFields:
        bodyMode === 'form-urlencoded' || bodyMode === 'form-data' ? buildFormFields(formRows) : [],
      timeoutSeconds: 30,
    };
    setLoading(true);
    try {
      const result = await executeWorkbenchRequest(
        payload,
        bodyMode === 'form-data' ? buildFileParts(formRows) : [],
      );
      setResponse(result);
      setLastRequest(payload);
      await loadHistory(result.historyId);
      if (result.success) message.success('请求完成');
      else message.error(result.errorMessage || '请求失败');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  const openHistory = async (id: number) => {
    setSelectedHistoryId(id);
    setHistoryLoading(true);
    try {
      const detail = await fetchWorkbenchHistoryDetail(id);
      const payload = detail.requestPayload;
      const split = splitUrlAndParams(payload.url || detail.url);
      setMethod(payload.method || detail.method || 'GET');
      setUrl(split.url);
      setParams(split.params);
      setHeaders(recordToRows('header', payload.headers || detail.requestHeaders || {}));
      setCookies([]);
      setAuthType('none');
      setAuthToken('');
      setBodyMode(payload.bodyMode || 'raw');
      setBody(payload.body || '');
      setFormRows(formFieldsToRows(payload.formFields));
      setResponse({
        success: Boolean(detail.success),
        statusCode: detail.responseStatus || 0,
        durationMs: detail.durationMs || 0,
        headers: detail.responseHeaders || {},
        body: detail.responseBody || '',
        errorMessage: detail.errorMessage,
        historyId: detail.id,
      });
      setLastRequest(payload);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求历史详情获取失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  const clearHistory = async () => {
    try {
      await clearWorkbenchHistory();
      setHistoryItems([]);
      setSelectedHistoryId(null);
      message.success('请求历史已清理');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求历史清理失败');
    }
  };
  const startRenameHistory = (item: WorkbenchHistoryItem) => {
    setRenameTarget(item);
    setRenameName(displayRequestName(item));
    setRenameModalOpen(true);
  };
  const cancelRename = () => {
    setRenameModalOpen(false);
    setRenameTarget(null);
  };
  const submitRenameHistory = async () => {
    if (!renameTarget) return;
    const nextName = renameName.trim();
    if (!nextName) {
      message.warning('请求名称不能为空');
      return;
    }
    setRenameSaving(true);
    try {
      const updated = await renameWorkbenchHistory(renameTarget.id, nextName);
      setHistoryItems((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      cancelRename();
      message.success('请求名称已修改');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求名称修改失败');
    } finally {
      setRenameSaving(false);
    }
  };
  const deleteHistoryItem = async (id: number) => {
    try {
      await deleteWorkbenchHistory(id);
      setHistoryItems((items) => items.filter((item) => item.id !== id));
      if (selectedHistoryId === id) {
        setSelectedHistoryId(null);
        setResponse(null);
        setLastRequest(null);
      }
      message.success('请求记录已删除');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求删除失败');
    }
  };
  const formatBody = () => {
    if (bodyMode !== 'json') {
      message.warning('只有 JSON 请求体可以格式化');
      return;
    }
    if (!body.trim()) return;
    try {
      setBody(formatJsonText(body));
    } catch {
      message.warning('当前请求体不是合法 JSON');
    }
  };
  const closeCurlModal = () => {
    setCurlModalOpen(false);
    setCurlText('');
  };
  const importCurl = () => {
    try {
      const parsed = parseCurl(curlText);
      setMethod(SUPPORTED_METHODS.has(parsed.method) ? parsed.method : 'GET');
      setUrl(parsed.url);
      setParams(parsed.params);
      setHeaders(parsed.headers.length ? parsed.headers : createDefaultHeaders());
      setBodyMode(parsed.bodyMode);
      setBody(
        parsed.bodyMode === 'form-urlencoded' || parsed.bodyMode === 'form-data' ? '' : parsed.body,
      );
      setFormRows(parsed.formRows.length ? parsed.formRows : createDefaultFormRows());
      closeCurlModal();
      message.success('cURL 已导入');
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'cURL 解析失败');
    }
  };
  const copyResponseBody = async () => {
    if (!response?.body) return;
    try {
      await navigator.clipboard.writeText(response.body);
      message.success('响应体已复制');
    } catch {
      message.error('复制失败');
    }
  };

  return {
    request: {
      method,
      setMethod,
      url,
      setUrl,
      params,
      setParams,
      headers,
      setHeaders,
      cookies,
      setCookies,
      authType,
      setAuthType,
      authToken,
      setAuthToken,
      bodyMode,
      setBodyMode,
      body,
      setBody,
      formRows,
      setFormRows,
      loading,
      resetRequest,
      parseParamsFromUrl,
      sendRequest,
      formatBody,
    },
    history: {
      items: historyItems,
      visibleItems: filteredHistory,
      selectedId: selectedHistoryId,
      loading: historyLoading,
      search: historySearch,
      setSearch: setHistorySearch,
      load: loadHistory,
      open: openHistory,
      clear: clearHistory,
      remove: deleteHistoryItem,
      startRename: startRenameHistory,
      renameOpen: renameModalOpen,
      renameName,
      setRenameName,
      renameSaving,
      cancelRename,
      submitRename: submitRenameHistory,
      title: displayRequestName(selectedHistoryItem),
    },
    response: {
      value: response,
      lastRequest,
      language: requestCodeLanguage,
      setLanguage: setRequestCodeLanguage,
      copyBody: copyResponseBody,
    },
    curl: {
      open: curlModalOpen,
      text: curlText,
      setText: setCurlText,
      show: () => {
        setCurlText('');
        setCurlModalOpen(true);
      },
      close: closeCurlModal,
      import: importCurl,
    },
  };
}
