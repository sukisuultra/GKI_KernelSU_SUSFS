# NP03J Wild 6.1 LTS — SukiSU Ultra + KPM + SUSFS

Target production branch: `np03j-wild`.

## Device target

- Device: REDMAGIC Nova NP03J
- ROM family: REDMAGICOS 11 / Android 16
- KMI: `android14-6.1`
- Kernel selector: `6.1.x-android14`
- Patch selector: `lts`
- Branding: `Wild`

Android userspace version does not select KMI. Do not change this target to
`android16-6.12` unless fresh device evidence proves the device KMI changed.

## Production root stack

- Root flavor: `SukiSU-Ultra`
- Integration: built-in
- Commit mode: `verified`
- SukiSU kernel pin:
  `b20dee702035af09cb2ecb5f35443bbc1747f3e6`
- SukiSU Manager stable pin: `v4.2.0`
- Manager APK: `SukiSU_v4.2.0_40900-release.apk`
- Manager APK SHA256:
  `4ca9810e6355fbff0bbe4bf5ce159808e64a40d85987a11894030cd990a6bdf3`
- Kernel/Manager UAPI at this audited pair: `2`
- Pin rationale: upstream `e2912817...` did not build because `kernel_umount_feature_set()` was missing. SukiSU fixed exactly that regression in `b20dee7` (#964); the fix changes only `kernel/feature/kernel_umount.c` by adding the missing setter.

## SUSFS

- Branch family: `gki-android14-6.1`
- Verified pin:
  `4fc9c1898ea66f51847cdbc0d1473ea4ef525a70`

Do not replace the verified pin with branch tip merely because the tip is newer.
Promote a newer SUSFS revision only after it builds cleanly with the selected
SukiSU kernel source and works on NP03J.

## KPM / KernelPatch

- Required config: `CONFIG_KPM=y`
- KernelPatch release tag: `0.13.0`
- KernelPatch commit:
  `762e6fb446f58020691b83509873268f6af634f2`
- Official `patch_linux` SHA256:
  `ea4884140c0ee8835bc79b67e4c9b46094c6640d6407f0aab34d2df4e28e0450`

A SukiSU build is rejected unless:

1. `CONFIG_KPM=y`.
2. The exact KernelPatch tag resolves to the audited commit.
3. The downloaded `patch_linux` matches its audited SHA256.
4. `patch_linux` produces a non-empty `oImage`.
5. `oImage` differs from the original `Image`.
6. The patched image replaces the original build output.
7. `AnyKernel3/Image` matches the verified patched-image SHA256.

## Production workflow defaults

- Release Type: `Action`
- Use cache: `false` for first baseline build
- Bypass: `false`
- Kernel Version: `6.1.x-android14`
- OS Patch Level: `lts`
- Brand: `Wild`
- Commit Mode: `verified`
- Root Flavor: `SukiSU-Ultra`
- SUSFS: `true`
- NoMount: `false`
- Baseband Guard: `false`
- Networking extras: `false`
- DroidSpaces: `false`
- NTSync: `false`
- Ptrace patch: `false`
- Unicode extra patch: `false`
- BPF extra stack: `false`
- Performance patches: `false`

This first production baseline intentionally limits variables to:

`Wild + SukiSU Ultra + SUSFS + KPM`.

## Update policy

### 6.1 LTS

Keep `os_patch_level=lts`. Never permanently hard-code a sublevel such as
`6.1.177`. Inspect the actual produced kernel version on every build.

### SukiSU

Do not automatically move the verified kernel pin when a new manager release
appears. Audit the new stable manager, kernel-side source, UAPI, certificate,
SUSFS compatibility, and KPM path first. Then promote both verified pins.

### SUSFS

Do not blindly follow the branch tip. Promote only an NP03J-tested compatible
revision.

### KernelPatch

Do not use an unpinned `patch_linux`. For every KernelPatch update, pin the
release tag, exact commit, and release-asset SHA256.

## Flash rule

A green GitHub Actions run is not permission to flash.

Before flash verify:

- device still reports NP03J / expected ROM
- active slot
- bootloader state
- current kernel/KMI
- rollback boot/init_boot images
- kernel artifact SHA256
- actual kernel sublevel
- SukiSU commit
- SUSFS commit/version
- `CONFIG_KPM=y`
- KernelPatch commit/version
- original vs patched Image hashes
- packaged `AnyKernel3/Image` hash

Flash only after artifact forensic checks pass.
