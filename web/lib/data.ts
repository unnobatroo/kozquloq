import type { Report } from "./report";
import bundled from "../public/report.json";

/**
 * Live mode: when NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY are
 * set, fetch the latest report row from Supabase. Otherwise (or on any
 * failure) fall back to the JSON bundled at build time.
 */
export async function loadReport(): Promise<Report> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (url && key) {
    try {
      const res = await fetch(
        `${url}/rest/v1/reports?select=payload&order=created_at.desc&limit=1`,
        { headers: { apikey: key, Authorization: `Bearer ${key}` } },
      );
      if (res.ok) {
        const rows = (await res.json()) as { payload: Report }[];
        if (rows[0]?.payload?.health) return rows[0].payload;
      }
    } catch {
      // fall through to bundled data
    }
  }
  return bundled as unknown as Report;
}
