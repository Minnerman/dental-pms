type AppointmentStatus =
  | "booked"
  | "arrived"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "no_show";

export default function StatusIcon({ status }: { status: AppointmentStatus }) {
  return (
    <span className="status-icon" data-status={status} aria-hidden="true" />
  );
}
