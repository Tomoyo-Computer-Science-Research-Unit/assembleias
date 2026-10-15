import type { Metadata } from "next";
import { PartidosScreen } from "@/components/PartidosScreen";

export const metadata: Metadata = { title: "Partidos" };

export default function PartidosPage() {
  return <PartidosScreen />;
}
