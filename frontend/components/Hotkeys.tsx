"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { NAV_ITEMS } from "@/components/SiteNav";
import { nextCasaHref } from "@/lib/uf";

/** Teclas globais: 1–5 trocam de tela, U passa para a próxima casa, T inverte o tema nesta visita. Ignora campos de formulário. */
export function Hotkeys() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) {
        return;
      }
      const item = NAV_ITEMS.find((candidate) => candidate.key === event.key);
      if (item) {
        event.preventDefault();
        router.push(item.href);
        return;
      }
      if (event.key === "u" || event.key === "U") {
        event.preventDefault();
        window.location.href = nextCasaHref(pathname);
        return;
      }
      if (event.key === "t" || event.key === "T") {
        const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        window.dispatchEvent(new CustomEvent("pp-theme", { detail: next }));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, pathname]);

  return null;
}

export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

/** Atalhos de uma tela: recebe um mapa tecla → ação; setas são passadas como "ArrowUp" etc. */
export function useScreenHotkeys(handlers: Record<string, (event: KeyboardEvent) => void>) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) {
        return;
      }
      const handler = handlers[event.key] ?? handlers[event.key.toLowerCase()];
      if (handler) {
        event.preventDefault();
        handler(event);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlers]);
}
