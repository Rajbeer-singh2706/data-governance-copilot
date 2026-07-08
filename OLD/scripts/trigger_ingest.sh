#!/usr/bin/env bash
# Helper: trigger the on_demand_ingest_dag via Airflow REST API
# Usage: bash scripts/trigger_ingest.sh /path/to/document.pdf

set -euo pipefail

FILEPATH="${1:-}"
if [[ -z "$FILEPATH" ]]; then
  echo "Usage: $0 <filepath>"
  exit 1
fi

AIRFLOW_HOST="${AIRFLOW_HOST:-localhost:8080}"
AIRFLOW_USER="${AIRFLOW_ADMIN_USER:-admin}"
AIRFLOW_PASS="${AIRFLOW_ADMIN_PASSWORD:-admin}"

echo "Triggering on_demand_ingest_dag for: $FILEPATH"

curl -s -X POST \
  "http://${AIRFLOW_HOST}/api/v1/dags/on_demand_ingest_dag/dagRuns" \
  -H "Content-Type: application/json" \
  -u "${AIRFLOW_USER}:${AIRFLOW_PASS}" \
  -d "{\"conf\": {\"filepath\": \"${FILEPATH}\"}}" | python3 -m json.tool

echo ""
echo "✅ DAG triggered. Check Airflow UI at http://${AIRFLOW_HOST}"