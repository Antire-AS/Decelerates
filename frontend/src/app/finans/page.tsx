// Finansanalyse has moved under /portfolio/analytics — this route exists only
// to preserve old bookmarks. Server-side redirect; no flash.
import { redirect } from "next/navigation";

export default function FinansRedirect() {
  redirect("/portfolio/analytics");
}
