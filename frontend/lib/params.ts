import { notFound } from "next/navigation";

export function asStringParam(value: string | string[] | null | undefined): string | null {
  if (!value) return null;
  if (Array.isArray(value)) return value[0] ?? null;
  return value;
}

export function requireStringParam(
  name: string,
  value: string | string[] | null | undefined
): string {
  if (!value || Array.isArray(value)) {
    notFound();
  }
  const param = asStringParam(value);
  if (!param) {
    notFound();
  }
  return param;
}

export function requireNumericParam(
  name: string,
  value: string | string[] | null | undefined
): string {
  const param = requireStringParam(name, value);
  if (!/^\d+$/.test(param)) {
    notFound();
  }
  return param;
}
