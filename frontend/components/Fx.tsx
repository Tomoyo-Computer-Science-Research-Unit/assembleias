"use client";

import { useEffect } from "react";
import { isTyping } from "@/components/Hotkeys";

const STORAGE_KEY = "pp-fx";

/**
 * Efeitos de impressão do tomoyo.systems (print-fx, após o print-fx do remilia.org): a folha é
 * deformada por um campo de turbulência; a tinta sozinha é tirada como segunda chapa, deformada
 * por outro campo e impressa de volta, com leve desregistro, como riso ou fotocópia. A tecla F
 * liga e desliga.
 */
export function Fx() {
  useEffect(() => {
    const root = document.documentElement;
    let enabled = true;
    try {
      enabled = window.localStorage.getItem(STORAGE_KEY) !== "off";
    } catch {
      // sem armazenamento: fica ligado
    }
    root.classList.toggle("fx", enabled);

    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) {
        return;
      }
      if (event.key === "f" || event.key === "F") {
        enabled = !enabled;
        root.classList.toggle("fx", enabled);
        try {
          window.localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
        } catch {
          // ignorar
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
      <defs>
        <filter id="print-fx-light" x="-4%" y="-4%" width="108%" height="108%">
          <feTurbulence type="turbulence" baseFrequency="0.018" numOctaves="1" seed="0" result="grain" />
          <feDisplacementMap in="SourceGraphic" in2="grain" scale="1.2" xChannelSelector="R" yChannelSelector="G" result="sheet" />
          <feTurbulence type="turbulence" baseFrequency="0.008" numOctaves="1" seed="7" result="drift" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -.47 -.47 -.47 0 1.2" result="inkonly" />
          <feComposite in="inkonly" in2="SourceAlpha" operator="in" result="linework" />
          <feDisplacementMap in="linework" in2="drift" scale="1.8" xChannelSelector="R" yChannelSelector="G" result="wet" />
          <feFlood floodColor="#0e0e0e" result="inkwell" />
          <feComposite in="inkwell" in2="wet" operator="in" result="plate" />
          <feMerge>
            <feMergeNode in="plate" />
            <feMergeNode in="sheet" />
          </feMerge>
        </filter>
        <filter id="print-fx-dark" x="-4%" y="-4%" width="108%" height="108%">
          <feTurbulence type="turbulence" baseFrequency="0.018" numOctaves="1" seed="0" result="grain" />
          <feDisplacementMap in="SourceGraphic" in2="grain" scale="1.2" xChannelSelector="R" yChannelSelector="G" result="sheet" />
          <feTurbulence type="turbulence" baseFrequency="0.008" numOctaves="1" seed="7" result="drift" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  .47 .47 .47 0 -.2" result="inkonly" />
          <feComposite in="inkonly" in2="SourceAlpha" operator="in" result="linework" />
          <feDisplacementMap in="linework" in2="drift" scale="1.8" xChannelSelector="R" yChannelSelector="G" result="wet" />
          <feFlood floodColor="#f4f4f3" result="inkwell" />
          <feComposite in="inkwell" in2="wet" operator="in" result="plate" />
          <feMerge>
            <feMergeNode in="plate" />
            <feMergeNode in="sheet" />
          </feMerge>
        </filter>
      </defs>
    </svg>
  );
}
