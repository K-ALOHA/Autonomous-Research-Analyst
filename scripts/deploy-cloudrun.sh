#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCP_REGION:?Set GCP_REGION (for example us-central1)}"
: "${AR_REPOSITORY:?Set AR_REPOSITORY (Artifact Registry repository name)}"

BACKEND_SERVICE_NAME="${BACKEND_SERVICE_NAME:-ara-backend}"
FRONTEND_SERVICE_NAME="${FRONTEND_SERVICE_NAME:-ara-frontend}"
TAG="${TAG:-$(date +%Y%m%d%H%M%S)}"

BACKEND_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${BACKEND_SERVICE_NAME}:${TAG}"
FRONTEND_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${FRONTEND_SERVICE_NAME}:${TAG}"

tmp_backend=""
tmp_frontend=""
cleanup() {
  [[ -n "${tmp_backend}" && -f "${tmp_backend}" ]] && rm -f "${tmp_backend}"
  [[ -n "${tmp_frontend}" && -f "${tmp_frontend}" ]] && rm -f "${tmp_frontend}"
}
trap cleanup EXIT

echo "Building backend image: ${BACKEND_IMAGE}"
gcloud builds submit \
  --project "${GCP_PROJECT_ID}" \
  --tag "${BACKEND_IMAGE}" \
  --file backend/Dockerfile \
  .

tmp_backend="$(mktemp)"
sed -e "s|IMAGE_BACKEND|${BACKEND_IMAGE}|g" \
    -e "s|BACKEND_SERVICE_NAME|${BACKEND_SERVICE_NAME}|g" \
    deploy/cloudrun/backend.service.yaml > "${tmp_backend}"

echo "Deploying backend service: ${BACKEND_SERVICE_NAME}"
gcloud run services replace "${tmp_backend}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}"
gcloud run services add-iam-policy-binding "${BACKEND_SERVICE_NAME}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --member="allUsers" \
  --role="roles/run.invoker" >/dev/null

BACKEND_URL="$(
  gcloud run services describe "${BACKEND_SERVICE_NAME}" \
    --project "${GCP_PROJECT_ID}" \
    --region "${GCP_REGION}" \
    --format='value(status.url)'
)"
if [[ -z "${BACKEND_URL}" ]]; then
  echo "Failed to resolve backend URL from Cloud Run." >&2
  exit 1
fi
echo "Backend URL: ${BACKEND_URL}"

echo "Building frontend image: ${FRONTEND_IMAGE}"
gcloud builds submit \
  --project "${GCP_PROJECT_ID}" \
  --tag "${FRONTEND_IMAGE}" \
  --file frontend/Dockerfile \
  .

tmp_frontend="$(mktemp)"
sed -e "s|IMAGE_FRONTEND|${FRONTEND_IMAGE}|g" \
    -e "s|FRONTEND_SERVICE_NAME|${FRONTEND_SERVICE_NAME}|g" \
    -e "s|BACKEND_URL_VALUE|${BACKEND_URL}|g" \
    deploy/cloudrun/frontend.service.yaml > "${tmp_frontend}"

echo "Deploying frontend service: ${FRONTEND_SERVICE_NAME}"
gcloud run services replace "${tmp_frontend}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}"
gcloud run services add-iam-policy-binding "${FRONTEND_SERVICE_NAME}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --member="allUsers" \
  --role="roles/run.invoker" >/dev/null

FRONTEND_URL="$(
  gcloud run services describe "${FRONTEND_SERVICE_NAME}" \
    --project "${GCP_PROJECT_ID}" \
    --region "${GCP_REGION}" \
    --format='value(status.url)'
)"

echo "Deployment complete."
echo "Frontend URL: ${FRONTEND_URL}"
echo "Backend URL: ${BACKEND_URL}"
