export const NOTE_BODY_MAX_LENGTH = 2_000;

export async function noteResponseError(response: Response, fallback: string) {
  if (response.status === 403) {
    return "You do not have permission to perform this note action.";
  }
  if (response.status === 404) {
    return "This note or its related record is no longer available.";
  }
  if (response.status === 409) {
    return "This note changed before the request completed. Refresh and try again.";
  }
  if (response.status === 422) {
    return "Please check the note details and try again.";
  }
  return fallback;
}
