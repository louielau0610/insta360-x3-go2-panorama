import cv2
import numpy as np


X5_FACTORY_CANVAS = (10752, 5376)
X5_FACTORY_LEFT = (2650.814, 2690.430, 2687.930, 0.922, -0.294, 90.111)
X5_FACTORY_RIGHT = (2650.937, 8064.720, 2682.670, -0.982, -0.080, 90.003)
# Official-JPG-supervised fit from paired captures 003-005. Matrices map
# camera-local rays to panorama rays; radial tuples define rho/radius as
# a1*theta + a3*theta^3 + a5*theta^5.
X5_FITTED_LEFT_ROTATION = (
    (-0.9954594870, 0.0951861467, -0.0000854219),
    (0.0951798257, 0.9954029537, 0.0106658573),
    (0.0011002711, 0.0106092984, -0.9999431145),
)
X5_FITTED_RIGHT_ROTATION = (
    (0.9953706468, 0.0960658900, -0.0029360319),
    (-0.0960901713, 0.9953251775, -0.0097195696),
    (0.0019885873, 0.0099566981, 0.9999484535),
)
X5_FITTED_LEFT_RADIAL = (0.4917320864, 0.0196679358, -0.0010737689)
X5_FITTED_RIGHT_RADIAL = (0.4909367892, 0.0202281527, -0.0011700673)


def x5_factory_parameters(frame_width, frame_height):
    """Scale the X5 `p2` intrinsics to one local fisheye frame.

    The returned orientation tuples are retained verbatim from the camera's
    metadata. Their Euler-axis convention is not assumed by this helper.
    """
    lens_canvas = X5_FACTORY_CANVAS[1]
    scale_x = frame_width / lens_canvas
    scale_y = frame_height / lens_canvas
    scale_radius = (scale_x + scale_y) / 2

    def scale_lens(values, local_x_offset=0):
        radius, center_x, center_y, *orientation = values
        return {
            "center": ((center_x - local_x_offset) * scale_x, center_y * scale_y),
            "radius": radius * scale_radius,
            "orientation": tuple(orientation),
        }

    return {
        "left": scale_lens(X5_FACTORY_LEFT),
        "right": scale_lens(X5_FACTORY_RIGHT, local_x_offset=lens_canvas),
    }


class CalibratedDualFisheyeStitcher:
    """Stitch two upright fisheyes into a standard 2:1 equirectangular panorama.

    Lookup tables are generated once from per-lens radial curves and full
    rotations. Runtime work is two remaps plus dynamic or weighted overlap.
    """

    @classmethod
    def from_x5_factory(
        cls, frame_width, frame_height, fov=190, output_width=960, output_height=480,
        balance_exposure=True, blend_mode="dynamic_seam", seam_temporal=0.8, seam_update_interval=3,
    ):
        """Build the X5 preset from its `p2` intrinsics.

        Factory circle geometry is combined with the fitted full rotations and
        fifth-order radial curves. The raw orientation tuple remains available
        through :func:`x5_factory_parameters` for diagnostics.
        """
        factory = x5_factory_parameters(frame_width, frame_height)
        left, right = factory["left"], factory["right"]
        return cls(
            frame_width,
            frame_height,
            fov=fov,
            output_width=output_width,
            output_height=output_height,
            left_center=left["center"],
            right_center=right["center"],
            left_radius=left["radius"],
            right_radius=right["radius"],
            left_yaw=180 + left["orientation"][1],
            right_yaw=right["orientation"][1],
            left_pitch=left["orientation"][0],
            right_pitch=right["orientation"][0],
            left_rotation=X5_FITTED_LEFT_ROTATION,
            right_rotation=X5_FITTED_RIGHT_ROTATION,
            left_radial=X5_FITTED_LEFT_RADIAL,
            right_radial=X5_FITTED_RIGHT_RADIAL,
            balance_exposure=balance_exposure,
            blend_mode=blend_mode,
            seam_temporal=seam_temporal,
            seam_update_interval=seam_update_interval,
        )

    def __init__(
        self,
        frame_width,
        frame_height,
        fov=190,
        output_width=960,
        output_height=480,
        left_center=None,
        right_center=None,
        left_radius=None,
        right_radius=None,
        left_fov=None,
        right_fov=None,
        left_yaw=180,
        right_yaw=0,
        left_pitch=0,
        right_pitch=0,
        left_roll=0,
        right_roll=0,
        left_rotation=None,
        right_rotation=None,
        left_radial=None,
        right_radial=None,
        balance_exposure=True,
        blend_mode="weighted",
        seam_temporal=0.8,
        seam_update_interval=3,
    ):
        if output_width != output_height * 2:
            raise ValueError("Equirectangular output must use a 2:1 aspect ratio")
        if fov <= 180 or fov > 220:
            raise ValueError("fov must be greater than 180 and no more than 220 degrees")
        if blend_mode not in ("weighted", "dynamic_seam"):
            raise ValueError("blend_mode must be 'weighted' or 'dynamic_seam'")
        if not 0 <= seam_temporal < 1:
            raise ValueError("seam_temporal must be in [0, 1)")
        if seam_update_interval < 1:
            raise ValueError("seam_update_interval must be at least 1")

        self.frame_width = frame_width
        self.frame_height = frame_height
        self.fov = fov
        self.output_width = output_width
        self.output_height = output_height
        default_center = (frame_width / 2, frame_height / 2)
        self.left_center = left_center or default_center
        self.right_center = right_center or default_center
        default_radius = min(frame_width, frame_height) / 2
        self.left_radius = left_radius or default_radius
        self.right_radius = right_radius or default_radius
        self.left_fov = left_fov or fov
        self.right_fov = right_fov or fov
        self.left_yaw = left_yaw
        self.right_yaw = right_yaw
        self.left_pitch = left_pitch
        self.right_pitch = right_pitch
        self.left_roll = left_roll
        self.right_roll = right_roll
        self.left_rotation = left_rotation
        self.right_rotation = right_rotation
        self.left_radial = left_radial
        self.right_radial = right_radial
        self.balance_exposure = balance_exposure
        self.blend_mode = blend_mode
        self.seam_temporal = seam_temporal
        self.seam_update_interval = seam_update_interval
        self.last_exposure_gains = (1.0, 1.0)
        self.last_seams = None
        self.last_seam_alpha = None
        self.seam_frame_index = 0
        self.left_map_x, self.left_map_y, self.left_weight = self.precompute_lens_lut(
            self.left_center, self.left_radius, self.left_fov, self.left_yaw, self.left_pitch, self.left_roll,
            self.left_rotation, self.left_radial,
        )
        self.right_map_x, self.right_map_y, self.right_weight = self.precompute_lens_lut(
            self.right_center, self.right_radius, self.right_fov, self.right_yaw, self.right_pitch, self.right_roll,
            self.right_rotation, self.right_radial,
        )
        self.left_valid = self.left_weight > 0
        self.right_valid = self.right_weight > 0
        self.seam_scale = 4
        self.seam_small_size = (output_width // self.seam_scale, output_height // self.seam_scale)
        self.seam_overlap = cv2.resize(
            (self.left_valid & self.right_valid).astype(np.uint8),
            self.seam_small_size,
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)
        self.seam_x = np.arange(output_width, dtype=np.float32)[None, :]

    def precompute_lens_lut(self, center, radius, fov, yaw, pitch, roll, rotation=None, radial=None):
        """Map equirectangular directions through one calibrated fisheye lens."""
        longitude = np.linspace(-np.pi, np.pi, self.output_width, endpoint=False)
        latitude = np.linspace(np.pi / 2, -np.pi / 2, self.output_height)
        longitude, latitude = np.meshgrid(longitude, latitude)
        direction = np.stack(
            (np.cos(latitude) * np.sin(longitude), np.sin(latitude), np.cos(latitude) * np.cos(longitude)),
            axis=-1,
        )
        if rotation is None:
            yaw, pitch, roll = np.radians((yaw, pitch, roll))
            forward = np.array((np.sin(yaw) * np.cos(pitch), np.sin(pitch), np.cos(yaw) * np.cos(pitch)))
            right = np.array((np.cos(yaw), 0, -np.sin(yaw)))
            up = np.cross(forward, right)
            right, up = right * np.cos(roll) + up * np.sin(roll), up * np.cos(roll) - right * np.sin(roll)
            rotation = np.column_stack((right, up, forward))
        local = direction @ np.asarray(rotation)
        local_x = local[..., 0]
        local_y = local[..., 1]
        cos_angle = local[..., 2]
        angle = np.arccos(np.clip(cos_angle, -1, 1))
        if radial is None:
            half_fov = np.radians(fov / 2)
            normalized_radius = angle / half_fov
        else:
            a1, a3, a5 = radial
            normalized_radius = a1 * angle + a3 * angle**3 + a5 * angle**5
        radial_distance = radius * normalized_radius
        sine_angle = np.sin(angle)
        safe_sine = np.where(sine_angle > 1e-8, sine_angle, 1)
        map_x = center[0] + radial_distance * local_x / safe_sine
        map_y = center[1] - radial_distance * local_y / safe_sine
        valid = (normalized_radius >= 0) & (normalized_radius <= 1)
        map_x = np.where(valid, map_x, -1).astype(np.float32)
        map_y = np.where(valid, map_y, -1).astype(np.float32)
        weight = np.clip(1 - normalized_radius, 0, None).astype(np.float32)
        return map_x, map_y, weight

    def exposure_gains(self, left, right):
        """Estimate bounded per-lens gains from only their spherical overlap."""
        overlap = (self.left_weight > 0) & (self.right_weight > 0)
        left_luma = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        right_luma = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
        valid = overlap & (left_luma > 4) & (right_luma > 4)
        if np.count_nonzero(valid) < 100:
            return 1.0, 1.0
        left_level = np.median(left_luma[valid])
        right_level = np.median(right_luma[valid])
        target = np.sqrt(left_level * right_level)
        left_gain = float(np.clip(target / left_level, 0.8, 1.25))
        right_gain = float(np.clip(target / right_level, 0.8, 1.25))
        return left_gain, right_gain

    @staticmethod
    def minimum_cost_seam(cost, valid):
        """Return a smooth top-to-bottom path through one low-resolution band."""
        height, width = cost.shape
        penalty = float(np.max(cost) + 255)
        center_bias = 0.5 * np.abs(np.arange(width, dtype=np.float32) - (width - 1) / 2)
        row_cost = np.where(valid, cost, penalty) + center_bias[None, :]
        accumulated = row_cost.astype(np.float32)
        parents = np.zeros((height, width), np.int8)
        for row in range(1, height):
            previous = accumulated[row - 1]
            candidates = np.stack(
                (
                    np.pad(previous[:-1], (1, 0), constant_values=np.inf),
                    previous,
                    np.pad(previous[1:], (0, 1), constant_values=np.inf),
                )
            )
            parent = np.argmin(candidates, axis=0)
            parents[row] = parent.astype(np.int8) - 1
            accumulated[row] = row_cost[row] + np.min(candidates, axis=0)
        path = np.empty(height, np.int32)
        path[-1] = int(np.argmin(accumulated[-1]))
        for row in range(height - 1, 0, -1):
            path[row - 1] = np.clip(path[row] + parents[row, path[row]], 0, width - 1)
        return path

    def dynamic_seams(self, left, right):
        """Find two temporally smoothed content-aware seam paths."""
        left_small = cv2.resize(left, self.seam_small_size, interpolation=cv2.INTER_AREA)
        right_small = cv2.resize(right, self.seam_small_size, interpolation=cv2.INTER_AREA)
        if left_small.dtype != np.uint8:
            left_small = np.clip(left_small, 0, 255).astype(np.uint8)
            right_small = np.clip(right_small, 0, 255).astype(np.uint8)
        left_gray = cv2.cvtColor(left_small, cv2.COLOR_BGR2GRAY)
        right_gray = cv2.cvtColor(right_small, cv2.COLOR_BGR2GRAY)
        left_edge = cv2.Laplacian(left_gray, cv2.CV_32F)
        right_edge = cv2.Laplacian(right_gray, cv2.CV_32F)
        cost = cv2.absdiff(left_gray, right_gray).astype(np.float32)
        cost += 0.2 * (np.abs(left_edge) + np.abs(right_edge))
        left_f = left_gray.astype(np.float32)
        right_f = right_gray.astype(np.float32)
        bad_left = np.clip(right_f - left_f - 12, 0, None)
        bad_right = np.clip(left_f - right_f - 12, 0, None)
        content_overlap = self.seam_overlap & (left_gray > 4) & (right_gray > 4)
        small_width, _ = self.seam_small_size
        # A 190-degree dual-fisheye pair has only about ten degrees of true
        # overlap. Keep the optimizer inside that support instead of letting it
        # select a dark lens periphery merely because its pixel difference is low.
        half_band = max(4, small_width // 32)
        seams = []
        for seam_index, center in enumerate((small_width // 4, 3 * small_width // 4)):
            start, stop = center - half_band, center + half_band
            left_penalty = bad_left[:, start:stop]
            right_penalty = bad_right[:, start:stop]
            if seam_index == 0:
                region_cost = np.cumsum(left_penalty, axis=1)
                region_cost += np.cumsum(right_penalty[:, ::-1], axis=1)[:, ::-1]
            else:
                region_cost = np.cumsum(right_penalty, axis=1)
                region_cost += np.cumsum(left_penalty[:, ::-1], axis=1)[:, ::-1]
            band_cost = cost[:, start:stop] + 0.2 * region_cost
            path = self.minimum_cost_seam(band_cost, content_overlap[:, start:stop]) + start
            path = cv2.resize(path.astype(np.float32).reshape(-1, 1), (1, self.output_height), interpolation=cv2.INTER_LINEAR)[:, 0]
            seams.append(path * self.seam_scale)
        seams = np.stack(seams)
        if self.last_seams is not None:
            seams = self.seam_temporal * self.last_seams + (1 - self.seam_temporal) * seams
        self.last_seams = seams
        return seams

    def dynamic_seam_alpha(self, left, right):
        """Return a cached selection mask, refreshing its paths at a fixed cadence."""
        refresh = self.last_seam_alpha is None or self.seam_frame_index % self.seam_update_interval == 0
        self.seam_frame_index += 1
        if not refresh:
            return self.last_seam_alpha
        seams = self.dynamic_seams(left, right)
        alpha = (self.seam_x <= seams[0, :, None]) | (self.seam_x >= seams[1, :, None])
        alpha = np.where(self.left_valid & ~self.right_valid, 1, alpha)
        alpha = np.where(self.right_valid & ~self.left_valid, 0, alpha)
        left_u8 = left if left.dtype == np.uint8 else np.clip(left, 0, 255).astype(np.uint8)
        right_u8 = right if right.dtype == np.uint8 else np.clip(right, 0, 255).astype(np.uint8)
        left_luma = cv2.cvtColor(left_u8, cv2.COLOR_BGR2GRAY)
        right_luma = cv2.cvtColor(right_u8, cv2.COLOR_BGR2GRAY)
        alpha = np.where((left_luma < 12) & (right_luma > 24), 0, alpha)
        alpha = np.where((right_luma < 12) & (left_luma > 24), 1, alpha).astype(bool)
        self.last_seam_alpha = alpha
        return alpha

    @staticmethod
    def seam_blend(left, right, alpha):
        """Select pixels from two images with one vectorized spatial mask."""
        return np.where(alpha[..., None], left, right)

    def stitch_frames(self, left_frame, right_frame):
        """Return a 2:1 equirectangular panorama from the two raw fisheyes."""
        left = cv2.remap(left_frame, self.left_map_x, self.left_map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        right = cv2.remap(right_frame, self.right_map_x, self.right_map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        if self.balance_exposure:
            self.last_exposure_gains = self.exposure_gains(left, right)
            left = left.astype(np.float32) * self.last_exposure_gains[0]
            right = right.astype(np.float32) * self.last_exposure_gains[1]
        else:
            self.last_exposure_gains = (1.0, 1.0)
        if self.blend_mode == "dynamic_seam":
            alpha = self.dynamic_seam_alpha(left, right)
            output = self.seam_blend(left, right, alpha)
        else:
            total_weight = self.left_weight + self.right_weight
            total_weight = np.where(total_weight > 0, total_weight, 1)
            output = (
                left.astype(np.float32) * self.left_weight[..., None]
                + right.astype(np.float32) * self.right_weight[..., None]
            ) / total_weight[..., None]
        if output.dtype == np.uint8:
            return output
        return np.clip(np.rint(output), 0, 255).astype(np.uint8)
