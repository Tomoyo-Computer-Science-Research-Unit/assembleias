"use client";

import { usePathname } from "next/navigation";

const HINTS: Record<string, Array<[string, string]>> = {
  "/": [
    ["↑↓", "deputado"],
    ["←→", "ordem"],
    ["v", "votos / proposições"],
    ["e", "em exercício / todos"]
  ],
  "/votacoes": [
    ["↑↓", "votação"],
    ["←→", "ano"],
    ["r", "resultado"]
  ],
  "/presenca": [
    ["←→", "ano"],
    ["↑↓", "ordem"]
  ],
  "/partidos": [["↑↓", "partido"]],
  "/metodologia": []
};

export function StatusBar({ latestLabel }: { latestLabel: string }) {
  const pathname = usePathname();
  const base = pathname.replace(/\/+$/, "") || "/";
  const hints = HINTS[base] ?? [];

  return (
    <footer className="statusbar">
      <span className="flex items-center gap-4">
        {hints.map(([key, label]) => (
          <span key={key}>
            <span className="kbd">{key}</span>
            {label}
          </span>
        ))}
        <span>
          <span className="kbd">1–5</span>telas
        </span>
        <span>
          <span className="kbd">u</span>casa
        </span>
        <span>
          <span className="kbd">t</span>tema
        </span>
        <span>
          <span className="kbd">f</span>efeitos
        </span>
      </span>
      <span className="num">{latestLabel}</span>
    </footer>
  );
}
