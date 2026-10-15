import type { CSSProperties } from "react";

/**
 * Os cursores do tomoyo.systems: a seta do Plan 9, a mão e o I do X11, as mãos para arrastar.
 * Cada um em 16 px com cópia 2x; o ponto quente e o cursor nativo de reserva vão junto. O CSS
 * (globals.css) decide quando usá-los: só com mouse de verdade, as mãos claras no tema escuro.
 */
const CURSORS: Array<[name: string, hotspot: string, fallback: string]> = [
  ["arrow", "1 1", "default"],
  ["pointer", "0 0", "pointer"],
  ["text", "4 7", "text"],
  ["grab", "8 8", "grab"],
  ["grabbing", "8 8", "grabbing"],
  ["grab-dark", "8 8", "grab"],
  ["grabbing-dark", "8 8", "grabbing"],
];

export function cursorVars(basePath: string): CSSProperties {
  const vars: Record<string, string> = {};
  for (const [name, hotspot, fallback] of CURSORS) {
    const file = `${basePath}/cursors/${name}`;
    vars[`--cur-${name}-img`] = `image-set(url(${file}.png) 1x, url(${file}@2x.png) 2x) ${hotspot}, ${fallback}`;
  }
  return vars as CSSProperties;
}
