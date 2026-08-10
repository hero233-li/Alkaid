import { beforeEach, describe, expect, it } from 'vitest';
import {
  MARKDOWN_RECENT_STORAGE_KEY,
  MARKDOWN_WORKSPACE_STORAGE_KEY,
  clearMarkdownEditRequest,
  consumeMarkdownEditRequest,
  createDefaultMultidimensionalTableData,
  createMarkdownDocument,
  createMarkdownContentDocument,
  createMarkdownFolder,
  createMultidimensionalTableDocument,
  createDefaultSpreadsheetWorkbook,
  createSpreadsheetDocument,
  createUniqueMarkdownFileName,
  createUniqueMarkdownFolderName,
  createUniqueWordFileName,
  createWordDocument,
  getMarkdownFolderPath,
  inferMarkdownDocumentKind,
  isMarkdownFileName,
  loadMarkdownWorkspace,
  loadRecentMarkdownDocuments,
  moveMarkdownDocument,
  saveMarkdownWorkspace,
  normalizeMarkdownFileName,
  normalizeWordFileName,
  parseMarkdownTable,
  parseMultidimensionalTable,
  parseSpreadsheetWorkbook,
  peekMarkdownEditRequest,
  requestMarkdownEdit,
  saveRecentMarkdownDocuments,
  serializeMarkdownTable,
  serializeMultidimensionalTable,
  serializeSpreadsheetWorkbook,
  upsertRecentMarkdownDocument,
  validateSpreadsheetCellValue,
} from './model';

describe('data management markdown model', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it('passes a requested document id to the editor exactly once', () => {
    requestMarkdownEdit('document-1');

    expect(peekMarkdownEditRequest()).toBe('document-1');
    clearMarkdownEditRequest('another-document');
    expect(peekMarkdownEditRequest()).toBe('document-1');
    expect(consumeMarkdownEditRequest()).toBe('document-1');
    expect(consumeMarkdownEditRequest()).toBeNull();
  });

  it('normalizes markdown file names and removes unsafe path characters', () => {
    expect(normalizeMarkdownFileName('  需求/说明  ')).toBe('需求-说明.md');
    expect(normalizeMarkdownFileName('README.markdown')).toBe('README.markdown');
    expect(isMarkdownFileName('notes.MD')).toBe(true);
    expect(isMarkdownFileName('notes.txt')).toBe(false);
  });

  it('creates a unique markdown name when a recent file already exists', () => {
    expect(createUniqueMarkdownFileName('需求', ['需求.md', '需求 (2).md'])).toBe('需求 (3).md');
  });

  it('creates a database-backed online Word document with a Word-compatible name', () => {
    const document = createWordDocument(
      '项目方案.docx',
      '<h1>项目方案</h1><p>正文</p>',
      'opened',
      new Date('2026-08-02T08:00:00Z'),
    );

    expect(normalizeWordFileName('项目/方案.doc')).toBe('项目-方案.docx');
    expect(createUniqueWordFileName('项目方案', ['项目方案.docx'])).toBe('项目方案 (2).docx');
    expect(document.name).toBe('项目方案.docx');
    expect(document.kind).toBe('word');
    expect(document.source).toBe('opened');
    expect(document.content).toContain('<h1>项目方案</h1>');
  });

  it('treats Markdown tables as document content now that the legacy table type is removed', () => {
    const document = createMarkdownDocument('说明', 'document', new Date('2026-08-02T08:00:00Z'));
    const markdownTable = '# 数据\n\n| 名称 | 数量 |\n| --- | --- |\n| 示例 | 1 |\n';

    expect(document.kind).toBe('document');
    expect(document.content).toContain('在这里开始编写文档内容');
    expect(inferMarkdownDocumentKind(markdownTable)).toBe('document');
    expect(inferMarkdownDocumentKind('# 普通文档\n\n正文')).toBe('document');
  });

  it('serializes a compact Markdown table for document and multidimensional content', () => {
    const grid = [
      ['姓名', '部门', '说明'],
      ['张三', '研发', '包含 | 符号'],
      ['', '', ''],
    ];
    const content = serializeMarkdownTable('人员清单', grid);

    expect(content).toContain('# 人员清单');
    expect(content).toContain('| 姓名 | 部门 | 说明 |');
    expect(content).toContain('| 张三 | 研发 | 包含 \\| 符号 |');
    expect(content).not.toContain('|  |  |  |\n|  |  |  |');
  });

  it('restores a saved Markdown table for editing', () => {
    expect(
      parseMarkdownTable('# 清单\n\n| 名称 | 备注 |\n| --- | --- |\n| 产品 | 含\\|符号 |\n'),
    ).toEqual([
      ['名称', '备注'],
      ['产品', '含|符号'],
    ]);
  });

  it('preserves multidimensional field types in a valid Markdown table', () => {
    const data = {
      tableName: '项目数据表',
      fields: [
        { id: 'name', name: '名称', type: 'text' as const },
        { id: 'status', name: '状态', type: 'select' as const, options: ['进行中', '完成'] },
        { id: 'score', name: '评分', type: 'rating' as const },
      ],
      records: [['需求评审', '进行中', '4']],
      views: [
        { id: 'view-all', name: '全部需求', query: '', filters: [], wrapText: false },
        {
          id: 'view-reviewing',
          name: '评审中',
          query: '评审',
          filters: [{ fieldId: 'status', operator: 'equals' as const, value: '进行中' }],
          sort: { fieldId: 'score', direction: 'descending' as const },
          wrapText: true,
        },
      ],
      activeViewId: 'view-reviewing',
    };
    const content = serializeMultidimensionalTable('项目数据', data);
    const document = createMultidimensionalTableDocument(
      '项目数据',
      data,
      new Date('2026-08-02T08:00:00Z'),
    );

    expect(content).toContain('<!-- alioth:multidimensional-table:v1:');
    expect(content).toContain('| 名称 | 状态 | 评分 |');
    expect(inferMarkdownDocumentKind(content)).toBe('multidimensional-table');
    expect(parseMultidimensionalTable(content)).toEqual(data);
    expect(document.kind).toBe('multidimensional-table');
    expect(document.content).toBe(content);
  });

  it('persists an independently resized multidimensional field width', () => {
    const data = createDefaultMultidimensionalTableData();
    data.fields[0].width = 286;

    const restored = parseMultidimensionalTable(serializeMultidimensionalTable('列宽测试', data));

    expect(restored.fields[0].width).toBe(286);
    expect(restored.fields[1].width).toBeUndefined();
  });

  it('upgrades legacy multidimensional tables to one linked table view', () => {
    const legacyFields = encodeURIComponent(
      JSON.stringify([
        { id: 'name', name: '名称', type: 'text' },
        { id: 'status', name: '状态', type: 'text' },
      ]),
    );
    const content = `<!-- alioth:multidimensional-table:v1:${legacyFields} -->\n# 旧数据\n\n| 名称 | 状态 |\n| --- | --- |\n| 示例 | 正常 |\n`;
    const restored = parseMultidimensionalTable(content);

    expect(restored.tableName).toBe('数据表');
    expect(restored.views).toEqual([
      { id: 'view-1', name: '表格视图', query: '', filters: [], wrapText: false },
    ]);
    expect(restored.activeViewId).toBe('view-1');
    expect(restored.records[0]).toEqual(['示例', '正常']);
  });

  it('stores online spreadsheet structure as a versioned JSON workbook', () => {
    const workbook = createDefaultSpreadsheetWorkbook(3, 3);
    workbook.sheets[0].cells[0][0] = '10';
    workbook.sheets[0].cells[0][1] = '=A1*2';
    workbook.sheets[0].styles['0:1'] = {
      horizontal: 'center',
      vertical: 'middle',
      bold: true,
      italic: true,
      underline: true,
      fontFamily: 'Microsoft YaHei',
      fontSize: 16,
      textColor: '#ffffff',
      fillColor: '#2563eb',
      border: true,
      indent: 1,
      numberFormat: 'currency',
      decimalPlaces: 2,
    };
    workbook.sheets[0].columnWidths[0] = 180;
    workbook.sheets[0].rowHeights[0] = 48;
    workbook.sheets[0].freezeRows = 1;
    workbook.sheets[0].freezeColumns = 1;
    workbook.sheets[0].filters['0'] = '华东';
    workbook.sheets[0].validations['1:1'] = {
      type: 'list',
      allowBlank: true,
      options: ['通过', '拒绝'],
    };
    workbook.sheets[0].merges.push({
      startRow: 1,
      startColumn: 0,
      endRow: 1,
      endColumn: 2,
    });
    const content = serializeSpreadsheetWorkbook(workbook);
    const document = createSpreadsheetDocument(
      '预算表',
      workbook,
      new Date('2026-08-02T08:00:00Z'),
    );

    expect(document.name).toBe('预算表.sheet.json');
    expect(document.kind).toBe('spreadsheet');
    expect(inferMarkdownDocumentKind(content)).toBe('spreadsheet');
    expect(parseSpreadsheetWorkbook(content)).toEqual(workbook);
    expect(document.content).toBe(content);
  });

  it('supplies safe layout defaults when opening a legacy spreadsheet', () => {
    const workbook = createDefaultSpreadsheetWorkbook(2, 2);
    const legacySheet = { ...workbook.sheets[0] } as Partial<(typeof workbook.sheets)[number]>;
    delete legacySheet.columnWidths;
    delete legacySheet.rowHeights;
    delete legacySheet.freezeRows;
    delete legacySheet.freezeColumns;
    delete legacySheet.filters;
    delete legacySheet.validations;
    const restored = parseSpreadsheetWorkbook(
      JSON.stringify({ ...workbook, sheets: [legacySheet] }),
    );

    expect(restored.sheets[0].columnWidths).toEqual([112, 112]);
    expect(restored.sheets[0].rowHeights).toEqual([32, 32]);
    expect(restored.sheets[0].freezeRows).toBe(0);
    expect(restored.sheets[0].freezeColumns).toBe(0);
    expect(restored.sheets[0].filters).toEqual({});
    expect(restored.sheets[0].validations).toEqual({});
  });

  it('validates spreadsheet list, number, date and text length rules', () => {
    expect(
      validateSpreadsheetCellValue('完成', {
        type: 'list',
        allowBlank: false,
        options: ['待办', '完成'],
      }),
    ).toBe(true);
    expect(
      validateSpreadsheetCellValue('其他', {
        type: 'list',
        allowBlank: false,
        options: ['待办', '完成'],
      }),
    ).toBe(false);
    expect(
      validateSpreadsheetCellValue('12', {
        type: 'wholeNumber',
        allowBlank: false,
        minimum: 10,
        maximum: 20,
      }),
    ).toBe(true);
    expect(validateSpreadsheetCellValue('2026-08-02', { type: 'date', allowBlank: false })).toBe(
      true,
    );
    expect(
      validateSpreadsheetCellValue('abcd', {
        type: 'textLength',
        allowBlank: false,
        maximum: 3,
      }),
    ).toBe(false);
  });

  it('creates a designed document from editor content and supplies a title when empty', () => {
    const designed = createMarkdownContentDocument(
      '项目方案',
      '# 项目方案\n\n正文内容',
      new Date('2026-08-02T08:00:00Z'),
    );
    const empty = createMarkdownContentDocument('空白文档', '', new Date('2026-08-02T08:00:00Z'));

    expect(designed.kind).toBe('document');
    expect(designed.content).toBe('# 项目方案\n\n正文内容\n');
    expect(designed.size).toBe(new Blob([designed.content]).size);
    expect(empty.content).toBe('# 空白文档\n\n');
  });

  it('persists recent Documents and replaces a reopened file with the same name', () => {
    const first = createMarkdownDocument('设计说明', new Date('2026-08-01T08:00:00.000Z'));
    const reopened = {
      ...createMarkdownDocument('设计说明', new Date('2026-08-02T08:00:00.000Z')),
      content: '# 新内容\n',
    };
    const records = upsertRecentMarkdownDocument([first], reopened);

    expect(records).toHaveLength(1);
    expect(records[0].id).toBe(first.id);
    expect(records[0].content).toBe('# 新内容\n');
    expect(saveRecentMarkdownDocuments(records)).toBe(true);
    expect(loadRecentMarkdownDocuments()).toEqual([{ ...records[0], content: '' }]);
    expect(window.localStorage.getItem(MARKDOWN_WORKSPACE_STORAGE_KEY)).toBeTruthy();
  });

  it('migrates legacy recent files into the root document library', () => {
    const legacyDocument = createMarkdownDocument('旧文档', new Date('2026-08-01T08:00:00.000Z'));
    window.localStorage.setItem(
      MARKDOWN_RECENT_STORAGE_KEY,
      JSON.stringify([{ ...legacyDocument, kind: undefined, folderId: undefined }]),
    );

    const workspace = loadMarkdownWorkspace();

    expect(workspace.documents).toHaveLength(1);
    expect(workspace.documents[0].folderId).toBeNull();
    expect(workspace.documents[0].kind).toBe('document');
    expect(workspace.folders).toEqual([]);
  });

  it('creates nested folders and moves Documents into them', () => {
    const projectFolder = createMarkdownFolder(
      '项目资料',
      null,
      new Date('2026-08-02T08:00:00.000Z'),
    );
    const childFolder = createMarkdownFolder(
      '需求',
      projectFolder.id,
      new Date('2026-08-02T09:00:00.000Z'),
    );
    const document = createMarkdownDocument('需求说明');
    const workspace = moveMarkdownDocument(
      { documents: [document], folders: [projectFolder, childFolder] },
      document.id,
      childFolder.id,
    );

    expect(workspace.documents[0].folderId).toBe(childFolder.id);
    expect(getMarkdownFolderPath(childFolder.id, workspace.folders)).toBe('项目资料 / 需求');
    expect(createUniqueMarkdownFolderName('需求', ['需求', '需求 (2)'])).toBe('需求 (3)');
    expect(saveMarkdownWorkspace(workspace)).toBe(true);
    expect(loadMarkdownWorkspace()).toEqual({
      ...workspace,
      documents: workspace.documents.map((document) => ({ ...document, content: '' })),
    });
  });
});
