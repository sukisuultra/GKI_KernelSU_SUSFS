#!/usr/bin/env python3
import re
import sys
from pathlib import Path

NOVA_HASH = b"2b3d2c321a6b61090565e417cb020bfac1f4330d104481e80ed65aff632d94d4"
NOVA_PACKAGE = b"app.nova.utility"
POLICY_MARKER = b"NOVA_UTILITY_EXCLUSIVE_MANAGER_V1_CERTMAX_1280"
FORBIDDEN = {
    b"947ae944f3de4ed4c21a7e4f7953ecf351bfa2b36239da37a34111ad29993eef": "official SukiSU",
    b"f415f4ed9435427e1fdf7f1fccd4dbc07b3d6b8751e4dbcec6f19671f427870b": "RKSU",
    b"c371061b19d8c7d7d6133c6a9bafe198fa944e50c1b31c9d8daa8d7f1fc2d2d6": "KSU",
    b"52d52d8c8bfbe53dc2b6ff1c613184e2c03013e090fe8905d8e3d5dc2658c2e4": "WKSU",
    b"484fcba6e6c43b1fb09700633bf2fb4758f13cb0b2f4457b80d075084b26c588": "KowSU",
    b"79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7": "KSUN",
    b"7e0c6d7278a3bb8e364e0fcba95afaf3666cf5ff3c245a3b63c8833bd0445cc4": "MKSU",
}

if len(sys.argv) != 2:
    raise SystemExit("usage: verify-nova-exclusive-image.py <Image>")

path = Path(sys.argv[1])
if not path.is_file() or path.stat().st_size == 0:
    raise SystemExit(f"invalid Image: {path}")

data = path.read_bytes()

for needle, name in [
    (NOVA_HASH, "Nova Utility certificate SHA256"),
    (NOVA_PACKAGE, "Nova Utility package lock"),
    (POLICY_MARKER, "exclusive runtime policy marker"),
]:
    count = data.count(needle)
    if count < 1:
        raise SystemExit(f"missing {name} in final packaged Image")
    print(f"PASS: {name} present (count={count})")

for needle, name in FORBIDDEN.items():
    count = data.count(needle)
    if count:
        raise SystemExit(f"forbidden legacy Manager trust remains: {name} (count={count})")
print("PASS: all legacy/official Manager certificate hashes absent")

banner = re.search(rb"Linux version (6\.1\.[0-9]+-android14-Wild)[^\x00\n]*", data)
if not banner:
    raise SystemExit("Wild android14-6.1 Linux banner not found")
print("PASS: kernel=" + banner.group(1).decode())

print("PASS: final Image is artifact-side locked to Nova Utility only")
