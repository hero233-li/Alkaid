import { describe, expect, it } from 'vitest';
import { sanitizeWordHtml } from './wordDocument';

describe('online Word html', () => {
  it('removes executable markup while preserving rich text', () => {
    const html = sanitizeWordHtml(
      '<h1 onclick="alert(1)">标题</h1><script>alert(1)</script><p><b>正文</b></p>',
    );

    expect(html).toContain('<h1>标题</h1>');
    expect(html).toContain('<b>正文</b>');
    expect(html).not.toContain('onclick');
    expect(html).not.toContain('<script');
  });

  it('removes imported Word layout constraints that break preview and editing', () => {
    const html = sanitizeWordHtml(
      '<table width="1800" style="width:1800px; margin-left:640px; color:#123"><tr><td width="320" style="min-width:320px; font-weight:bold">内容</td></tr></table>',
    );

    expect(html).not.toContain('width="');
    expect(html).not.toContain('width:');
    expect(html).not.toContain('margin-left');
    expect(html).toContain('color:#123');
    expect(html).toContain('font-weight:bold');
  });
});
