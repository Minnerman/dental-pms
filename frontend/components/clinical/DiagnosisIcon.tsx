import type { DiagnosisAction } from "./toothDiagnosis";

// One consistent, original line-icon family for the palette and number menu.
const tooth = "M7 3.5C4 3.5 3.5 6.2 4.3 9.5L6.4 18.6C6.9 21.2 8.5 21.4 9.2 18.4L10.6 13.7C11.1 12.1 12.9 12.1 13.4 13.7L14.8 18.4C15.5 21.4 17.1 21.2 17.6 18.6L19.7 9.5C20.5 6.2 20 3.5 17 3.5C15 3.5 13.4 4.5 12 4.5S9 3.5 7 3.5Z";

export default function DiagnosisIcon({ action, className }: { action: DiagnosisAction; className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" width="1em" height="1em"
    fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" focusable="false" data-diagnosis-icon={action}>
    {action === "missing" && <><path d={tooth} opacity=".45" /><path d="m7 8 10 10M17 8 7 18" /></>}
    {action === "deciduous" && <><path d={tooth} transform="translate(-1 2) scale(.83)" /><path d="m16 7 2.5-5L21 7m-4-2h3" /></>}
    {action === "implant" && <><path d="M8 3h8v3H8zM8 6l1.5 13.5Q12 23 14.5 19.5L16 6M7.5 8.5h9M8 11.5h8M8.5 14.5h7M9 17.5h6" /></>}
    {action === "unerupted" && <><path d="M2 7q2.5-3 5 0t5 0t5 0t5 0" /><path d="M5 20v-3c0-6 3.5-7 7-5 3.5-2 7-1 7 5v3Z" /></>}
    {action === "impacted" && <><path d={tooth} transform="translate(0 3) rotate(-34 10 12) scale(.78)" /><path d="M18 9c3-1 4 1 3.5 4L20 20m-2-10v5" /></>}
    {action === "present" && <><path d={tooth} /><path d="m8.5 8 2.5 2.5 4.5-5" /></>}
    {action === "movement_forward" && <><path d="M12 3v18" strokeDasharray="2 3" opacity=".45" /><path d="M2 12h7m-3-3 3 3-3 3M22 12h-7m3-3-3 3 3 3" /></>}
    {action === "movement_backward" && <><path d="M12 3v18" strokeDasharray="2 3" opacity=".45" /><path d="M9 12H2m3-3-3 3 3 3M15 12h7m-3-3 3 3-3 3" /></>}
    {(action === "rotation_clockwise" || action === "rotation_anticlockwise") && <g transform={action === "rotation_anticlockwise" ? "translate(24 0) scale(-1 1)" : undefined}>
      <path d="M20 7a9 9 0 1 0 1 8M20 2v5h-5" /><path d={tooth} transform="translate(7 7) scale(.42)" />
    </g>}
    {action === "reset" && <><path d="M4 7a9 9 0 1 1-1 8M4 2v5h5" /><path d={tooth} transform="translate(7 7) scale(.42)" /></>}
  </svg>;
}
