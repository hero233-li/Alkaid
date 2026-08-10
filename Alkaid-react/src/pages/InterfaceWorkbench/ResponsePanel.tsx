import { Alert, Button, Empty, Space, Tabs, Tag, Tooltip, Typography } from 'antd';
import { Clipboard, History } from 'lucide-react';

import type { WorkbenchRequestPayload, WorkbenchResponsePayload } from '../../types';
import type { RequestCodeLanguage } from '../../utils/workbenchCodegen';
import { RequestCodeView } from './RequestCodeView';
import { JsonResponseViewer, ResponseCookiesView, ResponseHeadersView } from './ResponseViewer';
import { parseResponseCookies } from './responseModel';
import { statusColor } from './presentation';

interface ResponsePanelProps {
  response: WorkbenchResponsePayload | null;
  lastRequest: WorkbenchRequestPayload | null;
  language: RequestCodeLanguage;
  onLanguageChange: (language: RequestCodeLanguage) => void;
  onCopyBody: () => void;
}

export function ResponsePanel({
  response,
  lastRequest,
  language,
  onLanguageChange,
  onCopyBody,
}: ResponsePanelProps) {
  const cookies = response ? parseResponseCookies(response.headers) : [];
  const headerCount = response ? Object.keys(response.headers || {}).length : 0;
  return (
    <section className="response-pane">
      <div className="response-summary">
        <div className="response-title">
          <History size={16} />
          <Typography.Text strong>响应</Typography.Text>
        </div>
        {response ? (
          <Space>
            <Tag color={response.success ? statusColor(response.statusCode) : 'error'}>
              {response.success ? response.statusCode : 'ERROR'}
            </Tag>
            <Typography.Text type="secondary">{response.durationMs} ms</Typography.Text>
            <Tooltip title="复制响应体">
              <Button icon={<Clipboard size={16} />} onClick={onCopyBody} />
            </Tooltip>
          </Space>
        ) : null}
      </div>
      {!response ? (
        <div className="response-empty">
          <Empty description="发送请求后查看响应，每次请求都会写入左侧历史" />
        </div>
      ) : (
        <>
          {response.errorMessage ? (
            <Alert type="error" message={response.errorMessage} showIcon />
          ) : null}
          <Tabs
            className="response-tabs"
            items={[
              { key: 'body', label: 'Body', children: <JsonResponseViewer body={response.body} /> },
              {
                key: 'cookies',
                label: `Cookie ${cookies.length}`,
                children: <ResponseCookiesView cookies={cookies} />,
              },
              {
                key: 'headers',
                label: `Header ${headerCount}`,
                children: <ResponseHeadersView headers={response.headers || {}} />,
              },
              {
                key: 'actual',
                label: '实际请求',
                children: (
                  <RequestCodeView
                    payload={lastRequest}
                    language={language}
                    onLanguageChange={onLanguageChange}
                  />
                ),
              },
            ]}
          />
        </>
      )}
    </section>
  );
}
