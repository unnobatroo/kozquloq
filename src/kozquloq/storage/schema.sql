CREATE TABLE IF NOT EXISTS scenes (
    scene_token VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    weather VARCHAR NOT NULL,
    time_of_day VARCHAR NOT NULL,
    nbr_samples INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    sample_token VARCHAR PRIMARY KEY,
    scene_token VARCHAR REFERENCES scenes(scene_token),
    timestamp BIGINT NOT NULL,
    ego_speed_mps DOUBLE,
    camera_underexposed_count INTEGER DEFAULT 0,
    lidar_total_points INTEGER NOT NULL,
    radar_total_returns INTEGER NOT NULL,
    has_geometric_drift BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS annotation_audits (
    annotation_token VARCHAR PRIMARY KEY,
    sample_token VARCHAR REFERENCES samples(sample_token),
    instance_token VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    distance_to_ego_m DOUBLE NOT NULL,
    lidar_point_count INTEGER NOT NULL,
    radar_return_count INTEGER NOT NULL,
    is_ghost_label BOOLEAN NOT NULL,
    is_visible_on_camera BOOLEAN NOT NULL,
    velocity_mps DOUBLE,
    acceleration_mps2 DOUBLE,
    volume_variance_ratio DOUBLE,
    is_kinematic_outlier BOOLEAN NOT NULL,
    is_scale_unstable BOOLEAN NOT NULL,
    severity_score DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS sample_images (
    sample_token VARCHAR REFERENCES samples(sample_token),
    variant VARCHAR NOT NULL,  -- 'full' | 'boxes' | 'flagged'
    jpeg BLOB NOT NULL,
    PRIMARY KEY (sample_token, variant)
);

CREATE OR REPLACE VIEW view_slice_failure_rates AS
SELECT
    s.weather,
    s.time_of_day,
    a.category,
    COUNT(a.annotation_token) AS total_annotations,
    SUM(CASE WHEN a.is_ghost_label THEN 1 ELSE 0 END) AS ghost_labels_count,
    SUM(CASE WHEN a.is_kinematic_outlier THEN 1 ELSE 0 END) AS kinematic_outliers_count,
    ROUND(AVG(a.lidar_point_count), 2) AS avg_lidar_points,
    ROUND(SUM(CASE WHEN a.is_ghost_label OR a.is_kinematic_outlier THEN 1 ELSE 0 END) * 100.0 / COUNT(a.annotation_token), 2) AS failure_rate_pct
FROM annotation_audits a
JOIN samples sa ON a.sample_token = sa.sample_token
JOIN scenes s ON sa.scene_token = s.scene_token
GROUP BY s.weather, s.time_of_day, a.category;
