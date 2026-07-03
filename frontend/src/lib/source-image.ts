export function getSourceDomain(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function getSourceImageUrl(url: string): string | null {
  const domain = getSourceDomain(url);
  if (!domain) return null;
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=128`;
}

export function getSourceFallbackLetter(source: { url: string; title?: string | null }): string {
  const title = source.title?.trim();
  if (title) {
    const letter = title.match(/\p{L}/u)?.[0];
    if (letter) return letter.toUpperCase();
  }

  const domain = getSourceDomain(source.url);
  if (domain) return domain.charAt(0).toUpperCase();

  return "?";
}
