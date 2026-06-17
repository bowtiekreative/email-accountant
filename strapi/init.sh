#!/usr/bin/env bash
# One-time: scaffold the Strapi app and inject the orchestration content-types.
# Run from the repo root:  ./strapi/init.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/app"

if [ -d "$APP" ]; then
  echo "✔ $APP already exists — skipping scaffold."
else
  echo "▶ Scaffolding Strapi app (this pulls from npm)…"
  npx create-strapi-app@latest "$APP" \
    --no-run --skip-cloud --use-npm \
    --dbclient=postgres --dbhost=localhost --dbport=5432 \
    --dbname=strapi --dbusername=strapi --dbpassword=strapi || {
      echo "create-strapi-app failed — run it manually, then re-run this script."; exit 1; }
fi

echo "▶ Injecting content-types (Transaction, SyncLog, RoutingRule)…"
for name in transaction sync-log routing-rule; do
  dir="$APP/src/api/$name/content-types/$name"
  mkdir -p "$dir"
  cp "$HERE/schemas/$name.schema.json" "$dir/schema.json"
  # Minimal controller/route/service so the REST API is exposed.
  mkdir -p "$APP/src/api/$name/controllers" "$APP/src/api/$name/routes" "$APP/src/api/$name/services"
  cat > "$APP/src/api/$name/controllers/$name.js" <<JS
'use strict';
const { createCoreController } = require('@strapi/strapi').factories;
module.exports = createCoreController('api::$name.$name');
JS
  cat > "$APP/src/api/$name/routes/$name.js" <<JS
'use strict';
const { createCoreRouter } = require('@strapi/strapi').factories;
module.exports = createCoreRouter('api::$name.$name');
JS
  cat > "$APP/src/api/$name/services/$name.js" <<JS
'use strict';
const { createCoreService } = require('@strapi/strapi').factories;
module.exports = createCoreService('api::$name.$name');
JS
done

echo "✅ Done. Next:"
echo "   1) docker compose --env-file .env.stack up -d --build strapi"
echo "   2) Open http://localhost:1337/admin, create the admin user"
echo "   3) Settings → API Tokens → create a full-access token → put it in STRAPI_TOKEN"
