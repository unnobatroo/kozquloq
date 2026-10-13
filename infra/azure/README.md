# Running the audit on Azure

The audit is batch compute, so it maps cleanly onto **Azure Container Apps jobs**
(on-demand or scheduled). The dashboard on Vercel reads the published report.

## Flow

```text
dataset (Blob Storage) --> ACA job: kozquloq audit + report --json-out
                                   |
                                   +--> Supabase REST (publish_report.py)
```

## 1. Build and push the image

```bash
az acr build --registry <your-acr> --image kozquloq:latest .
```

## 2. Create the job

```bash
az containerapp job create \
  --name kozquloq-audit \
  --resource-group <rg> \
  --environment <aca-env> \
  --image <your-acr>.azurecr.io/kozquloq:latest \
  --cpu 2 --memory 4Gi \
  --replica-timeout 1800 \
  --trigger-type Manual \
  --args audit --dataroot /data --db /out/kozquloq.duckdb \
  --env-vars SUPABASE_URL=<url> SUPABASE_SERVICE_KEY=<key>
```

Mount the nuScenes dataset via Azure Files (`--volumes`) or download it in an
init container. A second command in the same job publishes the report:

```bash
kozquloq report --db /out/kozquloq.duckdb --no-html --json-out /tmp/report.json \
  && python scripts/publish_report.py /tmp/report.json
```

## 3. Run it

```bash
az containerapp job start --name kozquloq-audit --resource-group <rg>
```

For a recurring audit (e.g. nightly on fresh uploads), use
`--trigger-type Schedule --cron-expression "0 3 * * *"`.
