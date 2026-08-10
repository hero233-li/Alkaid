export function sanitizeWordHtml(value: string) {
  const parsed = new DOMParser().parseFromString(value, 'text/html');
  parsed.querySelectorAll('script, style, iframe, object, embed, link, meta').forEach((node) => {
    node.remove();
  });
  parsed.querySelectorAll<HTMLElement>('*').forEach((element) => {
    Array.from(element.attributes).forEach((attribute) => {
      const name = attribute.name.toLocaleLowerCase();
      const content = attribute.value.trim().toLocaleLowerCase();
      if (name.startsWith('on')) element.removeAttribute(attribute.name);
      if (name === 'style' && attribute.value) {
        const safeDeclarations = attribute.value
          .split(';')
          .map((item) => item.trim())
          .filter(Boolean)
          .filter((item) => {
            const property = item.split(':', 1)[0]?.trim().toLocaleLowerCase();
            return ![
              'position',
              'left',
              'right',
              'top',
              'bottom',
              'width',
              'min-width',
              'max-width',
              'height',
              'min-height',
              'max-height',
              'margin-left',
              'margin-right',
              'transform',
              'float',
              'overflow',
              'overflow-x',
              'overflow-y',
            ].includes(property);
          });
        if (safeDeclarations.length) element.setAttribute('style', safeDeclarations.join('; '));
        else element.removeAttribute('style');
      }
      if (
        (name === 'href' || name === 'src') &&
        !content.startsWith('https://') &&
        !content.startsWith('http://') &&
        !content.startsWith('data:image/') &&
        !content.startsWith('/api/documents/assets/') &&
        !content.startsWith('#')
      ) {
        element.removeAttribute(attribute.name);
      }
      if (
        (name === 'width' || name === 'height') &&
        ['TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD', 'COL', 'COLGROUP'].includes(element.tagName)
      ) {
        element.removeAttribute(attribute.name);
      }
    });
  });
  return parsed.body.innerHTML;
}
