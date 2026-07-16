export async function recallResponseError(response: Response, fallback: string) {
  if (response.status === 403) {
    return "You do not have permission to perform this recall action.";
  }
  if (response.status === 404) {
    return "This recall or patient record is no longer available.";
  }
  if (response.status === 409) {
    return "This recall state changed before the request completed. Refresh and try again.";
  }
  if (response.status === 413) {
    try {
      const payload = (await response.clone().json()) as { detail?: unknown };
      const detail = typeof payload.detail === "string" ? payload.detail : "";
      const count = detail.match(/^Too many recalls to export \((\d+)\)\./)?.[1];
      return count
        ? `Too many recalls to export (${count}). Narrow your filters.`
        : "Too many recalls to export. Narrow your filters.";
    } catch {
      return "Too many recalls to export. Narrow your filters.";
    }
  }
  if (response.status === 422) {
    try {
      const payload = (await response.clone().json()) as { detail?: unknown };
      if (payload.detail === "No recalls match your filters.") {
        return "No recalls match your filters.";
      }
    } catch {
      // Validation responses are intentionally reduced to a fixed safe message.
    }
    return "Please check the recall details or filters and try again.";
  }
  return fallback;
}

export function sanitizeRecallFilename(value: string, fallback: string, maxLength = 120) {
  let cleaned = value.replace(/[\x00-\x1f\x7f]+/g, "");
  cleaned = cleaned.replace(/[<>:"/\\|?*]+/g, "_");
  cleaned = cleaned.replace(/\s+/g, "_").trim();
  cleaned = cleaned.replace(/[^a-zA-Z0-9._-]+/g, "_");
  cleaned = cleaned.replace(/_+/g, "_").replace(/^_+|_+$/g, "");
  if (!cleaned) cleaned = fallback;
  if (cleaned.length <= maxLength) return cleaned;
  const match = cleaned.match(/(\.[a-zA-Z0-9]{1,10})$/);
  if (!match) return cleaned.slice(0, maxLength);
  const extension = match[1];
  const baseLength = maxLength - extension.length;
  if (baseLength <= 0) return cleaned.slice(0, maxLength);
  const base = cleaned.slice(0, -extension.length);
  return baseLength > 3
    ? `${base.slice(0, baseLength - 3)}...${extension}`
    : `${base.slice(0, baseLength)}${extension}`;
}
