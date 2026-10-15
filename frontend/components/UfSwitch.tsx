"use client";

import { usePathname } from "next/navigation";
import { CASAS, UF, casaHref } from "@/lib/uf";

/** Seletor de Assembleia no cabeçalho. Cada casa é um build próprio: trocar navega para a mesma tela na outra. */
export function UfSwitch() {
  const pathname = usePathname();
  return (
    <select
      className="yearselect"
      aria-label="Casa"
      value={UF}
      onChange={(event) => {
        const casa = CASAS.find((item) => item.uf === event.target.value);
        if (casa) {
          window.location.href = casaHref(casa, pathname);
        }
      }}
    >
      {CASAS.map((casa) => (
        <option key={casa.uf} value={casa.uf}>
          {casa.nome}
        </option>
      ))}
    </select>
  );
}
