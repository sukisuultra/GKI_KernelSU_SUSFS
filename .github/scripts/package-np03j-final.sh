#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${MANAGER_CERT_SIZE:?MANAGER_CERT_SIZE is required}"
: "${MANAGER_CERT_HASH:?MANAGER_CERT_HASH is required}"
: "${MANAGER_APK_SHA:?MANAGER_APK_SHA is required}"

mkdir -p final

MANAGER="$(find staging/manager -type f -name 'Nova_Utility_v4.2.0-spoofed_40939.apk' -print -quit)"
CERT="$(find staging/manager -type f -name 'Nova_Utility_Manager_Certificate.der' -print -quit)"
MINFO="$(find staging/manager -type f -name 'Nova_Utility_Manager_40939_BUILD_INFO.txt' -print -quit)"
test -f "$MANAGER"
test -f "$CERT"
test -f "$MINFO"

cp "$MANAGER" final/Nova_Utility_v4.2.0-spoofed_40939.apk
cp "$CERT" final/Nova_Utility_Manager_Certificate.der
cp "$MINFO" final/Nova_Utility_Manager_40939_BUILD_INFO.txt
cp staging/fallback/SukiSU_v4.2.0_40939-release.apk final/

(
  cd staging/kernel
  zip -qr "$GITHUB_WORKSPACE/final/NP03J_6.1.177_android14_Wild_SukiSU40939_UAPI4_FullFeatures_AnyKernel3.zip" .
)

(
  cd staging/nomount
  zip -qr "$GITHUB_WORKSPACE/final/NoMount_v2.0.0_NP03J_Metamodule.zip" .
)

BUILDINFO="$(find staging/buildinfo -type f -print -quit)"
test -f "$BUILDINFO"
cp "$BUILDINFO" final/NP03J_Final_FullFeatures_BuildInfo.md

CERT_HASH="$(sha256sum final/Nova_Utility_Manager_Certificate.der | awk '{print $1}')"
[ "$CERT_HASH" = "$MANAGER_CERT_HASH" ] || {
  echo "::error::Final bundle certificate hash mismatch"
  exit 1
}

MANAGER_SHA="$(sha256sum final/Nova_Utility_v4.2.0-spoofed_40939.apk | awk '{print $1}')"
[ "$MANAGER_SHA" = "$MANAGER_APK_SHA" ] || {
  echo "::error::Final bundle Manager hash mismatch"
  exit 1
}

cat > final/FINAL_BUILD_INFO.txt <<EOF
device=REDMAGIC Nova NP03J
rom=REDMAGICOS 11
android=16
kmi=android14-6.1
kernel=6.1.177-android14-Wild
root=SukiSU Ultra BUILT-IN
kernel_generation=40939
kernel_uapi=4
manager_name=Nova Utility
manager_package=app.nova.utility
manager_version=v4.2.0-spoofed
manager_version_code=40939
manager_source=cf87e3f4ddd3f6e5464d85acf56aaa6950e70841
manager_certificate_size=$MANAGER_CERT_SIZE
manager_certificate_sha256=$MANAGER_CERT_HASH
manager_apk_sha256=$MANAGER_APK_SHA
susfs=v2.3.0
susfs_commit=4fc9c1898ea66f51847cdbc0d1473ea4ef525a70
kpm=enabled
kernelpatch=0.13.0
nomount_commit=d0f57d5c37ff02aae2299daded57919153240cb3
baseband_guard=a54e0dc6cf0aff4dd87fec49644a02d2eb612905
droidspaces=cff50fa04d50472b607ba6822e8bf482b19cd427
networking=enabled
ntsync=enabled
unicode_fix=enabled
bpf_stack=BTF+eBPF+FUSE-BPF
ptrace_patch=selected-but-not-applicable-on-6.1
performance=disabled
release_notes_preview=disabled
workflow_commit=$GITHUB_SHA
workflow_run=https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID
EOF

(
  cd final
  sha256sum * > SHA256SUMS.txt
)

cat final/FINAL_BUILD_INFO.txt
cat final/SHA256SUMS.txt
