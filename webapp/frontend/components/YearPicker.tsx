"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function YearPicker({
  value,
  onChange,
}: {
  value?: number;
  onChange: (year?: number) => void;
}) {
  const [years, setYears] = useState<number[]>([]);

  useEffect(() => {
    api.years().then(setYears).catch(() => setYears([]));
  }, []);

  return (
    <select
      className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm"
      value={value ?? ""}
      onChange={(e) =>
        onChange(e.target.value ? Number(e.target.value) : undefined)
      }
    >
      <option value="">All years</option>
      {years.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </select>
  );
}
