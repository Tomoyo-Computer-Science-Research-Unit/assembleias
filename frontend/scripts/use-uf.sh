#!/usr/bin/env sh
# Copia os dados de uma UF (frontend/data/<uf>/) para onde o código os importa:
# lib/static-data.generated.json, lib/static-votacoes/, lib/static-deputados/ e public/fotos/.
# Um build só contém os dados de uma UF.  Uso: scripts/use-uf.sh [rj|sp]  (padrão: $NEXT_PUBLIC_UF ou rj)
set -eu
cd "$(dirname "$0")/.."
uf="$(printf '%s' "${1:-${NEXT_PUBLIC_UF:-RJ}}" | tr 'A-Z' 'a-z')"
src="data/$uf"
[ -f "$src/static-data.generated.json" ] || { echo "use-uf: $src/static-data.generated.json não existe" >&2; exit 1; }
rm -rf lib/static-votacoes lib/static-deputados public/fotos
cp "$src/static-data.generated.json" lib/static-data.generated.json
cp -R "$src/static-votacoes" lib/static-votacoes
cp -R "$src/static-deputados" lib/static-deputados
if [ -d "$src/fotos" ]; then cp -R "$src/fotos" public/fotos; else mkdir -p public/fotos; fi
echo "use-uf: $uf"
