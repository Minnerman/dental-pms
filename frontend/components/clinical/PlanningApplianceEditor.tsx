"use client";

import { useState } from "react";
import { planningToothLabel, type PlanningAppliance, type PlanningSnapshot } from "./treatmentPlanning";
import styles from "./TreatmentPlanningPanel.module.css";

export const applianceArchTeeth = (arch: "upper" | "lower") => {
  const right = arch === "upper" ? "UR" : "LR", left = arch === "upper" ? "UL" : "LL";
  return [...Array.from({ length: 8 }, (_, i) => `${right}${8 - i}`), ...Array.from({ length: 8 }, (_, i) => `${left}${i + 1}`)];
};

export default function PlanningApplianceEditor({ appliance, snapshot, onChange }: {
  appliance: PlanningAppliance; snapshot?: PlanningSnapshot; onChange: (next: PlanningAppliance) => void;
}) {
  const [anchor, setAnchor] = useState<string | null>(null);
  const positions = applianceArchTeeth(appliance.arch);
  function select(tooth: string) {
    if (appliance.kind === "denture") {
      const selected = new Set(appliance.members.map((member) => member.tooth));
      if (selected.has(tooth)) selected.delete(tooth); else selected.add(tooth);
      onChange({ ...appliance, members: positions.filter((entry) => selected.has(entry)).map((entry) => ({ tooth: entry, role: "denture" })) });
    } else if (!anchor) {
      setAnchor(tooth);
      onChange({ ...appliance, members: [{ tooth, role: "abutment" }] });
    } else {
      const first = positions.indexOf(anchor), last = positions.indexOf(tooth);
      const span = positions.slice(Math.min(first, last), Math.max(first, last) + 1);
      onChange({ ...appliance, members: span.map((entry, index) => ({ tooth: entry, role: index === 0 || index === span.length - 1 ? "abutment" : "pontic" })) });
      setAnchor(null);
    }
  }
  return <section className={styles.applianceEditor} data-testid="planning-group-editor" aria-label={`${appliance.kind === "bridge" ? "Bridge" : "Denture"} teeth`}>
    <div className={styles.header}>
      <label>Arch<select data-testid="planning-group-arch" value={appliance.arch} onChange={(event) => { setAnchor(null); onChange({ ...appliance, arch: event.target.value as PlanningAppliance["arch"], members: [] }); }}><option value="upper">Upper</option><option value="lower">Lower</option></select></label>
      {appliance.kind === "denture" && <button type="button" className="btn btn-secondary" data-testid="planning-group-full" onClick={() => onChange({ ...appliance, members: positions.map((tooth) => ({ tooth, role: "denture" })) })}>Full denture</button>}
      <button type="button" className="btn btn-secondary" data-testid="planning-group-clear" onClick={() => { setAnchor(null); onChange({ ...appliance, members: [] }); }}>Clear selection</button>
    </div>
    <p className={styles.muted}>{appliance.kind === "bridge" ? anchor ? "Now click the last bridge tooth." : "Click the first and last bridge teeth. Then review the suggested roles below." : "Click every tooth being replaced, or select Full denture. One appliance fee covers this selection."}</p>
    <div className={styles.applianceTeeth} role="group" aria-label="Select appliance teeth">{positions.map((tooth) => <button type="button" key={tooth} data-testid={`planning-group-member-${tooth}`} aria-pressed={appliance.members.some((member) => member.tooth === tooth)} onClick={() => select(tooth)}>{planningToothLabel(tooth, snapshot)}</button>)}</div>
    {appliance.members.length > 0 && <div className={styles.memberRoles} data-testid="planning-group-summary">
      {appliance.members.map((member) => appliance.kind === "bridge" ? <label key={member.tooth}>{planningToothLabel(member.tooth, snapshot)}<select data-testid={`planning-group-role-${member.tooth}`} value={member.role} onChange={(event) => onChange({ ...appliance, members: appliance.members.map((entry) => entry.tooth === member.tooth ? { ...entry, role: event.target.value as typeof member.role } : entry) })}><option value="abutment">Abutment</option><option value="pontic">Pontic</option><option value="wing">Wing</option></select></label> : <span key={member.tooth}>{planningToothLabel(member.tooth, snapshot)}</span>)}
    </div>}
    <small className={styles.muted}>{appliance.kind === "bridge" ? "Abutment = support crown · Pontic = replacement tooth · Wing = bonded support. Adding confirms these roles; the chart does not assess support suitability." : "Only selected replacement teeth are drawn. Existing teeth and implants are not marked missing by adding this plan."}</small>
  </section>;
}
