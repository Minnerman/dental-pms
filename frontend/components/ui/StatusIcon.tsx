type AppointmentStatus =
  | "booked"
  | "arrived"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "no_show";

const statusMap: Record<AppointmentStatus, { icon: string; label: string }> = {
  booked: { icon: "📅", label: "Booked" },
  arrived: { icon: "✅", label: "Arrived" },
  in_progress: { icon: "⏱️", label: "In progress" },
  completed: { icon: "✔️", label: "Completed" },
  cancelled: { icon: "✖️", label: "Cancelled" },
  no_show: { icon: "⚠️", label: "No show" },
};

export default function StatusIcon({ status }: { status: AppointmentStatus }) {
  const mapped = statusMap[status];
  return (
    <span className="status-icon" title={mapped.label}>
      {mapped.icon}
    </span>
  );
}
