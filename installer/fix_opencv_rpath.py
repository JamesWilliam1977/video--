"""Prepare OpenCV dylibs for macOS cx_Freeze packaging.

OpenCV 4.x dylibs commonly reference each other through @rpath. cx_Freeze 6.4
can fail while scanning _openshot.so before OpenShot's post-freeze rpath fixer
gets a chance to run, so stage the OpenCV dylibs and rewrite OpenCV references
to concrete paths before freeze starts.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys


def run(command):
    print(" ".join(command))
    subprocess.check_call(command)


def otool_dependencies(path):
    output = subprocess.check_output(["otool", "-L", path], text=True)
    dependencies = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        dependencies.append(line.split(" ", 1)[0])
    return dependencies


def opencv_rpath_dependencies(path):
    return [
        dependency
        for dependency in otool_dependencies(path)
        if dependency.startswith("@rpath/")
        and "opencv" in os.path.basename(dependency)
        and dependency.endswith(".dylib")
    ]


def stage_opencv_dylibs(opencv_root, stage_dir):
    opencv_lib_dir = os.path.join(opencv_root, "lib")
    if not os.path.isdir(opencv_lib_dir):
        raise FileNotFoundError(f"OpenCV lib directory not found: {opencv_lib_dir}")

    os.makedirs(stage_dir, exist_ok=True)
    dylibs = sorted(glob.glob(os.path.join(opencv_lib_dir, "*.dylib")))
    if not dylibs:
        raise FileNotFoundError(f"No OpenCV dylibs found in: {opencv_lib_dir}")

    for dylib in dylibs:
        staged = os.path.join(stage_dir, os.path.basename(dylib))
        print(f"Staging OpenCV dylib: {dylib} -> {staged}")
        shutil.copy2(dylib, staged)


def rewrite_opencv_dependencies(path, stage_dir):
    for dependency in opencv_rpath_dependencies(path):
        dependency_name = os.path.basename(dependency)
        staged_dependency = os.path.join(stage_dir, dependency_name)
        if not os.path.exists(staged_dependency):
            raise FileNotFoundError(
                f"Missing staged OpenCV dependency for {path}: {staged_dependency}"
            )
        print(f"Rewriting OpenCV dependency in {path}: {dependency} -> {staged_dependency}")
        run(["install_name_tool", "-change", dependency, staged_dependency, path])


def rewrite_opencv_ids(stage_dir):
    for dylib in sorted(glob.glob(os.path.join(stage_dir, "*.dylib"))):
        if "opencv" not in os.path.basename(dylib):
            continue
        run(["install_name_tool", "-id", dylib, dylib])


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("binding", help="Path to _openshot.so")
    parser.add_argument("opencv_root", help="OpenCV install prefix")
    parser.add_argument("stage_dir", help="Directory for staged OpenCV dylibs")
    args = parser.parse_args(argv)

    binding = os.path.abspath(args.binding)
    opencv_root = os.path.abspath(args.opencv_root)
    stage_dir = os.path.abspath(args.stage_dir)

    if not os.path.exists(binding):
        raise FileNotFoundError(f"OpenShot Python binding not found: {binding}")

    stage_opencv_dylibs(opencv_root, stage_dir)
    for path in [binding] + sorted(glob.glob(os.path.join(stage_dir, "*.dylib"))):
        rewrite_opencv_dependencies(path, stage_dir)
    rewrite_opencv_ids(stage_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
