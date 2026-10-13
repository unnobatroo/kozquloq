# Running the audit on Azure

The audit is batch compute, which maps cleanly onto **Azure Container Apps
jobs**: one shot or on a schedule, and the outputs land wherever you mount
storage. What comes out is a DuckDB file plus a Parquet invalid-token mask
that training pipelines can consume directly.

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

The job command runs scan and export back to back, so one execution produces
both the audit database and the mask:

```bash
az containerapp job create \
  --name kozquloq-audit \
  --resource-group <rg> \
  --environment <aca-env> \
  --image <your-acr>.azurecr.io/kozquloq:latest \
  --cpu 2 --memory 4Gi \
  --replica-timeout 1800 \
  --trigger-type Manual \
  --args sh -c "kozquloq scan --dataroot /data --db /out/kozquloq.duckdb --viz-dir /out/viz && \
                kozquloq export --db /out/kozquloq.duckdb --output /out/invalid_tokens.parquet"
```

Mount the nuScenes dataset read-only at `/data` via Azure Files
(`--volumes`), or download it in an init container. Mount an Azure Files
share at `/out` so outputs land in cloud storage when the container exits -
or run `az storage blob upload` afterwards against `/out/*.parquet`.

## 3. Run it

```bash
az containerapp job start --name kozquloq-audit --resource-group <rg>
```

For a recurring audit (say, nightly over fresh uploads), use
`--trigger-type Schedule --cron-expression "0 3 * * *"`.
