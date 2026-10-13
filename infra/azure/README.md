# Running the audit on Azure

The audit is batch compute, so it maps cleanly onto **Azure Container Apps jobs**
(on-demand or scheduled). Output is a DuckDB file plus a Parquet invalid-token
mask that training pipelines can consume directly.

## Flow

```text
dataset (Blob Storage) --> ACA job: kozquloq scan + export
                                   |
                                   +--> /out/kozquloq.duckdb + mask.parquet
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
  --args scan --dataroot /data --db /out/kozquloq.duckdb --viz-dir /out/viz
```

Mount the nuScenes dataset via Azure Files (`--volumes`) or download it in an
init container. A second run publishes the mask:

```bash
kozquloq export --db /out/kozquloq.duckdb --output /out/invalid_tokens.parquet
```

## 3. Run it

```bash
az containerapp job start --name kozquloq-audit --resource-group <rg>
```

For a recurring audit (e.g. nightly on fresh uploads), use
`--trigger-type Schedule --cron-expression "0 3 * * *"`.
