import { describe, expect, it } from 'vitest';
import { markdownToRichTextHtml, richTextToMarkdown } from './documentMarkdown';

describe('richTextToMarkdown', () => {
  it('converts visible document formatting into Markdown when saving', () => {
    expect(
      richTextToMarkdown(
        '<h1>实际标题</h1><p><strong>重点</strong>和<em>说明</em></p><ul><li>第一项</li><li>第二项</li></ul>',
      ),
    ).toBe('# 实际标题\n\n**重点**和*说明*\n\n- 第一项\n- 第二项');
  });

  it('converts a visible table into a Markdown table', () => {
    expect(
      richTextToMarkdown(
        '<table><thead><tr><th>名称</th><th>状态</th></tr></thead><tbody><tr><td>任务</td><td>完成</td></tr></tbody></table>',
      ),
    ).toBe('| 名称 | 状态 |\n| --- | --- |\n| 任务 | 完成 |');
  });

  it('restores Markdown as visible rich text for editing', () => {
    expect(markdownToRichTextHtml('# 标题\n\n正文包含 **重点**')).toBe(
      '<h1>标题</h1><p>正文包含 <strong>重点</strong></p>',
    );
  });

  it('preserves tutorial advanced syntax when saving rich content', () => {
    expect(
      richTextToMarkdown(
        '<h4>细分标题</h4><p><mark>重点</mark> <u>下划线</u> <sup>2</sup></p><span data-inline-math="E = mc^2">E = mc²</span><pre data-language="mermaid"><code>flowchart LR</code></pre>',
      ),
    ).toContain('#### 细分标题\n\n==重点== <u>下划线</u> <sup>2</sup>');
    expect(
      richTextToMarkdown(
        '<span data-inline-math="E = mc^2">E = mc²</span><pre data-language="mermaid"><code>flowchart LR</code></pre>',
      ),
    ).toBe('$E = mc^2$\n```mermaid\nflowchart LR\n```');
  });
});
