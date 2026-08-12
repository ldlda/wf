/** Parses an explicit comma-separated browser-origin allowlist. */
export const parseTrustedOrigins = (raw: string | undefined): ReadonlySet<string> => {
  if (raw === undefined || raw.trim() === "") return new Set();
  const origins = new Set<string>();
  for (const entry of raw.split(",")) {
    const value = entry.trim();
    if (value === "") continue;
    let parsed: URL;
    try {
      parsed = new URL(value);
    } catch {
      throw new Error(`Invalid trusted origin: ${value}`);
    }
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.pathname !== "/" ||
      parsed.search !== "" ||
      parsed.hash !== "" ||
      parsed.username !== "" ||
      parsed.password !== ""
    ) {
      throw new Error(`Invalid trusted origin: ${value}`);
    }
    origins.add(parsed.origin);
  }
  return origins;
};
