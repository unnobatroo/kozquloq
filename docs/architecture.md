# Architecture

Kozquloq has one job: read nuScenes sensor logs, check every 3D annotation
against what the sensors actually saw, and produce two outputs - a mask of
invalid annotation tokens, and overlay images showing the flags visually.
Everything in the design exists to serve that pipeline.

## The data contracts

Three frozen dataclasses in `src/kozquloq/types.py` carry everything between
stages. They are immutable on purpose - an auditor must never mutate the
frame it is auditing, only append findings.

- `SceneMeta` - the scene: token, name, weather, time of day.
- `FrameBundle` - one synchronized keyframe: the camera image, the LiDAR
  cloud, the annotation boxes, and the four SE(3) transforms plus intrinsics
  needed to go `lidar -> ego -> global -> ego -> camera`. The detour through
  the ego frames is not ceremony: the sensors fire at different timestamps
  and the car moved in between.
- `AnnBox` - one annotation in the global frame. nuScenes convention: local
  x is length, y is width, z is height. Getting this wrong silently corrupts
  point counts and manufactures ghosts.

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

The two seams that matter are `BaseAuditor` and `AuditStore`. Both are
dependency-injected into `AuditPipeline`, so you can swap the store or add an
auditor without touching pipeline code.

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
        +query_numpy(sql, params)*
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

Auditor order is load-bearing. `GeometricAuditor` fills `findings.boxes`,
`KinematicAuditor` refines those results in place (velocity and acceleration
are computed per instance across frames, so it keeps a tracker and resets it
per scene), and `SensorHealthAuditor` reads the box results for its drift
check. The kinematic state is also why `viz` runs the auditors over the
whole scene instead of just the target frame - a teleport only shows up if
the tracker saw the frames before it.

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

The whole audit runs inside one transaction. A killed scan rolls back instead
of leaving a half-written database that still computes a healthy grade -
a partial dataset would otherwise look better than it is.

## Storage schema

Two tables is the whole database. `samples` is per-keyframe context;
`audits` is one row per annotation with the flags and the severity.

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

Two views sit on top for the summary tables:
`view_slice_failure_rates` (failure % grouped by weather, time of day, and
category) and `view_severe_outliers` (`severity >= 0.5` joined with scene
context). All queries are parameterized - there is no dynamic SQL surface.

## The rules it enforces

- **Ghost label** - the box claims a `vehicle.*` or `human.pedestrian.*`
  category, sits within 35 m of the ego, and contains zero LiDAR returns
  after the ground plane is removed (anything below lidar z = -2.0 m is road
  surface, not object evidence). Ghosts score 0.55 and land in the mask.
- **Kinematic outlier** - acceleration between consecutive keyframes of one
  `instance_token` exceeds the class cap: 8 m/s² for pedestrians, 12 for
  vehicles. That is a tracking hop or a jittered center, not physics.
  Severity 0.25, so it downweights rather than masks by default.
- **Scale unstable** - a rigid object whose volume changed more than 15%
  between frames. Severity 0.20.
- **Underexposed frame** - mean camera intensity below 25/255.
- **Geometric drift** - a camera-visible box with plenty of 3D LiDAR hits
  shows almost no projected returns inside its 2D footprint, meaning the
  extrinsics went stale.

A flagged annotation can stack severities - a box that is both a ghost and a
kinematic outlier scores 0.80 and clearly belongs out of the training set.
