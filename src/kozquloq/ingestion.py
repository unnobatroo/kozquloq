"""Ingestion & synchronization: fixture dirs and real nuScenes datasets.

Both loaders yield (SceneMeta, list[FrameBundle]) pairs so the audit pipeline
never cares where frames came from.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, cast

import numpy as np

from kozquloq.types import AnnBox, FrameBundle, SceneMeta

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

    from numpy.typing import NDArray


def _se3(rotation: NDArray[np.float64], translation: NDArray[np.float64]) -> NDArray[np.float64]:
    T = np.eye(4)
    T[:3, :3] = rotation
    T[:3, 3] = translation
    return T


def load_fixture_frames(root: str) -> Iterator[tuple[SceneMeta, list[FrameBundle]]]:
    """Load the fixture format written by synthetic.dump_fixture_dataset."""
    import cv2

    with open(os.path.join(root, "fixture.json")) as fh:
        meta = json.load(fh)

    by_scene: dict[str, list[FrameBundle]] = {}
    scenes: dict[str, SceneMeta] = {}
    for s in meta["scenes"]:
        scenes[s["token"]] = SceneMeta(
            s["token"], s["name"], s["description"], s["weather"], s["time_of_day"]
        )
        by_scene[s["token"]] = []

    for s in meta["samples"]:
        image = cast(
            "NDArray[np.uint8]",
            cv2.cvtColor(cv2.imread(os.path.join(root, s["image"])), cv2.COLOR_BGR2RGB),
        )
        points = np.load(os.path.join(root, s["points"]))[:, :3]
        boxes = [
            AnnBox(
                token=b["token"],
                instance_token=b["instance_token"],
                category=b["category"],
                center=np.asarray(b["center"], dtype=np.float64),
                size=np.asarray(b["size"], dtype=np.float64),
                orientation=np.asarray(b["orientation"], dtype=np.float64),
                radar_returns=b.get("radar_returns", 0),
            )
            for b in s["boxes"]
        ]
        by_scene[s["scene_token"]].append(
            FrameBundle(
                sample_token=s["sample_token"],
                scene_token=s["scene_token"],
                timestamp_us=int(s["timestamp_us"]),
                ego_speed_mps=float(s.get("ego_speed_mps", 0.0)),
                image=image,
                lidar_points=points,
                radar_total_returns=int(s["radar_total_returns"]),
                boxes=boxes,
                T_lidar_to_ego=np.asarray(s["T_lidar_to_ego"]),
                T_ego_lidar_to_global=np.asarray(s["T_ego_lidar_to_global"]),
                T_ego_cam_to_global=np.asarray(s["T_ego_cam_to_global"]),
                T_cam_to_ego=np.asarray(s["T_cam_to_ego"]),
                K=np.asarray(s["K"]),
            )
        )

    for token, frames in by_scene.items():
        frames.sort(key=lambda f: f.timestamp_us)
        yield scenes[token], frames


def _nuscenes_frame(
    nusc: Any, sample: dict[str, Any], dataroot: str, prev: FrameBundle | None
) -> FrameBundle:
    """Build one synchronized FrameBundle from a nuScenes sample record."""
    import cv2
    from nuscenes.utils.data_classes import LidarPointCloud

    from kozquloq.auditors.geometry import quat_to_rot

    def se3_of(record: dict[str, Any]) -> NDArray[np.float64]:
        return _se3(quat_to_rot(np.asarray(record["rotation"])), np.asarray(record["translation"]))

    lidar_sd = nusc.get("sample_data", sample["data"]["LIDAR_TOP"])
    cam_sd = nusc.get("sample_data", sample["data"]["CAM_FRONT"])

    pc = LidarPointCloud.from_file(os.path.join(dataroot, lidar_sd["filename"]))
    points = pc.points[:3].T.astype(np.float64)

    img_bgr = cv2.imread(os.path.join(dataroot, cam_sd["filename"]))
    image = cast("NDArray[np.uint8]", cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

    lidar_calib = nusc.get("calibrated_sensor", lidar_sd["calibrated_sensor_token"])
    lidar_pose = nusc.get("ego_pose", lidar_sd["ego_pose_token"])
    cam_calib = nusc.get("calibrated_sensor", cam_sd["calibrated_sensor_token"])
    cam_pose = nusc.get("ego_pose", cam_sd["ego_pose_token"])

    boxes = []
    radar_hits = 0
    for ann_token in sample["anns"]:
        ann = nusc.get("sample_annotation", ann_token)
        boxes.append(
            AnnBox(
                token=ann["token"],
                instance_token=ann["instance_token"],
                category=ann["category_name"],
                center=np.asarray(ann["translation"]),
                size=np.asarray(ann["size"]),
                orientation=np.asarray(ann["rotation"]),
                radar_returns=int(ann.get("num_radar_pts", 0)),
            )
        )
        radar_hits += int(ann.get("num_radar_pts", 0))

    speed = 0.0
    if prev is not None:
        dt = (lidar_sd["timestamp"] - prev.timestamp_us) / 1e6
        if dt > 0:
            d = np.linalg.norm(
                np.asarray(lidar_pose["translation"]) - prev.T_ego_lidar_to_global[:3, 3]
            )
            speed = float(d / dt)

    return FrameBundle(
        sample_token=sample["token"],
        scene_token=sample["scene_token"],
        timestamp_us=int(lidar_sd["timestamp"]),
        ego_speed_mps=speed,
        image=image,
        lidar_points=points,
        radar_total_returns=radar_hits,
        boxes=boxes,
        T_lidar_to_ego=se3_of(lidar_calib),
        T_ego_lidar_to_global=se3_of(lidar_pose),
        T_ego_cam_to_global=se3_of(cam_pose),
        T_cam_to_ego=se3_of(cam_calib),
        K=np.asarray(cam_calib["camera_intrinsic"]),
    )


def load_nuscenes_frames(
    dataroot: str, version: str = "v1.0-mini", max_samples_per_scene: int | None = None
) -> Iterator[tuple[SceneMeta, list[FrameBundle]]]:
    """Load a real nuScenes dataset via the devkit (imported lazily)."""
    from nuscenes.nuscenes import NuScenes

    nusc = NuScenes(version=version, dataroot=dataroot, verbose=False)

    def weather_of(scene: dict[str, Any]) -> str:
        desc = scene["description"].lower()
        for w in ("rain", "snow", "fog", "night"):
            if w in desc:
                return w
        return "clear"

    for scene in nusc.scene:
        meta = SceneMeta(
            token=scene["token"],
            name=scene["name"],
            description=scene["description"],
            weather=weather_of(scene),
            time_of_day="night" if "night" in scene["description"].lower() else "day",
        )
        frames: list[FrameBundle] = []
        sample_token = scene["first_sample_token"]
        while sample_token and (not max_samples_per_scene or len(frames) < max_samples_per_scene):
            sample = nusc.get("sample", sample_token)
            sample_token = sample["next"]
            frames.append(_nuscenes_frame(nusc, sample, dataroot, frames[-1] if frames else None))
        yield meta, frames


def load_frames(
    dataroot: str, version: str = "v1.0-mini"
) -> Iterator[tuple[SceneMeta, list[FrameBundle]]]:
    """Dispatch: fixture dir (fixture.json present) or real nuScenes."""
    if os.path.exists(os.path.join(dataroot, "fixture.json")):
        yield from load_fixture_frames(dataroot)
    else:
        yield from load_nuscenes_frames(dataroot, version)
