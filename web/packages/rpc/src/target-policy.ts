import { InvalidTargetError } from "./errors.js";

export { InvalidTargetError };

const ALLOWED_HOSTNAMES = new Set(["127.0.0.1", "localhost", "[::1]"]);

/**
 * Normalize and validate a loopback RPC target URL.
 *
 * Only `http://127.0.0.1`, `http://localhost`, and `http://[::1]` are accepted.
 * DNS names other than the literal `localhost` are rejected to avoid
 * DNS-rebinding ambiguity — a hostname that resolves to a non-loopback
 * address at resolution time would bypass this check.
 */
export function normalizeLoopbackTarget(raw: string): string {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new InvalidTargetError({ message: "invalid URL" });
  }

  if (url.protocol !== "http:") {
    throw new InvalidTargetError({ message: "only http: protocol is allowed" });
  }

  if (!ALLOWED_HOSTNAMES.has(url.hostname)) {
    throw new InvalidTargetError({
      message: `hostname "${url.hostname}" is not an allowed loopback address`,
    });
  }

  if (url.username !== "" || url.password !== "") {
    throw new InvalidTargetError({ message: "credentials in URL are not allowed" });
  }

  if (url.port === "") {
    throw new InvalidTargetError({ message: "explicit port is required" });
  }

  const port = Number(url.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new InvalidTargetError({
      message: `port ${url.port} is outside valid range 1..65535`,
    });
  }

  if (url.search !== "") {
    throw new InvalidTargetError({ message: "query string is not allowed" });
  }

  if (url.hash !== "") {
    throw new InvalidTargetError({ message: "fragment is not allowed" });
  }

  return url.toString();
}
