CREATE TABLE IF NOT EXISTS samples (
    sample_token VARCHAR PRIMARY KEY,
    scene_name VARCHAR NOT NULL,
    weather VARCHAR NOT NULL,
    time_of_day VARCHAR NOT NULL,
    timestamp BIGINT NOT NULL,
    ego_speed_mps DOUBLE,
    camera_underexposed_count INTEGER DEFAULT 0,
    lidar_total_points INTEGER NOT NULL,
    radar_total_returns INTEGER NOT NULL,
    has_geometric_drift BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS audits (
    annotation_token VARCHAR PRIMARY KEY,
    sample_token VARCHAR REFERENCES samples(sample_token),
    instance_token VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    distance_to_ego_m DOUBLE NOT NULL,
    lidar_points INTEGER NOT NULL,
    radar_return_count INTEGER NOT NULL,
    is_ghost BOOLEAN NOT NULL,
    is_visible_on_camera BOOLEAN NOT NULL,
    velocity_mps DOUBLE,
    acceleration_mps2 DOUBLE,
    volume_variance_ratio DOUBLE,
    is_kinematic_outlier BOOLEAN NOT NULL,
    is_scale_unstable BOOLEAN NOT NULL,
    severity DOUBLE NOT NULL
);

CREATE OR REPLACE VIEW view_slice_failure_rates AS
SELECT
    s.weather,
    s.time_of_day,
    a.category,
    COUNT(a.annotation_token) AS total_annotations,
    SUM(CASE WHEN a.is_ghost THEN 1 ELSE 0 END) AS ghost_labels_count,
    SUM(CASE WHEN a.is_kinematic_outlier THEN 1 ELSE 0 END) AS kinematic_outliers_count,
    ROUND(AVG(a.lidar_points), 2) AS avg_lidar_points,
    ROUND(
        SUM(CASE WHEN a.is_ghost OR a.is_kinematic_outlier OR a.is_scale_unstable THEN 1 ELSE 0 END)
            * 100.0 / COUNT(a.annotation_token),
        2
    ) AS failure_rate_pct
FROM audits a
JOIN samples s ON a.sample_token = s.sample_token
GROUP BY s.weather, s.time_of_day, a.category;

CREATE OR REPLACE VIEW view_severe_outliers AS
SELECT a.*, s.scene_name, s.weather, s.time_of_day
FROM audits a
JOIN samples s ON a.sample_token = s.sample_token
WHERE a.severity >= 0.5;
