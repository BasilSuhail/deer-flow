import { redirect } from "next/navigation";

export default function LandingPage() {
  redirect("/workspace/chats/new");
}
