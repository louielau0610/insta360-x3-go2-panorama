from setuptools import find_packages, setup


setup(
    name="x5-360-pipeline",
    version="0.1.0",
    description="Insta360 X5 dual-fisheye stitching and complete cubemap output",
    python_requires=">=3.10",
    install_requires=["numpy>=1.24", "opencv-python>=4.5", "py360convert>=1.0.4"],
    py_modules=["dual_fisheye_stitcher"],
    packages=find_packages(include=["x5_360_pipeline*"]),
)
