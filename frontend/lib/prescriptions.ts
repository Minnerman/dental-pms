export const medicationInputs = [
  { key: "medicine", label: "Medicine name, strength and form", maxLength: 500, rows: 2 },
  { key: "directions", label: "Directions for use", maxLength: 2000, rows: 4 },
  { key: "quantity", label: "Quantity", maxLength: 120, rows: 1 },
] as const;

export const prescriptionInputs = [
  ...medicationInputs,
  { key: "prescriber_name", label: "Prescriber name", maxLength: 200, rows: 1 },
  { key: "prescriber_gdc", label: "Prescriber GDC number", maxLength: 50, rows: 1 },
] as const;

export type PrescriptionMedication = Record<(typeof medicationInputs)[number]["key"], string>;
export type PrescriptionDetails = Record<(typeof prescriptionInputs)[number]["key"], string>;
export type PrescriptionTemplate = PrescriptionMedication & {
  id: number;
  name: string;
  is_active: boolean;
};

export const emptyPrescription = (): PrescriptionDetails => ({
  medicine: "", directions: "", quantity: "", prescriber_name: "", prescriber_gdc: "",
});
