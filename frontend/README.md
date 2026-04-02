# PNBallie Frontend

## Development

1. Create `frontend/.env.local` (or copy from `.env.example`) with:

```dotenv
VITE_AZURE_CLIENT_ID=your-azure-client-id
VITE_AZURE_TENANT_ID=your-azure-tenant-id
VITE_AZURE_SCOPE=api://your-azure-client-id/user
```

2. Install dependencies:

```bash
npm install
```

3. Start local development:

```bash
npm run dev
```

The app uses MSAL redirect login and requires authentication before loading routes.
After login, the frontend auto-provisions a player using the signed-in account name.
