"""
setup.py — RemoteCameraMonitoring
==================================
Install:    pip install .
Develop:    pip install -e .
Run server: python -m RemoteCameraMonitoring.server
Run GUI:    python -m RemoteCameraMonitoring
"""

from setuptools import setup, find_packages

setup(
    name="RemoteCameraMonitoring",
    version="1.0.0",
    author="Jesus Urdiales",
    description="Stream and monitor your camera remotely over a local network or internet via WebRTC.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    # Ship templates and static resources inside the package
    package_data={
        "RemoteCameraMonitoring": [
            "templates/*.html",
            "resources/*.png",
            "resources/*.svg",
            "resources/*.ico",
        ],
    },
    install_requires=[
        "flask>=2.3",
        "flask-sock>=0.2",
        "opencv-python>=4.8",
        "numpy>=1.24",
        "aiortc>=1.9.0",
        "av>=12.0.0",
        "sounddevice>=0.4.6",
        'pygrabber>=0.2; sys_platform == "win32"',
        "PySide6>=6.0.0",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "remotecameraserver = RemoteCameraMonitoring.__main__:server",
            "remotecamera = RemoteCameraMonitoring.__main__:main",
            "remotecamera-legacy = RemoteCameraMonitoring.__main__:legacy",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
