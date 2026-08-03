import { useMemo } from 'react';
import { Button, Empty, Segmented, Tooltip, message } from 'antd';
import { Clipboard } from 'lucide-react';

import type { WorkbenchRequestPayload } from '../../types';
import {
  REQUEST_CODE_LANGUAGE_OPTIONS,
  generateRequestCode,
  type RequestCodeLanguage,
} from '../../utils/workbenchCodegen';

interface RequestCodeViewProps {
  payload: WorkbenchRequestPayload | null;
  language: RequestCodeLanguage;
  onLanguageChange: (language: RequestCodeLanguage) => void;
}

export function RequestCodeView({ payload, language, onLanguageChange }: RequestCodeViewProps) {
  const code = useMemo(
    () => (payload ? generateRequestCode(payload, language) : ''),
    [payload, language],
  );
  const copyCode = async () => {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      message.success('请求代码已复制');
    } catch {
      message.error('复制失败');
    }
  };
  if (!payload) {
    return (
      <div className="request-code-empty">
        <Empty description="发送请求后查看实际请求代码" />
      </div>
    );
  }
  return (
    <div className="request-code-view">
      <div className="request-code-toolbar">
        <Segmented
          value={language}
          options={REQUEST_CODE_LANGUAGE_OPTIONS}
          onChange={(value) => onLanguageChange(value as RequestCodeLanguage)}
        />
        <Tooltip title="复制请求代码">
          <Button icon={<Clipboard size={16} />} onClick={copyCode}>
            复制
          </Button>
        </Tooltip>
      </div>
      <pre className="response-code request-code-block">{code}</pre>
    </div>
  );
}
