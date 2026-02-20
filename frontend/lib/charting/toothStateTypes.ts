export const TOOTH_STATE_TYPES = [
  "implant",
  "bridge",
  "crown",
  "veneer",
  "inlay_onlay",
  "post",
  "root_canal",
  "filling",
  "extraction",
  "denture",
  "other",
] as const;

export type ToothStateType = (typeof TOOTH_STATE_TYPES)[number];

export const TOOTH_STATE_TYPE_LABELS: Record<ToothStateType, string> = {
  implant: "implant",
  bridge: "bridge",
  crown: "crown",
  veneer: "veneer",
  inlay_onlay: "inlay/onlay",
  post: "post",
  root_canal: "root canal",
  filling: "filling",
  extraction: "extraction",
  denture: "denture",
  other: "other",
};

const TOOTH_STATE_TYPE_SET = new Set<ToothStateType>(TOOTH_STATE_TYPES);

export function isToothStateType(value: unknown): value is ToothStateType {
  return typeof value === "string" && TOOTH_STATE_TYPE_SET.has(value as ToothStateType);
}
