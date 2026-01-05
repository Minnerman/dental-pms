import { Suspense } from "react";
import ResetPasswordClient from "./ResetPasswordClient";

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <main className="page-center">
          <section className="card" style={{ width: "min(460px, 100%)" }}>
            <div className="stack">
              <div className="badge">Dental PMS</div>
              <div className="badge">Loading reset form…</div>
            </div>
          </section>
        </main>
      }
    >
      <ResetPasswordClient />
    </Suspense>
  );
}
