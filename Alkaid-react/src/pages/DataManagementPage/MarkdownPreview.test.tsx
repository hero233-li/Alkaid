import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import MarkdownPreview from './MarkdownPreview';
import { createDefaultSpreadsheetWorkbook, serializeSpreadsheetWorkbook } from './model';

describe('online spreadsheet preview', () => {
  it('renders only the used data cells without editor row and column coordinates', () => {
    const workbook = createDefaultSpreadsheetWorkbook();
    workbook.sheets[0].cells[0][0] = '地区';
    workbook.sheets[0].cells[1][0] = '华东';

    const html = renderToStaticMarkup(
      <MarkdownPreview content={serializeSpreadsheetWorkbook(workbook)} kind="spreadsheet" />,
    );

    expect(html).toContain('<td>地区</td>');
    expect(html).toContain('<td>华东</td>');
    expect(html).not.toContain('<th');
    expect(html.match(/<tr/g)).toHaveLength(2);
  });

  it('shows an empty state instead of a blank coordinate grid', () => {
    const workbook = createDefaultSpreadsheetWorkbook();
    const html = renderToStaticMarkup(
      <MarkdownPreview content={serializeSpreadsheetWorkbook(workbook)} kind="spreadsheet" />,
    );

    expect(html).toContain('该工作表暂无内容');
    expect(html).not.toContain('<table');
  });
});

describe('document image preview', () => {
  it('renders uploaded document assets in Markdown and online Word', () => {
    const assetUrl = '/api/documents/assets/12345678-1234-1234-1234-123456789abc';
    const markdown = renderToStaticMarkup(
      <MarkdownPreview content={`![示例图片](${assetUrl})`} kind="document" />,
    );
    const word = renderToStaticMarkup(
      <MarkdownPreview content={`<p><img src="${assetUrl}" alt="示例图片"></p>`} kind="word" />,
    );

    expect(markdown).toContain(`src="${assetUrl}"`);
    expect(word).toContain(`src="${assetUrl}"`);
  });
});
