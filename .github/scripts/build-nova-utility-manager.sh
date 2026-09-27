#!/usr/bin/env bash
set -euo pipefail

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME is required}"
: "${ANDROID_SDK_ROOT:?ANDROID_SDK_ROOT is required}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"

SUKISU_MANAGER_SOURCE="cf87e3f4ddd3f6e5464d85acf56aaa6950e70841"
MANAGER_PACKAGE="app.nova.utility"
MANAGER_NAME="Nova Utility"
MANAGER_GENERATION="40939"
SRC="$PWD/SukiSU-Manager-Source"

rm -rf "$SRC"
git clone https://github.com/SukiSU-Ultra/SukiSU-Ultra.git "$SRC"
git -C "$SRC" checkout --detach "$SUKISU_MANAGER_SOURCE"
ACTUAL="$(git -C "$SRC" rev-parse HEAD)"
[ "$ACTUAL" = "$SUKISU_MANAGER_SOURCE" ] || {
  echo "::error::SukiSU manager source mismatch"
  exit 1
}
COUNT="$(git -C "$SRC" rev-list --count HEAD)"
VERSION_CODE=$((40000 + COUNT - 2815))
[ "$VERSION_CODE" = "$MANAGER_GENERATION" ] || {
  echo "::error::Manager generation mismatch: expected $MANAGER_GENERATION got $VERSION_CODE"
  exit 1
}
echo "PASS: manager source=$ACTUAL generation=$VERSION_CODE"

cd "$SRC/manager"

find . -depth -type d -name 'com' -execdir mv {} app \;
find . -depth -type d -name 'sukisu' -execdir mv {} nova \;
find . -depth -type d -name 'ultra' -execdir mv {} utility \;
find . -depth -type d -name 'io' -execdir mv {} core \;

find . -type f -exec sed -i \
  -e 's/com\.sukisu\.ultra/app.nova.utility/g' \
  -e 's/io\.sukisu\.ultra/core.nova.utility/g' \
  -e 's/com\.sukisu\.zako/app.nova.zako/g' \
  -e 's/com\/sukisu\/ultra/app\/nova\/utility/g' \
  -e 's/io\/sukisu\/ultra/core\/nova\/utility/g' \
  -e 's/io_sukisu_ultra/core_nova_utility/g' \
  -e 's/com_sukisu_ultra/app_nova_utility/g' {} +

sed -i \
  -e '/fun getGitDescribe(): String {/,/^    }/ s/\.trim()$/.trim() + "-spoofed"/' \
  build.gradle.kts

cd "$SRC"

sed -i \
  's/com\.sukisu\.ultra\.ui\.MainActivity/app.nova.utility.ui.MainActivity/g' \
  userspace/ksud/src/late_load.rs

grep -R -n -F 'package app.nova.utility' manager/app/src/main/java/app/nova/utility | head
grep -q 'namespace = "app.nova.utility"' manager/app/build.gradle.kts
grep -q 'Java_app_nova_utility_Natives_' manager/app/src/main/cpp/jni.cc
grep -q 'app.nova.utility.ui.MainActivity' userspace/ksud/src/late_load.rs

if grep -R -n -E 'package com\.sukisu\.ultra|namespace = "com\.sukisu\.ultra"|Java_com_sukisu_ultra_' manager/app/src/main; then
  echo "::error::Original Manager namespace remains after spoof"
  exit 1
fi
echo "PASS: deterministic spoof namespace=app.nova.utility"

STOREPASS="$(openssl rand -hex 32)"
KEYPASS="$(openssl rand -hex 32)"

keytool -genkeypair \
  -alias nova-utility \
  -keyalg RSA \
  -keysize 2048 \
  -sigalg SHA256withRSA \
  -validity 10000 \
  -dname "CN=Nova Utility, OU=NP03J Final, O=Local Build, C=US" \
  -storetype JKS \
  -keystore nova-utility.jks \
  -storepass "$STOREPASS" \
  -keypass "$KEYPASS"

keytool -exportcert \
  -alias nova-utility \
  -keystore nova-utility.jks \
  -storepass "$STOREPASS" \
  -file nova-utility-cert.der

SIZE_DEC="$(stat -c%s nova-utility-cert.der)"
SIZE_HEX="$(printf '0x%x' "$SIZE_DEC")"
HASH="$(sha256sum nova-utility-cert.der | awk '{print $1}')"
[[ "$SIZE_HEX" =~ ^0x[0-9a-f]+$ ]]
[[ "$HASH" =~ ^[0-9a-f]{64}$ ]]
echo "cert_size=$SIZE_HEX" >> "$GITHUB_OUTPUT"
echo "cert_hash=$HASH" >> "$GITHUB_OUTPUT"
echo "PASS: custom cert size=$SIZE_HEX ($SIZE_DEC bytes)"
echo "PASS: custom cert sha256=$HASH"

export KSU_PACKAGE_NAME="$MANAGER_PACKAGE"
for TARGET in aarch64-linux-android armv7-linux-androideabi x86_64-linux-android; do
  rustup target add "$TARGET"
  source .github/scripts/setup-rust-build.sh "$TARGET" 26
  cargo build \
    --target "$TRIPLE" \
    --release \
    --manifest-path ./userspace/ksud/Cargo.toml
  test -x "target/$TARGET/release/ksud"
done

mkdir -p manager/app/src/main/jniLibs/arm64-v8a
mkdir -p manager/app/src/main/jniLibs/armeabi-v7a
mkdir -p manager/app/src/main/jniLibs/x86_64
cp target/aarch64-linux-android/release/ksud manager/app/src/main/jniLibs/arm64-v8a/libksud.so
cp target/armv7-linux-androideabi/release/ksud manager/app/src/main/jniLibs/armeabi-v7a/libksud.so
cp target/x86_64-linux-android/release/ksud manager/app/src/main/jniLibs/x86_64/libksud.so

strings target/aarch64-linux-android/release/ksud | grep -F "$MANAGER_PACKAGE" >/dev/null
strings target/aarch64-linux-android/release/ksud | grep -F 'app.nova.utility.ui.MainActivity' >/dev/null
echo "PASS: ksud package binding=$MANAGER_PACKAGE"
echo "PASS: ksud Manager activity=app.nova.utility.ui.MainActivity"

cat >> manager/gradle.properties <<EOF
KEYSTORE_PASSWORD=$STOREPASS
KEY_ALIAS=nova-utility
KEY_PASSWORD=$KEYPASS
KEYSTORE_FILE=../nova-utility.jks
EOF

(
  cd manager
  ./gradlew clean assembleRelease \
    -PKSU_PACKAGE_NAME="$MANAGER_PACKAGE" \
    -PKSU_NAME="$MANAGER_NAME"
)

python3 repack_apk.py repack \
  -b release \
  -t release \
  -a arm64-v8a \
  -a armeabi-v7a \
  -a x86_64 \
  -K nova-utility.jks \
  -A nova-utility \
  -P "$STOREPASS" \
  -S "$KEYPASS" \
  --strip \
  --output-name "Nova_Utility_v4.2.0-spoofed_40939"

APK="$SRC/dist/Nova_Utility_v4.2.0-spoofed_40939.apk"
test -f "$APK"

AAPT2="$(find "$ANDROID_SDK_ROOT/build-tools" -type f -name aapt2 | sort -V | tail -n1)"
APKSIGNER="$(find "$ANDROID_SDK_ROOT/build-tools" -type f -name apksigner | sort -V | tail -n1)"
test -x "$AAPT2"
test -x "$APKSIGNER"

"$AAPT2" dump badging "$APK" > /tmp/nova-badging.txt
head -n 8 /tmp/nova-badging.txt
grep -q "package: name='app.nova.utility'" /tmp/nova-badging.txt
grep -q "versionCode='40939'" /tmp/nova-badging.txt
grep -q "versionName='v4.2.0-spoofed'" /tmp/nova-badging.txt
grep -q "application-label:'Nova Utility'" /tmp/nova-badging.txt

"$APKSIGNER" verify --verbose --print-certs "$APK" > /tmp/nova-signature.txt
cat /tmp/nova-signature.txt
grep -q 'Verified using v1 scheme (JAR signing): false' /tmp/nova-signature.txt
grep -q 'Verified using v2 scheme (APK Signature Scheme v2): true' /tmp/nova-signature.txt
grep -q 'Verified using v3 scheme (APK Signature Scheme v3): false' /tmp/nova-signature.txt
grep -q 'Verified using v3.1 scheme (APK Signature Scheme v3.1): false' /tmp/nova-signature.txt

CERT_HASH="$(sha256sum nova-utility-cert.der | awk '{print $1}')"
APK_CERT_HASH="$(sed -n 's/^Signer #1 certificate SHA-256 digest: //p' /tmp/nova-signature.txt | tr -d ':' | tr '[:upper:]' '[:lower:]' | head -n1)"
[ "$APK_CERT_HASH" = "$CERT_HASH" ] || {
  echo "::error::APK signing certificate mismatch: expected $CERT_HASH got $APK_CERT_HASH"
  exit 1
}

APK_SHA="$(sha256sum "$APK" | awk '{print $1}')"
echo "apk_sha256=$APK_SHA" >> "$GITHUB_OUTPUT"
echo "apk_name=$(basename "$APK")" >> "$GITHUB_OUTPUT"

cat > dist/Nova_Utility_Manager_40939_BUILD_INFO.txt <<EOF
app_name=Nova Utility
package=app.nova.utility
version_name=v4.2.0-spoofed
version_code=40939
manager_source=$SUKISU_MANAGER_SOURCE
kernel_generation=40939
manager_uapi=4
certificate_size=$SIZE_HEX
certificate_sha256=$HASH
apk_sha256=$APK_SHA
signing=v2-only
private_key_uploaded=no
EOF

cp nova-utility-cert.der dist/Nova_Utility_Manager_Certificate.der

rm -f nova-utility.jks
rm -f manager/key.jks manager/pr-key.jks || true
unset STOREPASS KEYPASS

echo "PASS: package=app.nova.utility"
echo "PASS: app name=Nova Utility"
echo "PASS: version=40939 / v4.2.0-spoofed"
echo "PASS: signature=v2 only"
echo "PASS: apk sha256=$APK_SHA"
