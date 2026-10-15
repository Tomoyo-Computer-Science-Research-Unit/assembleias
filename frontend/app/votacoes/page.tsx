import type { Metadata } from "next";
import { VotacoesExplorer } from "@/components/VotacoesExplorer";

export const metadata: Metadata = { title: "Votações" };

export default function VotacoesPage() {
  return <VotacoesExplorer />;
}
