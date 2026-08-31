# PNBallie frontend

De frontend leest de Entra-configuratie tijdens het starten uit `/config.json`. Kopieer voor lokale ontwikkeling het voorbeeld:

```bash
cp public/config.example.json public/config.json
npm run dev
```

`public/config.json` wordt niet gecommit en wordt uitgesloten van de containerbuild. Vul `azureClientId`, `azureTenantId` en `azureScope` in volgens het contract in de hoofd-README.

Beschikbare controles: `npm run lint`, `npm test`, `npm run type-check` en `npm run build`.
