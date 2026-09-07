// A guide only: age is never written to the tooth-conditions API as a finding.
// AAPD Dental Growth and Development (2025), primary exfoliation ranges:
// https://www.aapd.org/globalassets/media/policies_guidelines/r_dentalgrowth25.pdf
import { britishToothLabel } from "./toothDiagnosis";

export function dentitionSuggestion(dateOfBirth?: string | null, today = new Date()) {
  if (!dateOfBirth || !/^\d{4}-\d{2}-\d{2}$/.test(dateOfBirth)) return null;
  const birth = new Date(dateOfBirth + "T12:00:00");
  if (!Number.isFinite(birth.getTime()) || birth > today || birth.toISOString().slice(0, 10) !== dateOfBirth) return null;
  const age = (today.getFullYear() - birth.getFullYear()) +
    ((today.getMonth() * 31 + today.getDate()) - (birth.getMonth() * 31 + birth.getDate())) / 372;
  const likely: string[] = [];
  const changing: string[] = [];
  const upper = [[7, 8], [8, 9], [11, 12], [9, 11], [9, 12]];
  const lower = [[6, 7], [7, 8], [9, 11], [10, 12], [11, 13]];
  if (age >= 3 && age < 13) for (const quadrant of ["UR", "UL", "LR", "LL"]) {
    (quadrant.startsWith("U") ? upper : lower).forEach(([from, until], i) => {
      if (age < from) likely.push(quadrant + (i + 1));
      else if (age < until) changing.push(quadrant + (i + 1));
    });
  }
  return { age: Math.floor(age), likely, changing, stage: age < 3 ? "Developing primary dentition" : age < 6 ? "Primary dentition" : age < 13 ? "Mixed dentition" : "Permanent dentition" };
}

export default function DentitionGuide({ dateOfBirth, hasFindings }: { dateOfBirth?: string | null; hasFindings: boolean }) {
  if (hasFindings) return null;
  const guide = dentitionSuggestion(dateOfBirth);
  return <aside className="clinical-dentition-guide" data-testid="diagnosis-dentition-guide">
    <strong>First chart · Unconfirmed age guide</strong>
    <p>{guide ? `Age ${guide.age}: ${guide.stage.toLowerCase()} is a starting guide, not a diagnosis.` : "A valid date of birth is needed for an age-based dentition suggestion."} Confirm the teeth clinically before recording findings.</p>
    {guide && guide.age < 3 && <p>Primary teeth are developing. Eruption varies; check each tooth individually.</p>}
    {Boolean(guide?.likely.length) && <p>Likely primary teeth to check: {guide!.likely.map((tooth) => britishToothLabel(tooth, "deciduous")).join(", ")}.</p>}
    {Boolean(guide?.changing.length) && <p>Primary or permanent — check transition sites: {guide!.changing.map((tooth) => `${britishToothLabel(tooth, "deciduous")}/${tooth}`).join(", ")}.</p>}
    <p>No teeth are marked present, missing or unerupted from age. Wisdom teeth also need individual assessment. This guide is not saved as clinical data.</p>
    <a href="https://www.aapd.org/globalassets/media/policies_guidelines/r_dentalgrowth25.pdf" target="_blank" rel="noreferrer">Age-guide reference · AAPD</a>
  </aside>;
}
