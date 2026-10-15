import type { Metadata } from "next";
import { PresencaScreen } from "@/components/PresencaScreen";

export const metadata: Metadata = { title: "Presença" };

export default function PresencaPage() {
  return <PresencaScreen />;
}
