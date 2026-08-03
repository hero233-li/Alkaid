import type { Dispatch, SetStateAction } from 'react';
import { Button, Checkbox, Empty, Input, Segmented, Select, Tabs, Tooltip, Typography } from 'antd';
import { FileJson, Plus, SendHorizontal, Trash2, Zap } from 'lucide-react';

import type { WorkbenchBodyMode, WorkbenchFormFieldType } from '../../types';
import { createFormRow, createKeyValueRow, type FormRow, type KeyValueRow } from './requestModel';

const { TextArea } = Input;
const METHOD_OPTIONS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'].map((value) => ({
  label: value,
  value,
}));
const BODY_MODE_OPTIONS: Array<{ label: string; value: WorkbenchBodyMode }> = [
  { label: 'none', value: 'none' },
  { label: 'form-data', value: 'form-data' },
  { label: 'x-www-form-urlencoded', value: 'form-urlencoded' },
  { label: 'JSON', value: 'json' },
  { label: 'Raw', value: 'raw' },
];
const FORM_FIELD_TYPE_OPTIONS: Array<{ label: string; value: WorkbenchFormFieldType }> = [
  { label: '文本', value: 'text' },
  { label: '文件', value: 'file' },
];
const AUTH_TYPE_OPTIONS = [
  { label: '无认证', value: 'none' },
  { label: 'Bearer Token', value: 'bearer' },
];

interface RequestEditorProps {
  title: string;
  method: string;
  setMethod: (value: string) => void;
  url: string;
  setUrl: (value: string) => void;
  params: KeyValueRow[];
  setParams: Dispatch<SetStateAction<KeyValueRow[]>>;
  headers: KeyValueRow[];
  setHeaders: Dispatch<SetStateAction<KeyValueRow[]>>;
  cookies: KeyValueRow[];
  setCookies: Dispatch<SetStateAction<KeyValueRow[]>>;
  authType: string;
  setAuthType: (value: string) => void;
  authToken: string;
  setAuthToken: (value: string) => void;
  bodyMode: WorkbenchBodyMode;
  setBodyMode: (value: WorkbenchBodyMode) => void;
  body: string;
  setBody: (value: string) => void;
  formRows: FormRow[];
  setFormRows: Dispatch<SetStateAction<FormRow[]>>;
  loading: boolean;
  onNew: () => void;
  onParseUrl: () => void;
  onSend: () => void;
  onFormatBody: () => void;
}

export function RequestEditor(props: RequestEditorProps) {
  const updateRows = (
    setter: Dispatch<SetStateAction<KeyValueRow[]>>,
    id: string,
    patch: Partial<KeyValueRow>,
  ) => setter((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const keyValueEditor = (
    rows: KeyValueRow[],
    setter: Dispatch<SetStateAction<KeyValueRow[]>>,
    prefix: string,
    addText: string,
  ) => (
    <div className="kv-editor">
      <div className="workbench-section-header slim">
        <Typography.Text strong>{addText.replace('新增', '')}</Typography.Text>
        <Button
          icon={<Plus size={16} />}
          onClick={() => setter((items) => [...items, createKeyValueRow(prefix)])}
        >
          {addText}
        </Button>
      </div>
      <div className="kv-grid kv-grid-head">
        <span>启用</span>
        <span>参数名</span>
        <span>参数值</span>
        <span>操作</span>
      </div>
      <div className="kv-list">
        {rows.map((row) => (
          <div className="kv-grid" key={row.id}>
            <Checkbox
              checked={row.enabled}
              onChange={(event) => updateRows(setter, row.id, { enabled: event.target.checked })}
            />
            <Input
              value={row.name}
              placeholder="name"
              onChange={(event) => updateRows(setter, row.id, { name: event.target.value })}
            />
            <Input
              value={row.value}
              placeholder="value"
              onChange={(event) => updateRows(setter, row.id, { value: event.target.value })}
            />
            <Tooltip title="删除">
              <Button
                icon={<Trash2 size={16} />}
                onClick={() => setter((items) => items.filter((item) => item.id !== row.id))}
              />
            </Tooltip>
          </div>
        ))}
      </div>
    </div>
  );
  const updateFormRow = (id: string, patch: Partial<FormRow>) =>
    props.setFormRows((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const showFormEditor = props.bodyMode === 'form-urlencoded' || props.bodyMode === 'form-data';
  return (
    <>
      <div className="workbench-tabs-strip">
        <div className="request-tab active">
          <Zap size={15} />
          <span>{props.title}</span>
        </div>
        <Button icon={<Plus size={16} />} onClick={props.onNew} />
      </div>
      <section className="request-editor-pane">
        <div className="request-url-bar">
          <Select
            className="method-select"
            value={props.method}
            options={METHOD_OPTIONS}
            onChange={props.setMethod}
          />
          <Input
            value={props.url}
            placeholder="https://example.com/api/demo"
            onBlur={props.onParseUrl}
            onChange={(event) => props.setUrl(event.target.value)}
            onPressEnter={props.onSend}
          />
          <Button
            type="primary"
            icon={<SendHorizontal size={16} />}
            loading={props.loading}
            onClick={props.onSend}
          >
            发送
          </Button>
        </div>
        <Tabs
          className="request-config-tabs"
          items={[
            {
              key: 'params',
              label: `Params ${props.params.filter((row) => row.enabled && row.name.trim()).length}`,
              children: keyValueEditor(props.params, props.setParams, 'param', '新增参数'),
            },
            {
              key: 'body',
              label: 'Body',
              children: (
                <div className="body-editor">
                  <div className="body-mode-line">
                    <Segmented
                      value={props.bodyMode}
                      options={BODY_MODE_OPTIONS}
                      onChange={(value) => props.setBodyMode(value as WorkbenchBodyMode)}
                    />
                    <Button
                      icon={<FileJson size={16} />}
                      disabled={props.bodyMode !== 'json'}
                      onClick={props.onFormatBody}
                    >
                      格式化 JSON
                    </Button>
                  </div>
                  {props.bodyMode === 'none' ? (
                    <div className="body-empty">
                      <Empty description="该请求没有 Body" />
                    </div>
                  ) : null}
                  {props.bodyMode === 'json' || props.bodyMode === 'raw' ? (
                    <TextArea
                      className="request-body-input"
                      value={props.body}
                      placeholder={
                        props.bodyMode === 'json' ? '{"name":"Alioth"}' : 'raw request body'
                      }
                      onChange={(event) => props.setBody(event.target.value)}
                    />
                  ) : null}
                  {showFormEditor ? (
                    <>
                      <div
                        className={`form-field-grid form-field-head ${props.bodyMode === 'form-data' ? 'with-type' : ''}`}
                      >
                        <span>启用</span>
                        {props.bodyMode === 'form-data' ? <span>类型</span> : null}
                        <span>名称</span>
                        <span>值</span>
                        <span>操作</span>
                      </div>
                      <div className="form-field-list">
                        {props.formRows.map((row) => (
                          <div
                            className={`form-field-grid ${props.bodyMode === 'form-data' ? 'with-type' : ''}`}
                            key={row.id}
                          >
                            <Checkbox
                              checked={row.enabled}
                              onChange={(event) =>
                                updateFormRow(row.id, { enabled: event.target.checked })
                              }
                            />
                            {props.bodyMode === 'form-data' ? (
                              <Select
                                value={row.type}
                                options={FORM_FIELD_TYPE_OPTIONS}
                                onChange={(value) =>
                                  updateFormRow(row.id, { type: value, value: '', file: null })
                                }
                              />
                            ) : null}
                            <Input
                              value={row.name}
                              placeholder="name"
                              onChange={(event) =>
                                updateFormRow(row.id, { name: event.target.value })
                              }
                            />
                            {props.bodyMode === 'form-data' && row.type === 'file' ? (
                              <div className="file-field-cell">
                                <input
                                  className="form-file-input"
                                  type="file"
                                  onChange={(event) =>
                                    updateFormRow(row.id, {
                                      file: event.currentTarget.files?.[0] || null,
                                    })
                                  }
                                />
                                {row.file ? (
                                  <Typography.Text type="secondary">
                                    {row.file.name}
                                  </Typography.Text>
                                ) : null}
                                {!row.file && row.value ? (
                                  <Typography.Text type="secondary">{row.value}</Typography.Text>
                                ) : null}
                              </div>
                            ) : (
                              <Input
                                value={row.value}
                                placeholder="value"
                                onChange={(event) =>
                                  updateFormRow(row.id, { value: event.target.value })
                                }
                              />
                            )}
                            <Tooltip title="删除">
                              <Button
                                icon={<Trash2 size={16} />}
                                onClick={() =>
                                  props.setFormRows((rows) =>
                                    rows.filter((item) => item.id !== row.id),
                                  )
                                }
                              />
                            </Tooltip>
                          </div>
                        ))}
                      </div>
                      <Button
                        icon={<Plus size={16} />}
                        onClick={() => props.setFormRows((rows) => [...rows, createFormRow()])}
                      >
                        新增字段
                      </Button>
                    </>
                  ) : null}
                </div>
              ),
            },
            {
              key: 'headers',
              label: `Headers ${props.headers.filter((row) => row.enabled && row.name.trim()).length}`,
              children: keyValueEditor(props.headers, props.setHeaders, 'header', '新增 Header'),
            },
            {
              key: 'cookies',
              label: `Cookies ${props.cookies.filter((row) => row.enabled && row.name.trim()).length}`,
              children: keyValueEditor(props.cookies, props.setCookies, 'cookie', '新增 Cookie'),
            },
            {
              key: 'auth',
              label: 'Auth',
              children: (
                <div className="auth-editor">
                  <Select
                    value={props.authType}
                    options={AUTH_TYPE_OPTIONS}
                    onChange={props.setAuthType}
                  />
                  <Input.Password
                    value={props.authToken}
                    disabled={props.authType !== 'bearer'}
                    placeholder="Bearer Token"
                    onChange={(event) => props.setAuthToken(event.target.value)}
                  />
                </div>
              ),
            },
          ]}
        />
      </section>
    </>
  );
}
