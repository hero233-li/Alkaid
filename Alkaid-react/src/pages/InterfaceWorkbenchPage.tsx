import { Input, Modal } from 'antd';

import { RequestEditor } from './InterfaceWorkbench/RequestEditor';
import { ResponsePanel } from './InterfaceWorkbench/ResponsePanel';
import { useInterfaceWorkbench } from './InterfaceWorkbench/useInterfaceWorkbench';
import { WorkbenchHistoryPanel } from './InterfaceWorkbench/WorkbenchHistoryPanel';

const { TextArea } = Input;
const CURL_PLACEHOLDER = `curl -X POST https://example.com/api -H 'Content-Type: application/json' -d '{"name":"Alioth"}'`;

export default function InterfaceWorkbenchPage() {
  const model = useInterfaceWorkbench();
  const request = model.request;
  const history = model.history;
  const response = model.response;
  const curl = model.curl;

  return (
    <div className="workbench-apifox">
      <WorkbenchHistoryPanel
        items={history.items}
        visibleItems={history.visibleItems}
        selectedId={history.selectedId}
        loading={history.loading}
        search={history.search}
        onSearchChange={history.setSearch}
        onNew={request.resetRequest}
        onImport={curl.show}
        onRefresh={() => void history.load()}
        onClear={() => void history.clear()}
        onOpen={(id) => void history.open(id)}
        onDelete={(id) => void history.remove(id)}
        onStartRename={history.startRename}
        renameOpen={history.renameOpen}
        renameName={history.renameName}
        renameSaving={history.renameSaving}
        onRenameNameChange={history.setRenameName}
        onRenameCancel={history.cancelRename}
        onRenameSubmit={() => void history.submitRename()}
      />
      <main className="workbench-main-pane">
        <RequestEditor
          title={history.title}
          method={request.method}
          setMethod={request.setMethod}
          url={request.url}
          setUrl={request.setUrl}
          params={request.params}
          setParams={request.setParams}
          headers={request.headers}
          setHeaders={request.setHeaders}
          cookies={request.cookies}
          setCookies={request.setCookies}
          authType={request.authType}
          setAuthType={request.setAuthType}
          authToken={request.authToken}
          setAuthToken={request.setAuthToken}
          bodyMode={request.bodyMode}
          setBodyMode={request.setBodyMode}
          body={request.body}
          setBody={request.setBody}
          formRows={request.formRows}
          setFormRows={request.setFormRows}
          loading={request.loading}
          onNew={request.resetRequest}
          onParseUrl={request.parseParamsFromUrl}
          onSend={() => void request.sendRequest()}
          onFormatBody={request.formatBody}
        />
        <ResponsePanel
          response={response.value}
          lastRequest={response.lastRequest}
          language={response.language}
          onLanguageChange={response.setLanguage}
          onCopyBody={() => void response.copyBody()}
        />
      </main>
      <Modal
        title="导入 cURL"
        open={curl.open}
        onCancel={curl.close}
        onOk={curl.import}
        okText="解析并填入"
        cancelText="取消"
        width={720}
      >
        <TextArea
          className="curl-import-input"
          value={curl.text}
          placeholder={CURL_PLACEHOLDER}
          onChange={(event) => curl.setText(event.target.value)}
        />
      </Modal>
    </div>
  );
}
