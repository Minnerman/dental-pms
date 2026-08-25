export async function safeDocumentError(
  response: Response,
  fallback: string
): Promise<string> {
  if (response.status === 403) {
    return "You do not have permission to perform this document action.";
  }
  if (response.status === 404) {
    return "This patient document is no longer available.";
  }
  if (response.status === 409) {
    return "The document changed before this action completed. Refresh and try again.";
  }
  if (response.status === 413) {
    return "The selected file is too large. Choose a file no larger than 10 MB.";
  }
  if (response.status === 400 || response.status === 422) {
    return "Check the document details and try again.";
  }
  if (response.status >= 500) {
    return "The document service is temporarily unavailable. Try again later.";
  }
  return fallback;
}
