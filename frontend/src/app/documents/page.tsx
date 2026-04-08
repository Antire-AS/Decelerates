// Documents are now a sub-tab inside /knowledge — this route exists only to
// preserve old bookmarks. Server-side redirect; no flash.
import { redirect } from "next/navigation";

export default function DocumentsRedirect() {
  redirect("/knowledge?tab=documents");
}
