"use client";

import { cloneElement, isValidElement, useId, type CSSProperties, type ReactElement, type ReactNode } from "react";

/** Palco de uma tela: grade de painéis que ocupa toda a altura disponível. */
export function Screen({ columns, rows, children, className = "" }: { columns: string; rows?: string; children: ReactNode; className?: string }) {
  const style: CSSProperties = { gridTemplateColumns: columns, gridTemplateRows: rows };
  return (
    <div className={`screen ${className}`} style={style}>
      {children}
    </div>
  );
}

export function Panel({
  title,
  aside,
  children,
  foot,
  flush = false,
  fill = false,
  style,
  className = ""
}: {
  title: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  foot?: ReactNode;
  flush?: boolean;
  fill?: boolean;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`} style={style}>
      <header className="panel__head">
        <span>{title}</span>
        {aside ? <span className="flex shrink-0 items-center gap-2">{aside}</span> : null}
      </header>
      <div className={`panel__body ${flush ? "panel__body--flush" : ""} ${fill ? "panel__body--fill" : ""}`}>{children}</div>
      {foot ? <footer className="panel__foot">{foot}</footer> : null}
    </section>
  );
}

export function Tag({ children, ghost = false }: { children: ReactNode; ghost?: boolean }) {
  return <span className={ghost ? "tag tag--ghost" : "tag"}>{children}</span>;
}

/** Rótulo + controle. O rótulo é ligado por id para que o nome acessível seja só o texto do rótulo. */
export function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  const id = useId();
  return (
    <div className={`field ${className}`}>
      <label id={`${id}-label`} htmlFor={id}>
        {label}
      </label>
      {isValidElement(children) ? cloneElement(children as ReactElement<{ id?: string }>, { id }) : children}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label
}: {
  value: T;
  options: Array<{ value: T; label: string; disabled?: boolean }>;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={value === option.value} disabled={option.disabled} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="px-4 py-6 text-center text-[11px] tracking-[0.18em] text-ash">{children}</p>;
}

/** Linha "rótulo … valor" para painéis de detalhe. */
export function Stat({ label, value, sub }: { label: ReactNode; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-line py-1.5 text-[11.5px]">
      <span className="text-ash">{label}</span>
      <span className="num text-right text-ink">
        {value}
        {sub ? <span className="ml-1 text-ash">{sub}</span> : null}
      </span>
    </div>
  );
}
