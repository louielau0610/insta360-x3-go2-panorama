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
    rotations. Runtime work is two remaps plus a weighted overlap blend.
    """

    @classmethod
    def from_x5_factory(cls, frame_width, frame_height, fov=190, output_width=960, output_height=480, balance_exposure=True):
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
    ):
        if output_width != output_height * 2:
            raise ValueError("Equirectangular output must use a 2:1 aspect ratio")
        if fov <= 180 or fov > 220:
            raise ValueError("fov must be greater than 180 and no more than 220 degrees")

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
        self.last_exposure_gains = (1.0, 1.0)
        self.left_map_x, self.left_map_y, self.left_weight = self.precompute_lens_lut(
            self.left_center, self.left_radius, self.left_fov, self.left_yaw, self.left_pitch, self.left_roll,
            self.left_rotation, self.left_radial,
        )
        self.right_map_x, self.right_map_y, self.right_weight = self.precompute_lens_lut(
            self.right_center, self.right_radius, self.right_fov, self.right_yaw, self.right_pitch, self.right_roll,
            self.right_rotation, self.right_radial,
        )

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
        total_weight = self.left_weight + self.right_weight
        total_weight = np.where(total_weight > 0, total_weight, 1)
        output = (left.astype(np.float32) * self.left_weight[..., None] + right.astype(np.float32) * self.right_weight[..., None])
        return np.rint(output / total_weight[..., None]).astype(np.uint8)
