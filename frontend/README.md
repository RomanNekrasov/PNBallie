# PNBallie frontend

De Vue-frontend vraagt inlogopties op bij `/api/auth/providers`. Lokale accounts
werken zonder frontendconfiguratie; een optionele OIDC-provider wordt uitsluitend
op de backend ingesteld. Start vanuit deze map met:

```bash
npm ci
npm run dev
```

De Vite-proxy stuurt `/api` naar `http://localhost:8000`. De browserorigin voor de
backend is bij native ontwikkeling `http://localhost:5173`. Zie de hoofd-README
voor installatie, groepsbeheer en de migratie van de oude Entra-authenticatie.

Beschikbare controles: `npm run lint`, `npm test`, `npm run type-check` en `npm run build`.
