const normalizeMarkdown = (value: string) =>
  value
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

const nodeToMarkdown = (node: Node): string => {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? '';
  if (!(node instanceof HTMLElement)) return '';

  const children = () => Array.from(node.childNodes).map(nodeToMarkdown).join('');
  const tag = node.tagName.toLowerCase();

  if (/^h[1-6]$/.test(tag)) return `${'#'.repeat(Number(tag[1]))} ${children().trim()}\n\n`;
  if (tag === 'strong' || tag === 'b') return `**${children()}**`;
  if (tag === 'em' || tag === 'i') return `*${children()}*`;
  if (tag === 's' || tag === 'strike' || tag === 'del') return `~~${children()}~~`;
  if (node.hasAttribute('data-inline-math')) return `$${node.getAttribute('data-inline-math')}$`;
  if (node.hasAttribute('data-block-math'))
    return `\n$$\n${node.getAttribute('data-block-math')}\n$$\n\n`;
  if (node.hasAttribute('data-footnote-ref')) return `[^${node.getAttribute('data-footnote-ref')}]`;
  if (node.hasAttribute('data-footnote-definition')) {
    return `[^${node.getAttribute('data-footnote-definition')}]: ${children().trim()}\n\n`;
  }
  if (tag === 'u' || tag === 'sup' || tag === 'sub' || tag === 'kbd') {
    return `<${tag}>${children()}</${tag}>`;
  }
  if (tag === 'mark') return `==${children()}==`;
  if (tag === 'code' && node.parentElement?.tagName.toLowerCase() !== 'pre') {
    return `\`${children()}\``;
  }
  if (tag === 'pre') {
    return `\n\`\`\`${node.getAttribute('data-language') || 'text'}\n${node.textContent ?? ''}\n\`\`\`\n\n`;
  }
  if (tag === 'blockquote') {
    return `${children()
      .trim()
      .split('\n')
      .map((line) => `> ${line}`)
      .join('\n')}\n\n`;
  }
  if (tag === 'a')
    return `[${children() || node.getAttribute('href') || '链接'}](${node.getAttribute('href') || ''})`;
  if (tag === 'img')
    return `![${node.getAttribute('alt') || '图片'}](${node.getAttribute('src') || ''})`;
  if (tag === 'hr') return '\n---\n\n';
  if (tag === 'br') return '\n';
  if (tag === 'ul' || tag === 'ol') {
    return `${Array.from(node.children)
      .map((item, index) => {
        const marker = tag === 'ol' ? `${index + 1}.` : '-';
        return `${marker} ${nodeToMarkdown(item).trim()}`;
      })
      .join('\n')}\n\n`;
  }
  if (tag === 'li') return children();
  if (tag === 'table') {
    const rows = Array.from(node.querySelectorAll('tr')).map((row) =>
      Array.from(row.querySelectorAll('th, td')).map((cell) => (cell.textContent ?? '').trim()),
    );
    if (!rows.length) return '';
    const width = Math.max(...rows.map((row) => row.length));
    const line = (cells: string[]) =>
      `| ${Array.from({ length: width }, (_, index) => cells[index] ?? '').join(' | ')} |`;
    return `${line(rows[0])}\n${line(Array.from({ length: width }, () => '---'))}\n${rows
      .slice(1)
      .map(line)
      .join('\n')}\n\n`;
  }
  if (tag === 'input' && node.getAttribute('type') === 'checkbox') {
    return node.hasAttribute('checked') ? '[x] ' : '[ ] ';
  }
  if (tag === 'p' || tag === 'div') return `${children()}\n\n`;
  return children();
};

export const richTextToMarkdown = (html: string) => {
  const documentRoot = new DOMParser().parseFromString(`<main>${html}</main>`, 'text/html');
  return normalizeMarkdown(nodeToMarkdown(documentRoot.body.firstElementChild as HTMLElement));
};

const escapeHtml = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const inlineMarkdownToHtml = (value: string) =>
  escapeHtml(value)
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/~~([^~]+)~~/g, '<s>$1</s>')
    .replace(/==([^=]+)==/g, '<mark>$1</mark>')
    .replace(/\$([^$]+)\$/g, '<span class="markdown-rich-math" data-inline-math="$1">$1</span>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>');

const markdownTableCells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split(/(?<!\\)\|/)
    .map((cell) => cell.trim().replace(/\\\|/g, '|'));

export const markdownToRichTextHtml = (markdown: string) => {
  const lines = markdown.replace(/\r/g, '').split('\n');
  const blocks: string[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) continue;
    if (
      line.includes('|') &&
      /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1] || '')
    ) {
      const header = markdownTableCells(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].includes('|')) {
        rows.push(markdownTableCells(lines[index]));
        index += 1;
      }
      index -= 1;
      blocks.push(
        `<table><thead><tr>${header.map((cell) => `<th>${inlineMarkdownToHtml(cell)}</th>`).join('')}</tr></thead><tbody>${rows
          .map(
            (row) =>
              `<tr>${header.map((_, cellIndex) => `<td>${inlineMarkdownToHtml(row[cellIndex] || '')}</td>`).join('')}</tr>`,
          )
          .join('')}</tbody></table>`,
      );
      continue;
    }
    if (line.startsWith('```')) {
      const language = escapeHtml(line.slice(3).trim() || 'text');
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) {
        code.push(lines[index]);
        index += 1;
      }
      blocks.push(
        `<pre data-language="${language}"><code>${escapeHtml(code.join('\n'))}</code></pre>`,
      );
      continue;
    }
    if (line.trim() === '$$') {
      const formula: string[] = [];
      index += 1;
      while (index < lines.length && lines[index].trim() !== '$$') {
        formula.push(lines[index]);
        index += 1;
      }
      const value = escapeHtml(formula.join('\n'));
      blocks.push(
        `<div class="markdown-rich-math is-block" data-block-math="${value}">${value}</div>`,
      );
      continue;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      blocks.push(
        `<h${heading[1].length}>${inlineMarkdownToHtml(heading[2])}</h${heading[1].length}>`,
      );
      continue;
    }
    if (/^\s*---+\s*$/.test(line)) {
      blocks.push('<hr>');
      continue;
    }
    if (/^>\s?/.test(line)) {
      blocks.push(`<blockquote>${inlineMarkdownToHtml(line.replace(/^>\s?/, ''))}</blockquote>`);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index])) {
        items.push(`<li>${inlineMarkdownToHtml(lines[index].replace(/^[-*]\s+/, ''))}</li>`);
        index += 1;
      }
      index -= 1;
      blocks.push(`<ul>${items.join('')}</ul>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        items.push(`<li>${inlineMarkdownToHtml(lines[index].replace(/^\d+\.\s+/, ''))}</li>`);
        index += 1;
      }
      index -= 1;
      blocks.push(`<ol>${items.join('')}</ol>`);
      continue;
    }
    blocks.push(`<p>${inlineMarkdownToHtml(line)}</p>`);
  }
  return blocks.join('');
};
