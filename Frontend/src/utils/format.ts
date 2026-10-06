export const duration = (n: number | null) =>
  n === null ? "—" : `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
export const date = (v: string | null) => {
  if (!v) return "—";
  const x = /^\d{8}$/.test(v) ? `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}` : v,
    d = new Date(x);
  return isNaN(d.getTime())
    ? v
    : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(d);
};
