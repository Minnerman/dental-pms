import type { ReactNode } from "react";

type TableProps = {
  children: ReactNode;
  className?: string;
};

export default function Table({ children, className }: TableProps) {
  return <table className={`table ${className || ""}`.trim()}>{children}</table>;
}
