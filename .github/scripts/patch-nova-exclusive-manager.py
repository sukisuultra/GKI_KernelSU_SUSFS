#!/usr/bin/env python3
import re
import sys
from pathlib import Path

EXPECTED_OFFICIAL_HASH = "947ae944f3de4ed4c21a7e4f7953ecf351bfa2b36239da37a34111ad29993eef"
OLD_CERT_MAX = 1024
NEW_CERT_MAX = 1280

def fail(msg: str) -> None:
    raise SystemExit(msg)

if len(sys.argv) != 6:
    fail("usage: patch-nova-exclusive-manager.py <apk_sign.c> <size_hex> <sha256> <package> <marker>")

path = Path(sys.argv[1])
size_hex = sys.argv[2].lower()
digest = sys.argv[3].lower()
package = sys.argv[4]
marker = sys.argv[5]

if not path.is_file():
    fail(f"apk_sign.c not found: {path}")
if not re.fullmatch(r"0x[0-9a-f]+", size_hex):
    fail(f"invalid certificate size: {size_hex}")
if not re.fullmatch(r"[0-9a-f]{64}", digest):
    fail(f"invalid certificate SHA256: {digest}")
if package != "app.nova.utility":
    fail(f"unexpected package: {package}")
if marker != "NOVA_UTILITY_EXCLUSIVE_MANAGER_V1_CERTMAX_1280":
    fail(f"unexpected policy marker: {marker}")

cert_size = int(size_hex, 16)
if cert_size != 1060:
    fail(f"unexpected Nova Utility certificate size: {cert_size}")
if not (OLD_CERT_MAX < cert_size <= NEW_CERT_MAX):
    fail(f"certificate size {cert_size} does not prove/fix the 1024-byte ceiling issue")

text = path.read_text()

old_define = "#define CERT_MAX_LENGTH 1024"
new_define = "#define CERT_MAX_LENGTH 1280"
if text.count(old_define) != 1:
    fail("audited source invariant failed: expected exactly one CERT_MAX_LENGTH 1024")
text = text.replace(old_define, new_define, 1)

table_pat = re.compile(
    r"(static struct apk_sign_key\s*\{.*?\}\s*apk_sign_keys\[\]\s*=\s*\{\n)(.*?)(\n\};)",
    re.S,
)
m = table_pat.search(text)
if not m:
    fail("apk_sign_keys[] table not found")

exclusive_entry = (
    f'    {{ {size_hex}, "{digest}" }}, '
    f'// {marker} package={package}\n'
)
text = text[:m.start(2)] + exclusive_entry + text[m.end(2):]

guard_pat = re.compile(
    r"#ifdef KSU_MANAGER_PACKAGE\n"
    r"    char pkg\[KSU_MAX_PACKAGE_NAME\];\n"
    r"    if \(get_pkg_from_apk_path\(pkg, path\) < 0\) \{.*?"
    r"#endif\n",
    re.S,
)
gm = guard_pat.search(text)
if not gm:
    fail("conditional KSU_MANAGER_PACKAGE block not found")

exclusive_guard = f'''    char pkg[KSU_MAX_PACKAGE_NAME];
    if (get_pkg_from_apk_path(pkg, path) < 0) {{
        pr_err("Failed to get package name from apk path: %s\\n", path);
        return false;
    }}

    if (strncmp(pkg, "{package}", sizeof("{package}")) != 0) {{
        return false;
    }}

    pr_info("{marker} accepted package: %s\\n", pkg);
'''
text = text[:gm.start()] + exclusive_guard + text[gm.end():]

path.write_text(text)

final = path.read_text()
if final.count(new_define) != 1:
    fail("CERT_MAX_LENGTH 1280 patch not present exactly once")
if old_define in final:
    fail("old CERT_MAX_LENGTH 1024 remains")
if final.count(digest) != 1:
    fail("Nova Utility certificate hash missing or duplicated")
if EXPECTED_OFFICIAL_HASH in final:
    fail("official SukiSU Manager certificate still trusted")
if final.count(package) < 2:
    fail("exclusive package policy not embedded as expected")
if final.count(marker) < 2:
    fail("exclusive policy marker not embedded as expected")

tm = table_pat.search(final)
if not tm:
    fail("apk_sign_keys[] disappeared after patch")
hashes = re.findall(r'"([0-9a-f]{64})"', tm.group(2))
if hashes != [digest]:
    fail(f"unexpected manager trust table hashes: {hashes}")

if "#ifdef KSU_MANAGER_PACKAGE" in final[final.find("bool is_manager_apk"):]:
    fail("conditional manager package gate still present in is_manager_apk")

print("PASS: Nova Utility exclusive runtime policy patched")
print(f"PASS: CERT_MAX_LENGTH={NEW_CERT_MAX}; cert_size={cert_size}")
print(f"PASS: only trusted Manager cert SHA256={digest}")
print(f"PASS: only eligible Manager package={package}")
print("PASS: official/alternate Manager trust table entries removed")
