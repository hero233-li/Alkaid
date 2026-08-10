import { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Dropdown, Input, Modal, Tooltip, Typography } from 'antd';
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  ArrowLeft,
  Bold,
  CalendarDays,
  Code2,
  Eraser,
  FileDown,
  FileText,
  FileUp,
  Heading1,
  Heading2,
  Heading3,
  Image,
  IndentDecrease,
  IndentIncrease,
  Italic,
  Link,
  List,
  ListOrdered,
  ListTodo,
  Minus,
  PanelLeft,
  Quote,
  Redo2,
  Replace,
  Save,
  Search,
  Strikethrough,
  Table2,
  Undo2,
} from 'lucide-react';
import { markdownToRichTextHtml, richTextToMarkdown } from './documentMarkdown';
import { sanitizeWordHtml } from './wordDocument';
import {
  convertLegacyWordDocument,
  exportWordDocument,
  uploadDocumentImage,
} from '../../api/documents';
import { normalizeWordFileName } from './model';

type DocumentMenuKey = 'start' | 'heading' | 'paragraph' | 'insert' | 'review' | 'file';
const DEFAULT_DOCUMENT_FILE_NAME = '未命名文档';

interface DocumentDesignerProps {
  onBack: () => void;
  onSave: (fileName: string, content: string) => void;
  initialFileName?: string;
  initialContent?: string;
  storageFormat?: 'markdown' | 'word';
}

interface OutlineItem {
  level: number;
  label: string;
  index: number;
}

const escapeHtml = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export default function DocumentDesigner({
  onBack,
  onSave,
  initialFileName,
  initialContent = '',
  storageFormat = 'markdown',
}: DocumentDesignerProps) {
  const isWord = storageFormat === 'word';
  const defaultFileName = isWord ? '未命名在线 Word' : DEFAULT_DOCUMENT_FILE_NAME;
  const [modalApi, modalContextHolder] = Modal.useModal();
  const [activeMenu, setActiveMenu] = useState<DocumentMenuKey>('start');
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveFileName, setSaveFileName] = useState('');
  const [fileName, setFileName] = useState(
    () =>
      initialFileName?.replace(isWord ? /\.(?:doc|docx)$/i : /\.(?:md|markdown)$/i, '') ||
      defaultFileName,
  );
  const [editorHtml, setEditorHtml] = useState(() =>
    isWord ? sanitizeWordHtml(initialContent) : markdownToRichTextHtml(initialContent),
  );
  const [showOutline, setShowOutline] = useState(true);
  const [findDialogOpen, setFindDialogOpen] = useState(false);
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [wordImporting, setWordImporting] = useState(false);
  const [wordExporting, setWordExporting] = useState(false);
  const editorRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const wordInputRef = useRef<HTMLInputElement>(null);
  const savedRangeRef = useRef<Range | null>(null);
  useEffect(() => {
    const nextHtml = isWord
      ? sanitizeWordHtml(initialContent)
      : markdownToRichTextHtml(initialContent);
    if (editorRef.current) {
      editorRef.current.innerHTML = nextHtml;
    }
    setEditorHtml(nextHtml);
  }, [initialContent, isWord]);
  const outline = useMemo(() => {
    const root = new DOMParser().parseFromString(editorHtml, 'text/html');
    return Array.from(root.querySelectorAll('h1, h2, h3, h4, h5, h6')).map<OutlineItem>(
      (heading, index) => ({
        level: Number(heading.tagName.slice(1)),
        label: heading.textContent?.trim() || '未命名标题',
        index,
      }),
    );
  }, [editorHtml]);
  const characterCount = useMemo(() => {
    const root = new DOMParser().parseFromString(editorHtml, 'text/html');
    return (root.body.textContent ?? '').replace(/\s/g, '').length;
  }, [editorHtml]);

  const rememberSelection = () => {
    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
    if (range && editorRef.current?.contains(range.commonAncestorContainer)) {
      savedRangeRef.current = range.cloneRange();
    }
  };

  const restoreSelection = () => {
    const selection = window.getSelection();
    if (!selection || !savedRangeRef.current) return;
    selection.removeAllRanges();
    selection.addRange(savedRangeRef.current);
  };

  const syncEditor = () => {
    rememberSelection();
    setEditorHtml(editorRef.current?.innerHTML ?? '');
  };

  const runCommand = (command: string, value?: string) => {
    editorRef.current?.focus();
    restoreSelection();
    document.execCommand(command, false, value);
    syncEditor();
  };

  const insertHtml = (html: string) => runCommand('insertHTML', html);

  const applyInlineCode = () => {
    const selection = window.getSelection();
    const selectedText = selection?.toString() || '代码';
    insertHtml(`<code>${escapeHtml(selectedText)}</code>`);
  };

  const wrapSelectionElement = (tag: string, placeholder: string) => {
    const selection = window.getSelection();
    const selectedText = selection?.toString() || placeholder;
    insertHtml(`<${tag}>${escapeHtml(selectedText)}</${tag}>`);
  };

  const insertLink = () => {
    const selection = window.getSelection();
    const href = window.prompt('请输入链接地址', 'https://');
    if (!href?.trim()) return;
    if (selection?.toString()) runCommand('createLink', href.trim());
    else insertHtml(`<a href="${escapeHtml(href.trim())}">链接文字</a>`);
  };

  const insertImageFile = async (file?: File) => {
    if (!file || !file.type.startsWith('image/')) return;
    try {
      const asset = await uploadDocumentImage(file);
      insertHtml(`<img src="${asset.url}" alt="${escapeHtml(file.name)}"><p><br></p>`);
    } catch (error) {
      Modal.error({
        title: '图片上传失败',
        content: error instanceof Error ? error.message : '请稍后重试',
      });
    }
  };

  const selectAllContent = () => {
    const editor = editorRef.current;
    if (!editor) return;
    const range = document.createRange();
    range.selectNodeContents(editor);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    rememberSelection();
  };

  const selectFirstMatch = () => {
    const editor = editorRef.current;
    const keyword = findText.trim();
    if (!editor || !keyword) return;
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const index = (node.textContent ?? '')
        .toLocaleLowerCase()
        .indexOf(keyword.toLocaleLowerCase());
      if (index >= 0) {
        const range = document.createRange();
        range.setStart(node, index);
        range.setEnd(node, index + keyword.length);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
        savedRangeRef.current = range.cloneRange();
        (node.parentElement as HTMLElement | null)?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
        setFindDialogOpen(false);
        return;
      }
      node = walker.nextNode();
    }
    modalApi.info({ title: '查找结果', content: `没有找到“${keyword}”。` });
  };

  const replaceAllMatches = () => {
    const editor = editorRef.current;
    const keyword = findText.trim();
    if (!editor || !keyword) return;
    const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const matcher = new RegExp(escaped, 'gi');
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    const nodes: Text[] = [];
    let node = walker.nextNode();
    while (node) {
      nodes.push(node as Text);
      node = walker.nextNode();
    }
    let replacements = 0;
    nodes.forEach((textNode) => {
      textNode.data = textNode.data.replace(matcher, () => {
        replacements += 1;
        return replaceText;
      });
    });
    syncEditor();
    setFindDialogOpen(false);
    modalApi.success({ title: '替换完成', content: `共替换 ${replacements} 处内容。` });
  };

  const replaceEditorContentWithWord = async (file: File) => {
    setWordImporting(true);
    try {
      let html: string;
      if (/\.docx$/i.test(file.name)) {
        const mammoth = await import('mammoth');
        const result = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() });
        html = result.value;
      } else {
        html = (await convertLegacyWordDocument(file)).html;
      }
      const sanitized = sanitizeWordHtml(html);
      if (editorRef.current) editorRef.current.innerHTML = sanitized;
      setEditorHtml(sanitized);
      setFileName(file.name.replace(/\.(?:doc|docx)$/i, ''));
      modalApi.success({ title: '导入完成', content: `${file.name} 已载入在线 Word 编辑器。` });
    } catch (error) {
      modalApi.error({
        title: '导入失败',
        content: error instanceof Error ? error.message : '无法读取该 Word 文件',
      });
    } finally {
      setWordImporting(false);
    }
  };

  const requestWordImport = (file?: File) => {
    if (!file || !/\.(?:doc|docx)$/i.test(file.name)) return;
    const hasContent = Boolean((editorRef.current?.textContent ?? '').trim());
    if (!hasContent) {
      void replaceEditorContentWithWord(file);
      return;
    }
    modalApi.confirm({
      title: '导入 Word 文件？',
      content: '导入后将替换当前编辑区中的全部内容。',
      okText: '替换并导入',
      cancelText: '取消',
      onOk: () => replaceEditorContentWithWord(file),
    });
  };

  const downloadWordDocx = async () => {
    setWordExporting(true);
    try {
      const html = sanitizeWordHtml(editorRef.current?.innerHTML ?? editorHtml);
      const normalizedName = normalizeWordFileName(fileName);
      const blob = await exportWordDocument(normalizedName, html);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = normalizedName;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      modalApi.error({
        title: '导出失败',
        content: error instanceof Error ? error.message : '无法生成 .docx 文件',
      });
    } finally {
      setWordExporting(false);
    }
  };

  const requestSave = () => {
    const currentFileName = fileName.trim();
    if (currentFileName && currentFileName !== defaultFileName) {
      const html = editorRef.current?.innerHTML ?? editorHtml;
      onSave(currentFileName, isWord ? html : richTextToMarkdown(html));
      return;
    }
    setSaveFileName('');
    setSaveDialogOpen(true);
  };

  const saveDocument = () => {
    const html = editorRef.current?.innerHTML ?? editorHtml;
    onSave(saveFileName, isWord ? html : richTextToMarkdown(html));
  };

  const handleBack = () => {
    modalApi.confirm({
      title: `是否离开${isWord ? '在线 Word' : '文档'}设计？`,
      content: '离开后将丢弃当前文件及所有尚未保存的内容。',
      okText: '丢弃并离开',
      okButtonProps: { danger: true },
      cancelText: '继续编辑',
      onOk: onBack,
    });
  };

  const focusHeading = (index: number) => {
    const heading = editorRef.current?.querySelectorAll('h1, h2, h3, h4, h5, h6')[index] as
      HTMLElement | undefined;
    heading?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    heading?.focus();
  };

  return (
    <div className="markdown-document-designer">
      {modalContextHolder}
      <header className="markdown-document-designer-header">
        <Button type="text" icon={<ArrowLeft size={18} />} onClick={handleBack}>
          离开
        </Button>
        <span className="markdown-document-designer-mark">
          <FileText size={22} />
        </span>
        <div className="markdown-document-designer-title">
          <Typography.Text strong>{isWord ? '在线 Word' : '文档设计'}</Typography.Text>
          <Input
            variant="borderless"
            value={fileName}
            maxLength={120}
            aria-label={isWord ? '在线 Word 文件名称' : '文档文件名称'}
            suffix={isWord ? '.docx' : '.md'}
            onChange={(event) =>
              setFileName(
                event.target.value.replace(isWord ? /\.(?:doc|docx)$/i : /\.(?:md|markdown)$/i, ''),
              )
            }
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === 's') {
                event.preventDefault();
                requestSave();
              }
            }}
          />
        </div>
        <Tooltip title={showOutline ? '隐藏目录' : '显示目录'}>
          <Button
            type="text"
            aria-label={showOutline ? '隐藏目录' : '显示目录'}
            icon={<PanelLeft size={18} />}
            onClick={() => setShowOutline((current) => !current)}
          />
        </Tooltip>
        <Button
          className="markdown-document-save"
          type="primary"
          icon={<Save size={17} />}
          onClick={requestSave}
        >
          {isWord ? '保存 .docx' : '保存文档'}
        </Button>
      </header>

      <nav className="markdown-designer-menu-tabs" role="tablist" aria-label="文档菜单页">
        <button
          type="button"
          role="tab"
          aria-selected={activeMenu === 'start'}
          className={activeMenu === 'start' ? 'is-active' : ''}
          onClick={() => setActiveMenu('start')}
        >
          开始
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeMenu === 'heading'}
          className={activeMenu === 'heading' ? 'is-active' : ''}
          onClick={() => setActiveMenu('heading')}
        >
          标题
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeMenu === 'paragraph'}
          className={activeMenu === 'paragraph' ? 'is-active' : ''}
          onClick={() => setActiveMenu('paragraph')}
        >
          段落
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeMenu === 'insert'}
          className={activeMenu === 'insert' ? 'is-active' : ''}
          onClick={() => setActiveMenu('insert')}
        >
          插入
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeMenu === 'review'}
          className={activeMenu === 'review' ? 'is-active' : ''}
          onClick={() => setActiveMenu('review')}
        >
          审阅
        </button>
        {isWord && (
          <button
            type="button"
            role="tab"
            aria-selected={activeMenu === 'file'}
            className={activeMenu === 'file' ? 'is-active' : ''}
            onClick={() => setActiveMenu('file')}
          >
            文件
          </button>
        )}
      </nav>

      <div
        className="markdown-document-ribbon"
        role="toolbar"
        aria-label="文档格式工具栏"
        onMouseDown={(event) => {
          if ((event.target as HTMLElement).closest('button')) event.preventDefault();
        }}
      >
        {activeMenu === 'file' ? (
          <>
            {isWord && (
              <div className="markdown-document-tool-group">
                <Tooltip title="打开 .doc 或 .docx 并替换当前内容">
                  <Button
                    className="markdown-document-tool-wide"
                    icon={<FileUp size={18} />}
                    loading={wordImporting}
                    onClick={() => wordInputRef.current?.click()}
                  >
                    导入 Word
                  </Button>
                </Tooltip>
                <input
                  ref={wordInputRef}
                  className="markdown-document-hidden-input"
                  type="file"
                  accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  aria-label="导入 Word 文件"
                  onChange={(event) => {
                    requestWordImport(event.target.files?.[0]);
                    event.target.value = '';
                  }}
                />
                <Tooltip title="导出真正的 Office Open XML .docx 文件">
                  <Button
                    className="markdown-document-tool-wide"
                    icon={<FileDown size={18} />}
                    loading={wordExporting}
                    onClick={() => void downloadWordDocx()}
                  >
                    导出 .docx
                  </Button>
                </Tooltip>
              </div>
            )}
          </>
        ) : activeMenu === 'start' ? (
          <>
            <div className="markdown-document-tool-group">
              <Tooltip title="撤销">
                <Button
                  aria-label="撤销"
                  icon={<Undo2 size={18} />}
                  onClick={() => runCommand('undo')}
                />
              </Tooltip>
              <Tooltip title="重做">
                <Button
                  aria-label="重做"
                  icon={<Redo2 size={18} />}
                  onClick={() => runCommand('redo')}
                />
              </Tooltip>
            </div>
            <div className="markdown-document-tool-group">
              <Dropdown
                trigger={['click']}
                menu={{
                  items: [
                    { key: 'Microsoft YaHei', label: '微软雅黑' },
                    { key: 'SimSun', label: '宋体' },
                    { key: 'SimHei', label: '黑体' },
                    { key: 'Arial', label: 'Arial' },
                    { key: 'Times New Roman', label: 'Times New Roman' },
                  ],
                  onClick: ({ key }) => runCommand('fontName', key),
                }}
              >
                <Button className="markdown-document-tool-wide">字体</Button>
              </Dropdown>
              <Dropdown
                trigger={['click']}
                menu={{
                  items: [
                    { key: '2', label: '小号' },
                    { key: '3', label: '正文' },
                    { key: '4', label: '中号' },
                    { key: '5', label: '大号' },
                    { key: '6', label: '特大号' },
                  ],
                  onClick: ({ key }) => runCommand('fontSize', key),
                }}
              >
                <Button className="markdown-document-tool-wide">字号</Button>
              </Dropdown>
            </div>
            <div className="markdown-document-tool-group">
              <Tooltip title="粗体">
                <Button
                  aria-label="粗体"
                  icon={<Bold size={18} />}
                  onClick={() => runCommand('bold')}
                />
              </Tooltip>
              <Tooltip title="斜体">
                <Button
                  aria-label="斜体"
                  icon={<Italic size={18} />}
                  onClick={() => runCommand('italic')}
                />
              </Tooltip>
              <Tooltip title="删除线">
                <Button
                  aria-label="删除线"
                  icon={<Strikethrough size={18} />}
                  onClick={() => runCommand('strikeThrough')}
                />
              </Tooltip>
              <Tooltip title="行内代码">
                <Button
                  aria-label="行内代码"
                  icon={<Code2 size={18} />}
                  onClick={applyInlineCode}
                />
              </Tooltip>
              <Tooltip title="下划线（HTML 扩展）">
                <Button aria-label="下划线" onClick={() => runCommand('underline')}>
                  U
                </Button>
              </Tooltip>
              <Tooltip title="文本高亮（扩展语法）">
                <Button
                  aria-label="文本高亮"
                  onClick={() => wrapSelectionElement('mark', '高亮文字')}
                >
                  高亮
                </Button>
              </Tooltip>
              <Tooltip title="清除格式">
                <Button
                  aria-label="清除格式"
                  icon={<Eraser size={18} />}
                  onClick={() => runCommand('removeFormat')}
                />
              </Tooltip>
            </div>
          </>
        ) : activeMenu === 'heading' ? (
          <div className="markdown-document-tool-group">
            <Tooltip title="正文（取消标题级别）">
              <Button
                className="markdown-document-tool-wide"
                aria-label="正文"
                onClick={() => runCommand('formatBlock', 'p')}
              >
                正文
              </Button>
            </Tooltip>
            <Tooltip title="一级标题">
              <Button
                aria-label="一级标题"
                icon={<Heading1 size={18} />}
                onClick={() => runCommand('formatBlock', 'h1')}
              />
            </Tooltip>
            <Tooltip title="二级标题">
              <Button
                aria-label="二级标题"
                icon={<Heading2 size={18} />}
                onClick={() => runCommand('formatBlock', 'h2')}
              />
            </Tooltip>
            <Tooltip title="三级标题">
              <Button
                aria-label="三级标题"
                icon={<Heading3 size={18} />}
                onClick={() => runCommand('formatBlock', 'h3')}
              />
            </Tooltip>
            <Tooltip title="四级标题">
              <Button aria-label="四级标题" onClick={() => runCommand('formatBlock', 'h4')}>
                H4
              </Button>
            </Tooltip>
            <Tooltip title="五级标题">
              <Button aria-label="五级标题" onClick={() => runCommand('formatBlock', 'h5')}>
                H5
              </Button>
            </Tooltip>
            <Tooltip title="六级标题">
              <Button aria-label="六级标题" onClick={() => runCommand('formatBlock', 'h6')}>
                H6
              </Button>
            </Tooltip>
          </div>
        ) : activeMenu === 'paragraph' ? (
          <>
            <div className="markdown-document-tool-group">
              <Tooltip title="无序列表">
                <Button
                  aria-label="无序列表"
                  icon={<List size={18} />}
                  onClick={() => runCommand('insertUnorderedList')}
                />
              </Tooltip>
              <Tooltip title="有序列表">
                <Button
                  aria-label="有序列表"
                  icon={<ListOrdered size={18} />}
                  onClick={() => runCommand('insertOrderedList')}
                />
              </Tooltip>
              <Tooltip title="引用">
                <Button
                  aria-label="引用"
                  icon={<Quote size={18} />}
                  onClick={() => runCommand('formatBlock', 'blockquote')}
                />
              </Tooltip>
              <Tooltip title="左对齐">
                <Button
                  aria-label="左对齐"
                  icon={<AlignLeft size={18} />}
                  onClick={() => runCommand('justifyLeft')}
                />
              </Tooltip>
              <Tooltip title="居中">
                <Button
                  aria-label="居中"
                  icon={<AlignCenter size={18} />}
                  onClick={() => runCommand('justifyCenter')}
                />
              </Tooltip>
              <Tooltip title="右对齐">
                <Button
                  aria-label="右对齐"
                  icon={<AlignRight size={18} />}
                  onClick={() => runCommand('justifyRight')}
                />
              </Tooltip>
              <Tooltip title="两端对齐">
                <Button
                  aria-label="两端对齐"
                  icon={<AlignJustify size={18} />}
                  onClick={() => runCommand('justifyFull')}
                />
              </Tooltip>
              <Tooltip title="减少缩进">
                <Button
                  aria-label="减少缩进"
                  icon={<IndentDecrease size={18} />}
                  onClick={() => runCommand('outdent')}
                />
              </Tooltip>
              <Tooltip title="增加缩进">
                <Button
                  aria-label="增加缩进"
                  icon={<IndentIncrease size={18} />}
                  onClick={() => runCommand('indent')}
                />
              </Tooltip>
            </div>
          </>
        ) : activeMenu === 'insert' ? (
          <>
            <div className="markdown-document-tool-group">
              <Tooltip title="链接">
                <Button aria-label="链接" icon={<Link size={18} />} onClick={insertLink} />
              </Tooltip>
              <Tooltip title="插入本地图片">
                <Button
                  aria-label="图片"
                  icon={<Image size={18} />}
                  onClick={() => imageInputRef.current?.click()}
                />
              </Tooltip>
              <input
                ref={imageInputRef}
                className="markdown-document-hidden-input"
                type="file"
                accept="image/*"
                aria-label="选择要插入的图片"
                onChange={(event) => {
                  void insertImageFile(event.target.files?.[0]);
                  event.target.value = '';
                }}
              />
              <Tooltip title="代码块">
                <Button
                  aria-label="代码块"
                  icon={<Code2 size={18} />}
                  onClick={() => insertHtml('<pre><code>代码内容</code></pre><p><br></p>')}
                />
              </Tooltip>
            </div>
            <div className="markdown-document-tool-group">
              <Tooltip title="任务项">
                <Button
                  aria-label="任务项"
                  icon={<ListTodo size={18} />}
                  onClick={() => insertHtml('<p><input type="checkbox" disabled> 待办事项</p>')}
                />
              </Tooltip>
              <Tooltip title="分隔线">
                <Button
                  aria-label="分隔线"
                  icon={<Minus size={18} />}
                  onClick={() => insertHtml('<hr><p><br></p>')}
                />
              </Tooltip>
              <Tooltip title="Markdown 表格">
                <Button
                  aria-label="Markdown 表格"
                  icon={<Table2 size={18} />}
                  onClick={() =>
                    insertHtml(
                      '<table><thead><tr><th>列 1</th><th>列 2</th></tr></thead><tbody><tr><td><br></td><td><br></td></tr></tbody></table><p><br></p>',
                    )
                  }
                />
              </Tooltip>
              <Tooltip title="强制换行">
                <Button aria-label="强制换行" onClick={() => insertHtml('<br>')}>
                  换行
                </Button>
              </Tooltip>
              <Tooltip title="插入当前日期">
                <Button
                  className="markdown-document-tool-wide"
                  aria-label="插入当前日期"
                  icon={<CalendarDays size={18} />}
                  onClick={() => insertHtml(new Intl.DateTimeFormat('zh-CN').format(new Date()))}
                >
                  日期
                </Button>
              </Tooltip>
              <Tooltip title="插入分页符">
                <Button
                  className="markdown-document-tool-wide"
                  aria-label="分页符"
                  onClick={() =>
                    insertHtml(
                      '<div class="word-page-break" style="break-after: page; page-break-after: always;"></div><p><br></p>',
                    )
                  }
                >
                  分页
                </Button>
              </Tooltip>
            </div>
          </>
        ) : (
          <>
            <div className="markdown-document-tool-group">
              <Tooltip title="查找或替换文档内容">
                <Button
                  className="markdown-document-tool-wide"
                  aria-label="查找替换"
                  icon={<Search size={18} />}
                  onClick={() => setFindDialogOpen(true)}
                >
                  查找替换
                </Button>
              </Tooltip>
              <Tooltip title="选择全部文档内容">
                <Button className="markdown-document-tool-wide" onClick={selectAllContent}>
                  全选
                </Button>
              </Tooltip>
              <Tooltip title="清除选中内容的格式">
                <Button
                  className="markdown-document-tool-wide"
                  icon={<Eraser size={18} />}
                  onClick={() => runCommand('removeFormat')}
                >
                  清除格式
                </Button>
              </Tooltip>
            </div>
            <div className="markdown-document-tool-group">
              <Button
                className="markdown-document-tool-wide"
                icon={<Replace size={18} />}
                onClick={() =>
                  modalApi.info({
                    title: '文档统计',
                    content: `当前文档共 ${characterCount} 个字符，目录中包含 ${outline.length} 个标题。`,
                  })
                }
              >
                字数统计
              </Button>
            </div>
          </>
        )}
        <Typography.Text type="secondary">
          {isWord ? '所见即所得 · 在线 Word 富文本' : '所见即所得 · 保存时转换为 Markdown'}
        </Typography.Text>
      </div>

      <div className={`markdown-document-workspace ${showOutline ? '' : 'is-outline-hidden'}`}>
        {showOutline && (
          <aside className="markdown-document-outline">
            <Typography.Text strong>目录</Typography.Text>
            {outline.length ? (
              <nav aria-label="文档目录">
                {outline.map((item) => (
                  <button
                    type="button"
                    style={{ paddingLeft: 10 + (item.level - 1) * 14 }}
                    onClick={() => focusHeading(item.index)}
                    key={`${item.index}-${item.label}`}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            ) : (
              <div className="markdown-document-outline-empty">
                <FileText size={28} />
                <Typography.Text strong>暂无目录</Typography.Text>
                <Typography.Text type="secondary">添加任意级别标题后自动生成</Typography.Text>
              </div>
            )}
          </aside>
        )}

        <main className="markdown-document-canvas">
          <div className="markdown-document-paper">
            <div
              ref={editorRef}
              className="markdown-document-rich-editor"
              contentEditable
              suppressContentEditableWarning
              role="textbox"
              aria-label="文档内容"
              aria-multiline="true"
              data-placeholder="在这里开始编写文档……"
              spellCheck
              onInput={syncEditor}
              onMouseUp={rememberSelection}
              onKeyUp={rememberSelection}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === 's') {
                  event.preventDefault();
                  requestSave();
                }
              }}
            />
          </div>
        </main>
      </div>

      <footer className="markdown-document-statusbar">
        <span>页面：1 / 1</span>
        <span>字符数：{characterCount}</span>
        <Typography.Text type="secondary">
          {isWord ? '在线 Word · 数据库持久化' : '可视化编辑 · 数据库持久化'}
        </Typography.Text>
      </footer>

      <Modal
        title="查找与替换"
        open={findDialogOpen}
        width={480}
        footer={[
          <Button key="cancel" onClick={() => setFindDialogOpen(false)}>
            取消
          </Button>,
          <Button key="find" disabled={!findText.trim()} onClick={selectFirstMatch}>
            查找
          </Button>,
          <Button
            key="replace"
            type="primary"
            disabled={!findText.trim()}
            onClick={replaceAllMatches}
          >
            全部替换
          </Button>,
        ]}
        onCancel={() => setFindDialogOpen(false)}
      >
        <div className="markdown-document-find-form">
          <Input
            autoFocus
            prefix={<Search size={16} />}
            value={findText}
            aria-label="查找内容"
            placeholder="查找内容"
            onChange={(event) => setFindText(event.target.value)}
            onPressEnter={selectFirstMatch}
          />
          <Input
            prefix={<Replace size={16} />}
            value={replaceText}
            aria-label="替换为"
            placeholder="替换为"
            onChange={(event) => setReplaceText(event.target.value)}
          />
        </div>
      </Modal>

      <Modal
        title={isWord ? '保存在线 Word' : '保存文档'}
        open={saveDialogOpen}
        okText="创建文件"
        cancelText="取消"
        okButtonProps={{ disabled: !saveFileName.trim() }}
        onOk={() => {
          setFileName(
            saveFileName.replace(isWord ? /\.(?:doc|docx)$/i : /\.(?:md|markdown)$/i, ''),
          );
          saveDocument();
        }}
        onCancel={() => setSaveDialogOpen(false)}
      >
        <Typography.Paragraph type="secondary">
          {isWord
            ? '请为当前在线 Word 创建一个文件名，系统会自动补充 .docx 后缀。'
            : '请为当前 Markdown 文档创建一个文件名，系统会自动补充 .md 后缀。'}
        </Typography.Paragraph>
        <Input
          autoFocus
          value={saveFileName}
          maxLength={120}
          aria-label="保存文档名称"
          placeholder="例如：项目需求说明"
          onChange={(event) => setSaveFileName(event.target.value)}
          onPressEnter={() => {
            if (!saveFileName.trim()) return;
            setFileName(
              saveFileName.replace(isWord ? /\.(?:doc|docx)$/i : /\.(?:md|markdown)$/i, ''),
            );
            saveDocument();
          }}
        />
      </Modal>
    </div>
  );
}
