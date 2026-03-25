import type { ReactNode } from "react";

import styles from "./patient-responsive.module.css";

export default function PatientRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <div className={styles.shell}>{children}</div>;
}
