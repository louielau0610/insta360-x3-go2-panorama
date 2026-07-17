from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from py360convert.utils import EquirecSampler, cube_h2dict, mode_to_order

from dual_fisheye_stitcher import CalibratedDualFisheyeStitcher


@dataclass
class CubemapFrame:
    """One BGR panorama and its complete six-face cubemap."""

    panorama: np.ndarray
    cubemap_horizon: np.ndarray
    faces: dict[str, np.ndarray]
    jpeg_faces: dict[str, np.ndarray] | None = None


class X5CubemapPipeline:
    """Convert X5 side-by-side fisheyes into a panorama and F/R/B/L/U/D faces."""

    face_order = "FRBLUD"

    def __init__(
        self,
        fisheye_width,
        fisheye_height,
        panorama_width=1280,
        cube_face_width=512,
        balance_exposure=False,
        blend_mode="dynamic_seam",
        seam_update_interval=3,
    ):
        if panorama_width % 2:
            raise ValueError("panorama_width must be even for a 2:1 panorama")
        self.fisheye_width = fisheye_width
        self.fisheye_height = fisheye_height
        self.panorama_width = panorama_width
        self.panorama_height = panorama_width // 2
        self.cube_face_width = cube_face_width
        self.stitcher = CalibratedDualFisheyeStitcher.from_x5_factory(
            fisheye_width,
            fisheye_height,
            output_width=panorama_width,
            output_height=self.panorama_height,
            balance_exposure=balance_exposure,
            blend_mode=blend_mode,
            seam_update_interval=seam_update_interval,
        )
        self.cube_sampler = EquirecSampler.from_cubemap(
            cube_face_width,
            self.panorama_height,
            panorama_width,
            mode_to_order("bilinear"),
        )

    def process(self, left_frame, right_frame, encode_jpeg=False, jpeg_quality=85):
        """Process two BGR fisheye frames and return panorama plus six cube faces."""
        self._validate_fisheye(left_frame, "left_frame")
        self._validate_fisheye(right_frame, "right_frame")
        panorama = self.stitcher.stitch_frames(left_frame, right_frame)
        cubemap_horizon = np.stack(
            [self.cube_sampler(panorama[..., channel]) for channel in range(3)],
            axis=-1,
        )
        faces = cube_h2dict(cubemap_horizon)
        jpeg_faces = None
        if encode_jpeg:
            jpeg_faces = {
                name: cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])[1]
                for name, frame in faces.items()
            }
        return CubemapFrame(panorama, cubemap_horizon, faces, jpeg_faces)

    def process_side_by_side(self, frame, encode_jpeg=False, jpeg_quality=85):
        """Process one BGR frame containing left and right square fisheyes side by side."""
        expected_shape = (self.fisheye_height, self.fisheye_width * 2)
        if frame.ndim != 3 or frame.shape[:2] != expected_shape or frame.shape[2] != 3:
            raise ValueError(f"frame must be a BGR image with shape {expected_shape + (3,)}")
        return self.process(
            frame[:, : self.fisheye_width],
            frame[:, self.fisheye_width :],
            encode_jpeg,
            jpeg_quality,
        )

    def _validate_fisheye(self, frame, name):
        expected_shape = (self.fisheye_height, self.fisheye_width, 3)
        if frame.ndim != 3 or frame.shape != expected_shape:
            raise ValueError(f"{name} must be a BGR image with shape {expected_shape}")
