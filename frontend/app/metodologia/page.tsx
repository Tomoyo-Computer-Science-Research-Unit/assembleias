import type { Metadata } from "next";
import { Panel, Screen } from "@/components/ui";
import { methodSections } from "@/lib/method";
import { formatInt, getMeta, getDeputados, getVotacoes } from "@/lib/static-api";

export const metadata: Metadata = { title: "Método" };

function flatten(prefix: string, value: unknown, out: Array<[string, string]>) {
  if (value === null || value === undefined) {
    return;
  }
  if (typeof value === "number" || typeof value === "string" || typeof value === "boolean") {
    out.push([prefix, typeof value === "number" ? formatInt(value) : String(value)]);
    return;
  }
  if (Array.isArray(value)) {
    out.push([prefix, `${value.length} itens`]);
    return;
  }
  if (typeof value === "object") {
    for (const [key, inner] of Object.entries(value as Record<string, unknown>)) {
      flatten(prefix ? `${prefix} · ${key}` : key, inner, out);
    }
  }
}

export default function MethodPage() {
  const meta = getMeta();
  const votacoes = getVotacoes();
  const deputados = getDeputados();
  const semResultado = votacoes.filter((item) => !item.resultado).length;
  const coverage: Array<[string, string]> = [];
  for (const key of ["votacoes", "presenca", "proposicoes"]) {
    flatten(key, (meta.stats as Record<string, unknown>)[key], coverage);
  }
  const generated = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(meta.generated_at));
  const sections = methodSections({ generated, votacoes: votacoes.length, semResultado, stats: meta.stats as Record<string, unknown> });

  return (
    <Screen columns="minmax(0, 1fr) 440px" rows="minmax(0, 1fr) minmax(0, 1fr)">
      <Panel title={<b>Método</b>} fill style={{ gridRow: "1 / span 2" }}>
        <div className="max-w-[72ch] space-y-5 text-[12.5px] leading-6 text-sumi">
          {sections.map((section) => (
            <section key={section.title}>
              <h3 className="serif text-[15px] text-ink">{section.title}</h3>
              <p>{section.body}</p>
            </section>
          ))}
        </div>
      </Panel>

      <Panel title={<b>Cobertura</b>} flush fill>
        <table className="ruled">
          <tbody>
            <tr>
              <td>Deputados</td>
              <td className="num right">{formatInt(deputados.length)}</td>
            </tr>
            <tr>
              <td>Votações nominais lidas</td>
              <td className="num right">{formatInt(votacoes.length)}</td>
            </tr>
            {coverage.map(([key, value]) => (
              <tr key={key}>
                <td className="max-w-[300px] whitespace-normal break-words text-ash">
                  {key}
                </td>
                <td className="num right">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title={<b>Fontes lidas</b>} flush fill>
        <table className="ruled">
          <tbody>
            {meta.sources.map((source) => (
              <tr key={`${source.name}-${source.url}`}>
                <td className="max-w-[320px] whitespace-normal break-words">
                  <a href={source.url} target="_blank" rel="noreferrer" className="text-ink underline decoration-fog underline-offset-4 hover:decoration-ink" title={source.url}>
                    {source.name}
                  </a>
                </td>
                <td className="num right faint">{source.count !== undefined ? formatInt(source.count) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </Screen>
  );
}
