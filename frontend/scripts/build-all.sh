#!/usr/bin/env sh
# Constrói todas as casas de data/casas.json e junta num só diretório servível, como no servidor:
#   out-all/          a casa raiz (root=true), base "$ROOT"
#   out-all/<slug>/   cada uma das demais, base "$ROOT/<slug>"
# ROOT vazio serve na raiz (testes); em produção o deploy usa ROOT=/assembleias e publica cada pasta.
set -eu
cd "$(dirname "$0")/.."
ROOT="${ROOT:-}"
rm -rf out out-all out-casas .next
mkdir -p out-casas
node -e 'for (const c of require("./data/casas.json").casas) console.log(c.uf, c.slug, c.root ? 1 : 0)' > out-casas/list
while read -r uf slug isroot; do
  if [ "$isroot" = 1 ]; then base="$ROOT"; else base="$ROOT/$slug"; fi
  rm -rf .next
  NEXT_PUBLIC_UF="$uf" NEXT_PUBLIC_BASE_PATH="$base" npm run build --silent >/dev/null
  mv out "out-casas/$slug"
  echo "build-all: $uf em ${base:-/}"
done < out-casas/list
rootslug="$(awk '$3 == 1 { print $2; exit }' out-casas/list)"
mv "out-casas/$rootslug" out-all
while read -r uf slug isroot; do
  [ "$isroot" = 1 ] || mv "out-casas/$slug" "out-all/$slug"
done < out-casas/list
rm -rf out-casas
