export async function patientMutationError(response: Response, fallback: string) {
  if (response.status === 403) {
    return "You do not have permission to change patient records.";
  }
  if (response.status === 404) {
    return "This patient record is no longer available.";
  }
  if (response.status === 409) {
    return "This patient record changed before the request completed. Refresh and try again.";
  }
  if (response.status === 422) {
    return "Please check the patient details and try again.";
  }
  return fallback;
}
