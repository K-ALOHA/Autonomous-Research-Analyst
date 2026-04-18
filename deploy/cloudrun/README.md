# Cloud Run deployment

Templates:

- `backend.service.yaml`
- `frontend.service.yaml`

These files are template manifests. The deploy script replaces placeholders:

- `BACKEND_SERVICE_NAME`
- `FRONTEND_SERVICE_NAME`
- `IMAGE_BACKEND`
- `IMAGE_FRONTEND`
- `BACKEND_URL_VALUE`

Deploy both services:

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export AR_REPOSITORY="ara-images"
./scripts/deploy-cloudrun.sh
```

Optional overrides:

- `BACKEND_SERVICE_NAME` (default `ara-backend`)
- `FRONTEND_SERVICE_NAME` (default `ara-frontend`)
- `TAG` (default timestamp)
