# Architecture

Kozquloq is an annotation linter for autonomous-driving datasets: it ingests
nuScenes keyframes, audits every 3D annotation against the sensor evidence,
and emits invalid-token masks plus annotated overlay images.

## Data contracts

Three frozen dataclasses carry everything between stages
(`src/kozquloq/types.py`). Immutable by rule (see `AGENTS.md`).

- `SceneMeta` - scene token, name, weather, time of day.
- `FrameBundle` - one synchronized keyframe: camera image, lidar points,
  annotation boxes, and the four SE(3) transforms + intrinsics needed for
  the `lidar -> ego -> global -> ego -> camera` reprojection chain.
- `AnnBox` - one 3D annotation in the global frame (nuScenes convention:
  local x = length, y = width, z = height).

## Component overview

```mermaid
flowchart LR
    subgraph Sources
        NS[nuScenes dataset<br/>v1.0-mini / full]
        FIX[Fixture dir<br/>fixture.json + npy + jpg]
        SYN[Synthetic scene<br/>synthetic.py]
    end

    subgraph Kozquloq[" "]
        ING[ingestion.py<br/>load_frames]
        subgraph Auditors
            GEO[GeometricAuditor]
            KIN[KinematicAuditor]
            SH[SensorHealthAuditor]
        end
        PIPE[AuditPipeline]
        STORE[(DuckDBAuditStore<br/>samples + audits)]
        OV[overlay.py<br/>static JPEG renderer]
    end

    subgraph Outputs
        DB[(kozquloq.duckdb)]
        MASK[mask.parquet / .json<br/>annotation_token + reason]
        JPG[viz_out/*.jpg]
        DS[QualityAuditDataset<br/>PyTorch]
    end

    NS --> ING
    FIX --> ING
    SYN --> PIPE
    ING --> PIPE
    PIPE --> Auditors
    Auditors --> STORE
    Auditors -. flagged frames .-> OV --> JPG
    STORE --> DB
    DB --> MASK
    DB --> DS
```

## Class diagram

```mermaid
classDiagram
    class BaseAuditor {
        <<abstract>>
        +audit_sample(bundle, findings)*
        +reset()
    }
    class GeometricAuditor
    class KinematicAuditor {
        -KinematicTracker _tracker
    }
    class SensorHealthAuditor
    BaseAuditor <|.. GeometricAuditor
    BaseAuditor <|.. KinematicAuditor
    BaseAuditor <|.. SensorHealthAuditor

    class AuditStore {
        <<abstract>>
        +save_sample(row)*
        +save_audits(rows)*
        +query(sql, params)*
        +query_arrow(sql, params)*
        +get_slice_metrics()*
        +get_summary()*
        +get_invalid_tokens(min_severity)*
        +export_parquet(path)*
        +clear()*
        +transaction()
    }
    class DuckDBAuditStore
    AuditStore <|.. DuckDBAuditStore

    class AuditPipeline {
        +AuditStore store
        +list~BaseAuditor~ auditors
        +Path? viz_dir
        +run(scenes, on_progress, clear)
    }
    AuditPipeline --> AuditStore : injected
    AuditPipeline --> BaseAuditor : injected

    class FrameFindings {
        +FrameBundle bundle
        +list~BoxAuditResult~ boxes
        +SampleHealth? health
    }
    BaseAuditor ..> FrameFindings : writes into

    class BoxAuditResult {
        +bool is_ghost
        +bool is_kinematic_outlier
        +bool is_scale_unstable
        +float severity
        +to_row(sample_token)
    }
    class SampleHealth {
        +to_row(bundle, scene)
    }
    FrameFindings *-- BoxAuditResult
    FrameFindings *-- SampleHealth
```

Auditor ordering matters: `GeometricAuditor` fills `findings.boxes`,
`KinematicAuditor` refines them in place (velocity/acceleration need the
per-frame results), `SensorHealthAuditor` reads them for the drift check.

## Sequence: `kozquloq scan`

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli/main.py
    participant ING as ingestion.py
    participant PIPE as AuditPipeline
    participant AUD as Auditors (geo/kin/health)
    participant OV as overlay.py
    participant DB as DuckDBAuditStore

    User->>CLI: scan --dataroot D --db F --viz-dir V
    CLI->>ING: load_frames(D)
    ING-->>CLI: [(SceneMeta, [FrameBundle])]
    CLI->>PIPE: run(scenes, clear=True)
    PIPE->>DB: transaction()
    loop each scene
        PIPE->>AUD: reset()
        loop each FrameBundle
            PIPE->>AUD: audit_sample(bundle, findings)
            AUD-->>PIPE: boxes + health
            PIPE->>DB: save_sample(row)
            opt frame has flagged boxes and viz_dir set
                PIPE->>OV: save_annotated_frame(bundle, boxes, V)
                OV-->>PIPE: V/{sample_token}.jpg
            end
        end
        PIPE->>DB: save_audits(rows)
    end
    PIPE->>DB: commit()
    DB-->>CLI: get_summary() / get_slice_metrics()
    CLI-->>User: Rich tables
```

## Storage schema

```mermaid
erDiagram
    samples ||--o{ audits : "sample_token"
    samples {
        varchar sample_token PK
        varchar scene_name
        varchar weather
        varchar time_of_day
        bigint  timestamp
        double  ego_speed_mps
        int     camera_underexposed_count
        int     lidar_total_points
        int     radar_total_returns
        bool    has_geometric_drift
    }
    audits {
        varchar annotation_token PK
        varchar sample_token FK
        varchar instance_token
        varchar category
        double  distance_to_ego_m
        int     lidar_points
        int     radar_return_count
        bool    is_ghost
        bool    is_visible_on_camera
        double  velocity_mps
        double  acceleration_mps2
        double  volume_variance_ratio
        bool    is_kinematic_outlier
        bool    is_scale_unstable
        double  severity
    }
```

Two SQL views sit on top: `view_slice_failure_rates` (failure % grouped by
weather / time of day / category) and `view_severe_outliers`
(`severity >= 0.5` joined with scene context).

## Rules enforced on real data

- **Ghost label**: category is `vehicle.*` or `human.pedestrian.*`, distance
  to ego < 35 m, and zero lidar returns inside the box after ground-plane
  filtering (lidar-frame z < -2.0 m is road surface, never box support).
- **Kinematic outlier**: acceleration exceeds the class cap
  (pedestrian 8, vehicle 12, default 12 m/s^2) between consecutive
  keyframes of one `instance_token`.
- **Scale unstable**: rigid-object volume changes > 15% between frames.
- **Underexposed frame**: mean camera intensity < 25/255.
- **Geometric drift**: a camera-visible box with 20+ lidar hits in 3D shows
  almost no projected returns inside its 2D footprint.
