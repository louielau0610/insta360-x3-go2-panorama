from setuptools import find_packages, setup


setup(
    name="x5-360-pipeline",
    version="0.1.0",
    description="Insta360 X5 and Unitree GO2 raw ROS2 capture and 360-degree processing",
    python_requires=">=3.8",
    install_requires=["numpy>=1.24", "opencv-python-headless>=4.5", "py360convert>=1.0.4"],
    py_modules=["dual_fisheye_stitcher"],
    packages=find_packages(include=["x5_360_pipeline*", "go2_experiment*", "x5_ros*"]),
    entry_points={
        "console_scripts": [
            "go2-collect=go2_experiment.cli:main",
            "x5-ros-publish=x5_ros.publisher:main",
            "x5-ros-export=x5_ros.export_pairs:main",
            "x5-ros-postprocess=x5_ros.postprocess_pairs:main",
        ]
    },
)
