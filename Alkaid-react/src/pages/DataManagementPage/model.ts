export const MARKDOWN_RECENT_STORAGE_KEY = 'alioth:data-management:recent-markdown:v1';
export const MARKDOWN_WORKSPACE_STORAGE_KEY = 'alioth:data-management:workspace:v2';
export const MARKDOWN_WORKSPACE_CHANGED_EVENT = 'alioth:markdown-workspace-changed';
export const MARKDOWN_CREATE_REQUESTED_EVENT = 'alioth:markdown-create-requested';
export const MARKDOWN_EDIT_REQUESTED_EVENT = 'alioth:markdown-edit-requested';
export const MARKDOWN_CREATE_REQUEST_KEY = 'alioth:data-management:create-requested';
export const MARKDOWN_EDIT_REQUEST_KEY = 'alioth:data-management:edit-requested';
export const MAX_MARKDOWN_FILE_SIZE = 128 * 1024 * 1024;
export const MAX_RECENT_MARKDOWN_FILES = 12;

export type MarkdownDocumentSource = 'created' | 'opened';
export type MarkdownDocumentKind = 'document' | 'word' | 'multidimensional-table' | 'spreadsheet';

export interface MarkdownDocumentRecord {
  id: string;
  name: string;
  content: string;
  size: number;
  kind: MarkdownDocumentKind;
  source: MarkdownDocumentSource;
  locked?: boolean;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
  lastOpenedAt: string;
}

export interface MarkdownFolderRecord {
  id: string;
  name: string;
  parentId: string | null;
  createdAt: string;
}

export interface MarkdownWorkspace {
  documents: MarkdownDocumentRecord[];
  folders: MarkdownFolderRecord[];
}

export type MarkdownTableGrid = string[][];

export type MultidimensionalFieldType =
  | 'text'
  | 'richText'
  | 'number'
  | 'date'
  | 'time'
  | 'select'
  | 'multiSelect'
  | 'attachment'
  | 'rating'
  | 'checkbox'
  | 'percentage'
  | 'currency'
  | 'progress'
  | 'hyperlink'
  | 'phone'
  | 'email'
  | 'idCard'
  | 'address'
  | 'barcode';

export interface MultidimensionalField {
  id: string;
  name: string;
  type: MultidimensionalFieldType;
  width?: number;
  options?: string[];
}

export interface MultidimensionalTableView {
  id: string;
  name: string;
  query: string;
  filters: MultidimensionalViewFilter[];
  sort?: {
    fieldId: string;
    direction: 'ascending' | 'descending';
  };
  wrapText: boolean;
}

export interface MultidimensionalViewFilter {
  fieldId: string;
  operator: 'contains' | 'equals' | 'notEmpty';
  value: string;
}

export interface MultidimensionalTableData {
  tableName: string;
  fields: MultidimensionalField[];
  records: string[][];
  views: MultidimensionalTableView[];
  activeViewId: string;
}

export type SpreadsheetHorizontalAlignment = 'left' | 'center' | 'right';
export type SpreadsheetVerticalAlignment = 'top' | 'middle' | 'bottom';
export type SpreadsheetNumberFormat = 'general' | 'number' | 'percent' | 'currency';

export interface SpreadsheetCellStyle {
  horizontal?: SpreadsheetHorizontalAlignment;
  vertical?: SpreadsheetVerticalAlignment;
  wrap?: boolean;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
  fontFamily?: string;
  fontSize?: number;
  textColor?: string;
  fillColor?: string;
  border?: boolean;
  indent?: number;
  numberFormat?: SpreadsheetNumberFormat;
  decimalPlaces?: number;
}

export interface SpreadsheetMergeRange {
  startRow: number;
  startColumn: number;
  endRow: number;
  endColumn: number;
}

export type SpreadsheetValidationType = 'list' | 'wholeNumber' | 'decimal' | 'date' | 'textLength';

export interface SpreadsheetDataValidation {
  type: SpreadsheetValidationType;
  allowBlank: boolean;
  options?: string[];
  minimum?: number;
  maximum?: number;
}

export interface SpreadsheetSheet {
  id: string;
  name: string;
  rowCount: number;
  columnCount: number;
  cells: string[][];
  styles: Record<string, SpreadsheetCellStyle>;
  merges: SpreadsheetMergeRange[];
  columnWidths: number[];
  rowHeights: number[];
  freezeRows: number;
  freezeColumns: number;
  filters: Record<string, string>;
  validations: Record<string, SpreadsheetDataValidation>;
}

export interface SpreadsheetWorkbook {
  format: 'alioth-spreadsheet';
  version: 1;
  activeSheetId: string;
  sheets: SpreadsheetSheet[];
}

const MULTIDIMENSIONAL_TABLE_MARKER = 'alioth:multidimensional-table:v1:';

export function requestMarkdownCreation(storage: Storage = window.sessionStorage) {
  storage.removeItem(MARKDOWN_EDIT_REQUEST_KEY);
  storage.setItem(MARKDOWN_CREATE_REQUEST_KEY, '1');
  window.dispatchEvent(new Event(MARKDOWN_CREATE_REQUESTED_EVENT));
}

export function consumeMarkdownCreationRequest(storage: Storage = window.sessionStorage) {
  const requested = storage.getItem(MARKDOWN_CREATE_REQUEST_KEY) === '1';
  if (requested) storage.removeItem(MARKDOWN_CREATE_REQUEST_KEY);
  return requested;
}

export function requestMarkdownEdit(documentId: string, storage: Storage = window.sessionStorage) {
  storage.setItem(MARKDOWN_EDIT_REQUEST_KEY, documentId);
  window.dispatchEvent(new Event(MARKDOWN_EDIT_REQUESTED_EVENT));
}

export function peekMarkdownEditRequest(storage: Storage = window.sessionStorage) {
  return storage.getItem(MARKDOWN_EDIT_REQUEST_KEY);
}

export function clearMarkdownEditRequest(
  expectedDocumentId?: string,
  storage: Storage = window.sessionStorage,
) {
  if (expectedDocumentId && storage.getItem(MARKDOWN_EDIT_REQUEST_KEY) !== expectedDocumentId) {
    return;
  }
  storage.removeItem(MARKDOWN_EDIT_REQUEST_KEY);
}

export function consumeMarkdownEditRequest(storage: Storage = window.sessionStorage) {
  const documentId = peekMarkdownEditRequest(storage);
  if (documentId) clearMarkdownEditRequest(documentId, storage);
  return documentId;
}

function isMarkdownDocumentRecord(value: unknown) {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<MarkdownDocumentRecord>;
  const storedKind = (item as { kind?: unknown }).kind;
  return (
    typeof item.id === 'string' &&
    typeof item.name === 'string' &&
    typeof item.content === 'string' &&
    typeof item.size === 'number' &&
    (storedKind === undefined ||
      storedKind === 'document' ||
      storedKind === 'word' ||
      storedKind === 'table' ||
      storedKind === 'multidimensional-table' ||
      storedKind === 'spreadsheet') &&
    (item.source === 'created' || item.source === 'opened') &&
    (item.locked === undefined || typeof item.locked === 'boolean') &&
    (item.folderId === undefined || item.folderId === null || typeof item.folderId === 'string') &&
    typeof item.createdAt === 'string' &&
    typeof item.updatedAt === 'string' &&
    typeof item.lastOpenedAt === 'string'
  );
}

function isMarkdownFolderRecord(value: unknown): value is MarkdownFolderRecord {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<MarkdownFolderRecord>;
  return (
    typeof item.id === 'string' &&
    typeof item.name === 'string' &&
    (item.parentId === null || typeof item.parentId === 'string') &&
    typeof item.createdAt === 'string'
  );
}

function normalizeWorkspace(workspace: MarkdownWorkspace): MarkdownWorkspace {
  const folders = workspace.folders.filter(isMarkdownFolderRecord);
  const folderIds = new Set(folders.map((folder) => folder.id));
  return {
    folders: folders.map((folder) => ({
      ...folder,
      parentId:
        folder.parentId && folder.parentId !== folder.id && folderIds.has(folder.parentId)
          ? folder.parentId
          : null,
    })),
    documents: workspace.documents
      .filter(isMarkdownDocumentRecord)
      .map((document) => ({
        ...document,
        kind:
          (document as unknown as { kind?: string }).kind === 'table'
            ? 'document'
            : document.kind || inferMarkdownDocumentKind(document.content),
        locked: Boolean(document.locked),
        folderId: document.folderId && folderIds.has(document.folderId) ? document.folderId : null,
      }))
      .sort((left, right) => right.lastOpenedAt.localeCompare(left.lastOpenedAt)),
  };
}

export function normalizeMarkdownFileName(value: string) {
  const cleaned = value
    .trim()
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/[.\s]+$/g, '')
    .trim();
  const baseName = cleaned || '未命名文档';
  return /\.(?:md|markdown)$/i.test(baseName) ? baseName : `${baseName}.md`;
}

export function normalizeSpreadsheetFileName(value: string) {
  const cleaned = value
    .trim()
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/[.\s]+$/g, '')
    .trim();
  const baseName = cleaned || '未命名在线表格';
  return /\.sheet\.json$/i.test(baseName) ? baseName : `${baseName}.sheet.json`;
}

export function normalizeWordFileName(value: string) {
  const cleaned = value
    .trim()
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/[.\s]+$/g, '')
    .trim();
  const baseName = (cleaned || '未命名在线 Word').replace(/\.(?:doc|docx)$/i, '');
  return `${baseName}.docx`;
}

export function normalizeMarkdownFolderName(value: string) {
  return (
    value
      .trim()
      .replace(/[\\/:*?"<>|]/g, '-')
      .replace(/[.\s]+$/g, '')
      .trim() || '未命名文件夹'
  );
}

export function getMarkdownTitle(fileName: string) {
  return fileName.replace(/\.(?:md|markdown)$/i, '');
}

export function getMarkdownDocumentKindLabel(kind: MarkdownDocumentKind) {
  if (kind === 'word') return '在线 Word';
  if (kind === 'multidimensional-table') return '多维表格';
  if (kind === 'spreadsheet') return '在线表格';
  return '文档';
}

export function inferMarkdownDocumentKind(content: string): MarkdownDocumentKind {
  try {
    const parsed = JSON.parse(content) as Partial<SpreadsheetWorkbook>;
    if (parsed.format === 'alioth-spreadsheet' && Array.isArray(parsed.sheets)) {
      return 'spreadsheet';
    }
  } catch {
    // 非 JSON 内容继续按 Markdown 类型识别。
  }
  if (content.includes(`<!-- ${MULTIDIMENSIONAL_TABLE_MARKER}`)) {
    return 'multidimensional-table';
  }
  return 'document';
}

function escapeMarkdownTableCell(value: string) {
  return value.trim().replace(/\r?\n/g, '<br>').replace(/\|/g, '\\|');
}

export function serializeMarkdownTable(fileName: string, grid: MarkdownTableGrid) {
  let lastUsedRow = -1;
  let lastUsedColumn = -1;
  grid.forEach((row, rowIndex) => {
    row.forEach((cell, columnIndex) => {
      if (cell.trim()) {
        lastUsedRow = Math.max(lastUsedRow, rowIndex);
        lastUsedColumn = Math.max(lastUsedColumn, columnIndex);
      }
    });
  });

  const columnCount = Math.max(3, lastUsedColumn + 1);
  const rowCount = Math.max(2, lastUsedRow + 1);
  const header = Array.from({ length: columnCount }, (_, columnIndex) => {
    const value = escapeMarkdownTableCell(grid[0]?.[columnIndex] || '');
    return value || `列 ${columnIndex + 1}`;
  });
  const body = Array.from({ length: rowCount - 1 }, (_, bodyRowIndex) =>
    Array.from({ length: columnCount }, (_, columnIndex) =>
      escapeMarkdownTableCell(grid[bodyRowIndex + 1]?.[columnIndex] || ''),
    ),
  );
  const markdownRows = [
    `| ${header.join(' | ')} |`,
    `| ${header.map(() => '---').join(' | ')} |`,
    ...body.map((row) => `| ${row.join(' | ')} |`),
  ];
  return `# ${getMarkdownTitle(normalizeMarkdownFileName(fileName))}\n\n${markdownRows.join('\n')}\n`;
}

export function createDefaultMultidimensionalTableData(): MultidimensionalTableData {
  return {
    tableName: '数据表',
    fields: [
      { id: 'field-text', name: '文本', type: 'text' },
      { id: 'field-number', name: '数字', type: 'number' },
      { id: 'field-date', name: '日期', type: 'date' },
      {
        id: 'field-select',
        name: '单选',
        type: 'select',
        options: ['未开始', '进行中', '已完成'],
      },
      { id: 'field-attachment', name: '图片和附件', type: 'attachment' },
      { id: 'field-rating', name: '评分', type: 'rating' },
    ],
    records: Array.from({ length: 5 }, () => Array.from({ length: 6 }, () => '')),
    views: [{ id: 'view-1', name: '表格视图', query: '', filters: [], wrapText: false }],
    activeViewId: 'view-1',
  };
}

export function createDefaultSpreadsheetWorkbook(
  rowCount = 30,
  columnCount = 12,
): SpreadsheetWorkbook {
  const sheetId = 'sheet-1';
  return {
    format: 'alioth-spreadsheet',
    version: 1,
    activeSheetId: sheetId,
    sheets: [
      {
        id: sheetId,
        name: '工作表 1',
        rowCount,
        columnCount,
        cells: Array.from({ length: rowCount }, () =>
          Array.from({ length: columnCount }, () => ''),
        ),
        styles: {},
        merges: [],
        columnWidths: Array.from({ length: columnCount }, () => 112),
        rowHeights: Array.from({ length: rowCount }, () => 32),
        freezeRows: 0,
        freezeColumns: 0,
        filters: {},
        validations: {},
      },
    ],
  };
}

export function serializeSpreadsheetWorkbook(workbook: SpreadsheetWorkbook) {
  return JSON.stringify(workbook, null, 2);
}

export function parseSpreadsheetWorkbook(content: string): SpreadsheetWorkbook {
  try {
    const parsed = JSON.parse(content) as Partial<SpreadsheetWorkbook>;
    if (
      parsed.format === 'alioth-spreadsheet' &&
      parsed.version === 1 &&
      typeof parsed.activeSheetId === 'string' &&
      Array.isArray(parsed.sheets) &&
      parsed.sheets.length
    ) {
      const workbook = parsed as SpreadsheetWorkbook;
      return {
        ...workbook,
        sheets: workbook.sheets.map((sheet) => ({
          ...sheet,
          columnWidths: Array.from({ length: sheet.columnCount }, (_, index) =>
            Math.max(56, Math.min(480, sheet.columnWidths?.[index] || 112)),
          ),
          rowHeights: Array.from({ length: sheet.rowCount }, (_, index) =>
            Math.max(24, Math.min(240, sheet.rowHeights?.[index] || 32)),
          ),
          freezeRows: Math.max(0, Math.min(sheet.rowCount, sheet.freezeRows || 0)),
          freezeColumns: Math.max(0, Math.min(sheet.columnCount, sheet.freezeColumns || 0)),
          filters: sheet.filters || {},
          validations: sheet.validations || {},
        })),
      };
    }
  } catch {
    // 损坏或非工作簿文件会返回一个安全的空工作簿。
  }
  return createDefaultSpreadsheetWorkbook();
}

export function validateSpreadsheetCellValue(
  value: string,
  validation?: SpreadsheetDataValidation,
) {
  if (!validation || (!value.trim() && validation.allowBlank)) return true;
  if (validation.type === 'list') return (validation.options || []).includes(value);
  if (validation.type === 'date') return !Number.isNaN(Date.parse(value));
  if (validation.type === 'textLength') {
    return (
      value.length >= (validation.minimum ?? 0) &&
      value.length <= (validation.maximum ?? Number.POSITIVE_INFINITY)
    );
  }
  const numeric = Number(value);
  if (!value.trim() || !Number.isFinite(numeric)) return false;
  if (validation.type === 'wholeNumber' && !Number.isInteger(numeric)) return false;
  return (
    numeric >= (validation.minimum ?? Number.NEGATIVE_INFINITY) &&
    numeric <= (validation.maximum ?? Number.POSITIVE_INFINITY)
  );
}

export function serializeMultidimensionalTable(fileName: string, data: MultidimensionalTableData) {
  const normalizedFields = data.fields.map((field) => ({
    ...field,
    name: field.name.trim() || '未命名字段',
    width: typeof field.width === 'number' ? Math.min(480, Math.max(100, field.width)) : undefined,
    options:
      field.type === 'select' || field.type === 'multiSelect'
        ? field.options?.filter(Boolean) || []
        : undefined,
  }));
  const normalizedViews = data.views.length
    ? data.views.map((view, index) => ({
        id: view.id || `view-${index + 1}`,
        name: view.name.trim() || `表格视图 (${index + 1})`,
        query: view.query || '',
        filters: view.filters || [],
        sort: view.sort,
        wrapText: Boolean(view.wrapText),
      }))
    : [{ id: 'view-1', name: '表格视图', query: '', filters: [], wrapText: false }];
  const activeViewId = normalizedViews.some((view) => view.id === data.activeViewId)
    ? data.activeViewId
    : normalizedViews[0].id;
  const metadata = encodeURIComponent(
    JSON.stringify({
      tableName: data.tableName.trim() || '数据表',
      fields: normalizedFields,
      views: normalizedViews,
      activeViewId,
    }),
  );
  const grid: MarkdownTableGrid = [
    normalizedFields.map((field) => field.name),
    ...data.records.map((record) => normalizedFields.map((_, index) => record[index] || '')),
  ];
  return `<!-- ${MULTIDIMENSIONAL_TABLE_MARKER}${metadata} -->\n${serializeMarkdownTable(fileName, grid)}`;
}

export function parseMultidimensionalTable(content: string): MultidimensionalTableData {
  const metadataPattern = new RegExp(
    `<!--\\s*${MULTIDIMENSIONAL_TABLE_MARKER.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}([^\\s]+)\\s*-->`,
  );
  const metadata = metadataPattern.exec(content)?.[1];
  const grid = parseMarkdownTable(content);
  let fields: MultidimensionalField[] = [];
  let tableName = '数据表';
  let views: MultidimensionalTableView[] = [];
  let activeViewId = '';
  if (metadata) {
    try {
      const parsed: unknown = JSON.parse(decodeURIComponent(metadata));
      const parsedFields = Array.isArray(parsed)
        ? parsed
        : parsed &&
            typeof parsed === 'object' &&
            Array.isArray((parsed as { fields?: unknown }).fields)
          ? (parsed as { fields: unknown[] }).fields
          : [];
      fields = parsedFields
        .filter(
          (field): field is MultidimensionalField =>
            Boolean(field) &&
            typeof field === 'object' &&
            typeof (field as MultidimensionalField).id === 'string' &&
            typeof (field as MultidimensionalField).name === 'string' &&
            [
              'text',
              'richText',
              'number',
              'date',
              'time',
              'select',
              'multiSelect',
              'attachment',
              'rating',
              'checkbox',
              'percentage',
              'currency',
              'progress',
              'hyperlink',
              'phone',
              'email',
              'idCard',
              'address',
              'barcode',
            ].includes((field as MultidimensionalField).type),
        )
        .map((field) => ({
          ...field,
          width:
            typeof field.width === 'number' ? Math.min(480, Math.max(100, field.width)) : undefined,
        }));
      if (parsed && !Array.isArray(parsed) && typeof parsed === 'object') {
        const configuration = parsed as {
          tableName?: unknown;
          views?: unknown;
          activeViewId?: unknown;
        };
        if (typeof configuration.tableName === 'string' && configuration.tableName.trim()) {
          tableName = configuration.tableName.trim();
        }
        if (Array.isArray(configuration.views)) {
          views = configuration.views.flatMap((view) => {
            if (
              !view ||
              typeof view !== 'object' ||
              typeof (view as MultidimensionalTableView).id !== 'string' ||
              typeof (view as MultidimensionalTableView).name !== 'string'
            ) {
              return [];
            }
            const candidate = view as Partial<MultidimensionalTableView>;
            const filters = Array.isArray(candidate.filters)
              ? candidate.filters.filter(
                  (filter): filter is MultidimensionalViewFilter =>
                    Boolean(filter) &&
                    typeof filter.fieldId === 'string' &&
                    ['contains', 'equals', 'notEmpty'].includes(filter.operator) &&
                    typeof filter.value === 'string',
                )
              : [];
            const sort =
              candidate.sort &&
              typeof candidate.sort.fieldId === 'string' &&
              ['ascending', 'descending'].includes(candidate.sort.direction)
                ? candidate.sort
                : undefined;
            return [
              {
                id: candidate.id!,
                name: candidate.name!,
                query: typeof candidate.query === 'string' ? candidate.query : '',
                filters,
                sort,
                wrapText: Boolean(candidate.wrapText),
              },
            ];
          });
        }
        if (typeof configuration.activeViewId === 'string') {
          activeViewId = configuration.activeViewId;
        }
      }
    } catch {
      fields = [];
    }
  }
  if (!fields.length && grid[0]?.length) {
    fields = grid[0].map((name, index) => ({
      id: `field-${index + 1}`,
      name: name || `字段 ${index + 1}`,
      type: 'text',
    }));
  }
  const fallback = createDefaultMultidimensionalTableData();
  const resolvedFields = fields.length ? fields : fallback.fields;
  const sourceRecords = grid.length > 1 ? grid.slice(1) : fallback.records;
  const resolvedViews = views.length ? views : fallback.views;
  return {
    tableName,
    fields: resolvedFields,
    records: sourceRecords.map((record) => resolvedFields.map((_, index) => record[index] || '')),
    views: resolvedViews,
    activeViewId: resolvedViews.some((view) => view.id === activeViewId)
      ? activeViewId
      : resolvedViews[0].id,
  };
}

function parseMarkdownTableRow(line: string) {
  const value = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  const cells: string[] = [];
  let current = '';
  let escaped = false;
  for (const character of value) {
    if (escaped) {
      current += character;
      escaped = false;
    } else if (character === '\\') {
      escaped = true;
    } else if (character === '|') {
      cells.push(current.trim().replace(/<br\s*\/?>/gi, '\n'));
      current = '';
    } else {
      current += character;
    }
  }
  cells.push(current.trim().replace(/<br\s*\/?>/gi, '\n'));
  return cells;
}

export function parseMarkdownTable(content: string): MarkdownTableGrid {
  const lines = content.split(/\r?\n/);
  const separatorPattern = /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/;
  const separatorIndex = lines.findIndex(
    (line, index) => index > 0 && separatorPattern.test(line) && lines[index - 1].includes('|'),
  );
  if (separatorIndex < 1) return [];

  const rows = [parseMarkdownTableRow(lines[separatorIndex - 1])];
  for (let index = separatorIndex + 1; index < lines.length; index += 1) {
    if (!lines[index].includes('|')) break;
    rows.push(parseMarkdownTableRow(lines[index]));
  }
  return rows;
}

export function createUniqueMarkdownFileName(fileName: string, existingNames: string[]) {
  const normalized = normalizeMarkdownFileName(fileName);
  const occupied = new Set(existingNames.map((name) => name.toLocaleLowerCase()));
  if (!occupied.has(normalized.toLocaleLowerCase())) return normalized;

  const extension = normalized.toLocaleLowerCase().endsWith('.markdown') ? '.markdown' : '.md';
  const baseName = normalized.slice(0, -extension.length);
  let suffix = 2;
  while (occupied.has(`${baseName} (${suffix})${extension}`.toLocaleLowerCase())) suffix += 1;
  return `${baseName} (${suffix})${extension}`;
}

export function createUniqueSpreadsheetFileName(fileName: string, existingNames: string[]) {
  const normalized = normalizeSpreadsheetFileName(fileName);
  const occupied = new Set(existingNames.map((name) => name.toLocaleLowerCase()));
  if (!occupied.has(normalized.toLocaleLowerCase())) return normalized;
  const baseName = normalized.slice(0, -'.sheet.json'.length);
  let suffix = 2;
  while (occupied.has(`${baseName} (${suffix}).sheet.json`.toLocaleLowerCase())) suffix += 1;
  return `${baseName} (${suffix}).sheet.json`;
}

export function createUniqueWordFileName(fileName: string, existingNames: string[]) {
  const normalized = normalizeWordFileName(fileName);
  const occupied = new Set(existingNames.map((name) => name.toLocaleLowerCase()));
  if (!occupied.has(normalized.toLocaleLowerCase())) return normalized;
  const baseName = normalized.slice(0, -'.docx'.length);
  let suffix = 2;
  while (occupied.has(`${baseName} (${suffix}).docx`.toLocaleLowerCase())) suffix += 1;
  return `${baseName} (${suffix}).docx`;
}

export function createUniqueMarkdownFolderName(folderName: string, siblingNames: string[]) {
  const normalized = normalizeMarkdownFolderName(folderName);
  const occupied = new Set(siblingNames.map((name) => name.toLocaleLowerCase()));
  if (!occupied.has(normalized.toLocaleLowerCase())) return normalized;

  let suffix = 2;
  while (occupied.has(`${normalized} (${suffix})`.toLocaleLowerCase())) suffix += 1;
  return `${normalized} (${suffix})`;
}

function createRecordId(prefix: 'markdown' | 'folder') {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function createMarkdownDocument(
  name: string,
  kindOrNow: MarkdownDocumentKind | Date = 'document',
  now = new Date(),
): MarkdownDocumentRecord {
  const kind = kindOrNow instanceof Date ? 'document' : kindOrNow;
  const createdAt = kindOrNow instanceof Date ? kindOrNow : now;
  const normalizedName = normalizeMarkdownFileName(name);
  const timestamp = createdAt.toISOString();
  const title = getMarkdownTitle(normalizedName);
  const content =
    kind === 'multidimensional-table'
      ? serializeMultidimensionalTable(normalizedName, createDefaultMultidimensionalTableData())
      : `# ${title}\n\n在这里开始编写文档内容。\n`;
  return {
    id: createRecordId('markdown'),
    name: normalizedName,
    content,
    size: new Blob([content]).size,
    kind,
    source: 'created',
    locked: false,
    folderId: null,
    createdAt: timestamp,
    updatedAt: timestamp,
    lastOpenedAt: timestamp,
  };
}

export function createMultidimensionalTableDocument(
  name: string,
  data: MultidimensionalTableData,
  now = new Date(),
): MarkdownDocumentRecord {
  const document = createMarkdownDocument(name, 'multidimensional-table', now);
  const content = serializeMultidimensionalTable(document.name, data);
  return { ...document, content, size: new Blob([content]).size };
}

export function createSpreadsheetDocument(
  name: string,
  workbook: SpreadsheetWorkbook,
  now = new Date(),
): MarkdownDocumentRecord {
  const timestamp = now.toISOString();
  const content = serializeSpreadsheetWorkbook(workbook);
  return {
    id: createRecordId('markdown'),
    name: normalizeSpreadsheetFileName(name),
    content,
    size: new Blob([content]).size,
    kind: 'spreadsheet',
    source: 'created',
    locked: false,
    folderId: null,
    createdAt: timestamp,
    updatedAt: timestamp,
    lastOpenedAt: timestamp,
  };
}

export function createWordDocument(
  name: string,
  html: string,
  source: MarkdownDocumentSource = 'created',
  now = new Date(),
): MarkdownDocumentRecord {
  const timestamp = now.toISOString();
  const content = html.trim() || '<p><br></p>';
  return {
    id: createRecordId('markdown'),
    name: normalizeWordFileName(name),
    content,
    size: new Blob([content]).size,
    kind: 'word',
    source,
    locked: false,
    folderId: null,
    createdAt: timestamp,
    updatedAt: timestamp,
    lastOpenedAt: timestamp,
  };
}

export function createMarkdownContentDocument(
  name: string,
  value: string,
  now = new Date(),
): MarkdownDocumentRecord {
  const document = createMarkdownDocument(name, 'document', now);
  const trimmedContent = value.trimEnd();
  const content = trimmedContent
    ? `${trimmedContent}\n`
    : `# ${getMarkdownTitle(document.name)}\n\n`;
  return { ...document, content, size: new Blob([content]).size };
}

export function createOpenedMarkdownDocument(
  file: Pick<File, 'name' | 'size' | 'lastModified'>,
  content: string,
  now = new Date(),
): MarkdownDocumentRecord {
  const timestamp = now.toISOString();
  return {
    id: createRecordId('markdown'),
    name:
      inferMarkdownDocumentKind(content) === 'spreadsheet'
        ? normalizeSpreadsheetFileName(file.name)
        : normalizeMarkdownFileName(file.name),
    content,
    size: file.size,
    kind: inferMarkdownDocumentKind(content),
    source: 'opened',
    locked: false,
    folderId: null,
    createdAt: timestamp,
    updatedAt: file.lastModified ? new Date(file.lastModified).toISOString() : timestamp,
    lastOpenedAt: timestamp,
  };
}

export function createMarkdownFolder(
  name: string,
  parentId: string | null,
  now = new Date(),
): MarkdownFolderRecord {
  return {
    id: createRecordId('folder'),
    name: normalizeMarkdownFolderName(name),
    parentId,
    createdAt: now.toISOString(),
  };
}

export function upsertRecentMarkdownDocument(
  records: MarkdownDocumentRecord[],
  document: MarkdownDocumentRecord,
) {
  const existing = records.find(
    (item) => item.name.toLocaleLowerCase() === document.name.toLocaleLowerCase(),
  );
  const nextDocument = existing
    ? {
        ...document,
        id: existing.id,
        folderId: existing.folderId,
        createdAt: existing.createdAt,
      }
    : document;
  return [
    nextDocument,
    ...records.filter((item) => item.id !== existing?.id && item.id !== document.id),
  ].sort((left, right) => right.lastOpenedAt.localeCompare(left.lastOpenedAt));
}

function parseStoredWorkspace(value: string | null): MarkdownWorkspace | null {
  if (!value) return null;
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== 'object') return null;
  const workspace = parsed as Partial<MarkdownWorkspace>;
  if (!Array.isArray(workspace.documents) || !Array.isArray(workspace.folders)) return null;
  return normalizeWorkspace({ documents: workspace.documents, folders: workspace.folders });
}

function parseLegacyDocuments(value: string | null): MarkdownDocumentRecord[] {
  if (!value) return [];
  const parsed: unknown = JSON.parse(value);
  if (!Array.isArray(parsed)) return [];
  return parsed.filter(isMarkdownDocumentRecord).map((document) => ({
    ...document,
    kind: document.kind || inferMarkdownDocumentKind(document.content),
    folderId: document.folderId || null,
  }));
}

export function loadMarkdownWorkspace(storage: Storage = window.localStorage): MarkdownWorkspace {
  try {
    const workspace = parseStoredWorkspace(storage.getItem(MARKDOWN_WORKSPACE_STORAGE_KEY));
    if (workspace) return workspace;
    return normalizeWorkspace({
      documents: parseLegacyDocuments(storage.getItem(MARKDOWN_RECENT_STORAGE_KEY)),
      folders: [],
    });
  } catch {
    return { documents: [], folders: [] };
  }
}

export function saveMarkdownWorkspace(
  workspace: MarkdownWorkspace,
  storage: Storage = window.localStorage,
) {
  try {
    const normalized = normalizeWorkspace(workspace);
    // localStorage is only an index. Large document bodies are loaded from MySQL on demand.
    const metadataOnly = {
      ...normalized,
      documents: normalized.documents.map((document) => ({ ...document, content: '' })),
    };
    storage.setItem(MARKDOWN_WORKSPACE_STORAGE_KEY, JSON.stringify(metadataOnly));
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event(MARKDOWN_WORKSPACE_CHANGED_EVENT));
    }
    return true;
  } catch {
    return false;
  }
}

export function loadRecentMarkdownDocuments(storage: Storage = window.localStorage) {
  return loadMarkdownWorkspace(storage).documents;
}

export function saveRecentMarkdownDocuments(
  records: MarkdownDocumentRecord[],
  storage: Storage = window.localStorage,
) {
  const workspace = loadMarkdownWorkspace(storage);
  return saveMarkdownWorkspace({ ...workspace, documents: records }, storage);
}

export function moveMarkdownDocument(
  workspace: MarkdownWorkspace,
  documentId: string,
  folderId: string | null,
): MarkdownWorkspace {
  const validFolderId =
    folderId && workspace.folders.some((folder) => folder.id === folderId) ? folderId : null;
  return {
    ...workspace,
    documents: workspace.documents.map((document) =>
      document.id === documentId ? { ...document, folderId: validFolderId } : document,
    ),
  };
}

export function getMarkdownFolderPath(folderId: string | null, folders: MarkdownFolderRecord[]) {
  if (!folderId) return '未分类';
  const folderMap = new Map(folders.map((folder) => [folder.id, folder]));
  const names: string[] = [];
  const visited = new Set<string>();
  let currentId: string | null = folderId;
  while (currentId && !visited.has(currentId)) {
    visited.add(currentId);
    const folder = folderMap.get(currentId);
    if (!folder) break;
    names.unshift(folder.name);
    currentId = folder.parentId;
  }
  return names.length ? names.join(' / ') : '未分类';
}

export function isMarkdownFileName(fileName: string) {
  return /\.(?:md|markdown)$/i.test(fileName.trim());
}

export function isSupportedDataFileName(fileName: string) {
  return isMarkdownFileName(fileName) || /\.sheet\.json$/i.test(fileName.trim());
}

export function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  return `${(size / 1024).toFixed(size < 10 * 1024 ? 1 : 0)} KB`;
}
