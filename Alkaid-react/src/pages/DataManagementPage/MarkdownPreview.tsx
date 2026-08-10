import { markdownToRichTextHtml } from './documentMarkdown';
import {
  parseMultidimensionalTable,
  parseSpreadsheetWorkbook,
  type MarkdownDocumentKind,
} from './model';
import { evaluateGridCell } from './tableFormula';
import { sanitizeWordHtml } from './wordDocument';

interface MarkdownPreviewProps {
  content: string;
  kind?: MarkdownDocumentKind;
}

export default function MarkdownPreview({ content, kind = 'document' }: MarkdownPreviewProps) {
  if (kind === 'word') {
    return (
      <article
        className="markdown-rendered-preview data-management-word-preview"
        aria-label="在线 Word 渲染预览"
        dangerouslySetInnerHTML={{
          __html: sanitizeWordHtml(content) || '<p class="is-empty">该文件暂无内容</p>',
        }}
      />
    );
  }
  if (kind === 'spreadsheet') {
    const workbook = parseSpreadsheetWorkbook(content);
    const sheet = workbook.sheets.find((item) => item.id === workbook.activeSheetId)!;
    let lastRow = -1;
    let lastColumn = -1;
    sheet.cells.forEach((row, rowIndex) =>
      row.forEach((cell, columnIndex) => {
        if (cell.trim()) {
          lastRow = Math.max(lastRow, rowIndex);
          lastColumn = Math.max(lastColumn, columnIndex);
        }
      }),
    );
    return (
      <article className="markdown-rendered-preview" aria-label="在线表格渲染预览">
        <h1>{sheet.name}</h1>
        {lastRow >= 0 && lastColumn >= 0 ? (
          <table className="spreadsheet-preview-table">
            <colgroup>
              {Array.from({ length: lastColumn + 1 }, (_, column) => (
                <col key={column} style={{ width: sheet.columnWidths[column] }} />
              ))}
            </colgroup>
            <tbody>
              {Array.from({ length: lastRow + 1 }, (_, row) => (
                <tr key={row} style={{ height: sheet.rowHeights[row] }}>
                  {Array.from({ length: lastColumn + 1 }, (_, column) => {
                    const merge = sheet.merges.find(
                      (item) =>
                        row >= item.startRow &&
                        row <= item.endRow &&
                        column >= item.startColumn &&
                        column <= item.endColumn,
                    );
                    if (merge && (merge.startRow !== row || merge.startColumn !== column))
                      return null;
                    const style = sheet.styles[`${row}:${column}`] || {};
                    return (
                      <td
                        key={column}
                        colSpan={merge ? merge.endColumn - merge.startColumn + 1 : undefined}
                        rowSpan={merge ? merge.endRow - merge.startRow + 1 : undefined}
                        style={{
                          textAlign: style.horizontal,
                          fontWeight: style.bold ? 700 : undefined,
                          whiteSpace: style.wrap ? 'normal' : undefined,
                        }}
                      >
                        {evaluateGridCell(sheet.cells, row, column).value}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="is-empty">该工作表暂无内容</p>
        )}
      </article>
    );
  }

  if (kind === 'multidimensional-table') {
    const data = parseMultidimensionalTable(content);
    const title = /^#\s+(.+)$/m.exec(content)?.[1];
    return (
      <article className="markdown-rendered-preview" aria-label="多维表格渲染预览">
        {title && <h1>{title}</h1>}
        <table className="multidimensional-preview-table">
          <colgroup>
            {data.fields.map((field) => (
              <col key={field.id} style={{ width: field.width || 180 }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {data.fields.map((field) => (
                <th key={field.id}>
                  {field.name}
                  <small>{field.type}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.records.map((record, rowIndex) => (
              <tr key={rowIndex}>
                {data.fields.map((field, columnIndex) => (
                  <td key={field.id}>
                    {field.type === 'rating' && record[columnIndex]
                      ? '★'.repeat(Number(record[columnIndex]) || 0)
                      : record[columnIndex] || ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    );
  }

  return (
    <article
      className="markdown-rendered-preview"
      aria-label="Markdown 渲染预览"
      dangerouslySetInnerHTML={{
        __html: markdownToRichTextHtml(content) || '<p class="is-empty">该文件暂无内容</p>',
      }}
    />
  );
}
