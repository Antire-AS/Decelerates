// Anbefalingsbrev now lives inside the company profile (CRM tab) so it sits
// next to the related contacts/policies/submissions. This route exists only
// to preserve old bookmarks. If the URL carries ?orgnr=, we deep-link to the
// company; otherwise we send the user to /search to pick one.
import { redirect } from "next/navigation";

export default async function RecommendationsRedirect({
  searchParams,
}: {
  searchParams: Promise<{ orgnr?: string }>;
}) {
  const { orgnr } = await searchParams;
  if (orgnr && /^\d{9}$/.test(orgnr)) {
    redirect(`/search/${orgnr}?tab=crm`);
  }
  redirect("/search");
}
