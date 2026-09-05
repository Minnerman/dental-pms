export type Availability = "available" | "forbidden" | "unavailable";
export type AppointmentPeriod = { appointments: number; completed: number; completion_rate: number | null };
export type DashboardHome = {
  generated_at: string; date: string; timezone: string; currency: string;
  periods: {
    current_start: string; current_end: string; previous_start: string; previous_end: string;
    week_start: string; week_end: string; month_start: string; month_end: string;
  };
  appointments: {
    availability: Availability; today_count: number | null; in_clinic_count: number | null;
    schedule_availability: Availability;
    schedule: Array<{
      id: number; patient_id: number | null; patient_name: string | null;
      starts_at: string; ends_at: string; status: string; appointment_type: string | null;
      clinician: string | null; location_type: string;
    }>;
    schedule_has_more: boolean;
    unconfirmed_tomorrow: { availability: Availability; value: null; reason: string };
    last_7_days: AppointmentPeriod | null; previous_7_days: AppointmentPeriod | null;
  };
  payments: {
    availability: Availability; overdue_invoice_count: number | null; overdue_balance_pence: number | null;
    items_availability: Availability;
    items: Array<{ invoice_id: number; invoice_number: string; patient_id: number; patient_name: string; due_date: string; balance_pence: number }>;
    items_has_more: boolean;
    last_7_days_invoiced_pence: number | null; previous_7_days_invoiced_pence: number | null;
  };
  patients: {
    availability: Availability; recent: Array<{ id: number; name: string; phone?: string | null; created_at: string }>;
    recent_has_more: boolean; basis: "created_at";
  };
  recalls: {
    availability: Availability; due_this_week: number | null; overdue: number | null; scheduled_this_month: number | null;
    conversion_rate: { availability: Availability; value: null; reason: string };
  };
  definitions: Record<string, string>;
};
