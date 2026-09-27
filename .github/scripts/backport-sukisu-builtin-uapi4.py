#!/usr/bin/env python3
"""
NP03J production backport for SukiSU-Ultra builtin.

Base:
  SukiSU-Ultra builtin b20dee702035af09cb2ecb5f35443bbc1747f3e6

Backported upstream semantics:
  UAPI 3: 86e9b3bf00724b0f649709b8317f0475caf9e8ae
           "fix(kernel, uapi, ksud): make fd wrapper work with app profile (#3679)"
  UAPI 4: dda78702bef1841e70d5b26150b12c03b782e175
           "feat: new version matching detection mechanism (#3516)"

Manager generation paired with this kernel:
  40939
  official Manager source: cf87e3f4ddd3f6e5464d85acf56aaa6950e70841

This script deliberately refuses any source other than the audited builtin base.
It ports the kernel-side UAPI changes instead of merely changing the UAPI number.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE = "b20dee702035af09cb2ecb5f35443bbc1747f3e6"
UAPI3 = "86e9b3bf00724b0f649709b8317f0475caf9e8ae"
UAPI4 = "dda78702bef1841e70d5b26150b12c03b782e175"
MANAGER_SOURCE = "cf87e3f4ddd3f6e5464d85acf56aaa6950e70841"
GENERATION = "40939"


def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def read(path: Path) -> str:
    if not path.is_file():
        die(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        die(f"{path}: expected exactly one source pattern, found {count}")
    write(path, text.replace(old, new, 1))


def require(path: Path, needle: str) -> None:
    if needle not in read(path):
        die(f"{path}: required marker missing: {needle}")


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_dir", type=Path)
    args = ap.parse_args()
    root = args.source_dir.resolve()

    head = git_head(root)
    if head != BASE:
        die(f"refusing non-audited SukiSU source: expected {BASE}, got {head}")

    k = root / "kernel"

    # ---- UAPI 3: scoped su-session fd ----

    replace_once(
        k / "include/uapi/supercall.h",
        "// 2: allowlist v4 root profile flag\nDECLARE(__u32, KERNEL_SU_UAPI_VERSION, 2);",
        "// 2: allowlist v4 root profile flag\n"
        "// 3: scoped su-session driver fd\n"
        "// 4: add KSU_GET_INFO_FLAG_BUNDLED\n"
        "DECLARE(__u32, KERNEL_SU_UAPI_VERSION, 4);",
    )

    replace_once(
        k / "include/uapi/supercall.h",
        "DECLARE(__u32, KSU_GET_INFO_FLAG_PR_BUILD, (1U << 3));",
        "DECLARE(__u32, KSU_GET_INFO_FLAG_PR_BUILD, (1U << 3));\n"
        "DECLARE(__u32, KSU_GET_INFO_FLAG_BUNDLED, (1U << 4));",
    )

    replace_once(
        k / "supercall/supercall.h",
        '#include <linux/types.h>\n#include <linux/uaccess.h>',
        '#include <linux/fs.h>\n#include <linux/types.h>\n#include <linux/uaccess.h>',
    )

    replace_once(
        k / "supercall/supercall.h",
        "    ksu_ioctl_handler_t handler;\n"
        "    ksu_perm_check_t perm_check; // Permission check function\n"
        "};",
        "    ksu_ioctl_handler_t handler;\n"
        "    ksu_perm_check_t perm_check; // Permission check function\n"
        "    bool allow_su_session;\n"
        "};",
    )

    replace_once(
        k / "supercall/supercall.h",
        "// Install KSU fd to current process\n"
        "int ksu_install_fd(void);",
        "// Install KSU fd to current process\n"
        "int ksu_install_fd(void);\n"
        "// Install a KSU fd scoped to operations needed while starting su.\n"
        "int ksu_install_su_fd(void);\n"
        "bool ksu_is_su_session_fd(const struct file *filp);",
    )

    replace_once(
        k / "supercall/internal.h",
        '#include <linux/types.h>\n#include <linux/uaccess.h>',
        '#include <linux/fs.h>\n#include <linux/types.h>\n#include <linux/uaccess.h>',
    )

    replace_once(
        k / "supercall/internal.h",
        "long ksu_supercall_handle_ioctl(unsigned int cmd, void __user *argp);",
        "long ksu_supercall_handle_ioctl(const struct file *filp, unsigned int cmd, void __user *argp);",
    )

    replace_once(
        k / "supercall/supercall.c",
        """static int anon_ksu_release(struct inode *inode, struct file *filp)
{
    pr_info("ksu fd released\\n");
    return 0;
}

static long anon_ksu_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    return ksu_supercall_handle_ioctl(cmd, (void __user *)arg);
}
""",
        """#define KSU_DRIVER_PERMISSION_SU_SESSION (1UL << 0)

struct ksu_driver_context {
    unsigned long permissions;
};

static int anon_ksu_release(struct inode *inode, struct file *filp)
{
    kfree(filp->private_data);
    pr_info("ksu fd released\\n");
    return 0;
}

static long anon_ksu_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    return ksu_supercall_handle_ioctl(filp, cmd, (void __user *)arg);
}
""",
    )

    replace_once(
        k / "supercall/supercall.c",
        """int ksu_install_fd(void)
{
    struct file *filp;
    int fd;

    fd = get_unused_fd_flags(O_CLOEXEC);
    if (fd < 0) {
        pr_err("ksu_install_fd: failed to get unused fd\\n");
        return fd;
    }

    filp = anon_inode_getfile("[ksu_driver]", &anon_ksu_fops, NULL, O_RDWR | O_CLOEXEC);
    if (IS_ERR(filp)) {
        pr_err("ksu_install_fd: failed to create anon inode file\\n");
        put_unused_fd(fd);
        return PTR_ERR(filp);
    }

    fd_install(fd, filp);
    pr_info("ksu fd installed: %d for pid %d\\n", fd, current->pid);
    return fd;
}
""",
        """static int ksu_install_fd_with_permissions(unsigned int fd_flags, unsigned long permissions)
{
    struct ksu_driver_context *context;
    struct file *filp;
    const char *name;
    int fd;

    context = kzalloc(sizeof(*context), GFP_KERNEL);
    if (!context)
        return -ENOMEM;

    context->permissions = permissions;
    name = permissions & KSU_DRIVER_PERMISSION_SU_SESSION ? "[ksu_driver_su]" : "[ksu_driver]";

    fd = get_unused_fd_flags(fd_flags);
    if (fd < 0) {
        pr_err("ksu_install_fd: failed to get unused fd\\n");
        kfree(context);
        return fd;
    }

    filp = anon_inode_getfile(name, &anon_ksu_fops, context, O_RDWR);
    if (IS_ERR(filp)) {
        pr_err("ksu_install_fd: failed to create anon inode file\\n");
        put_unused_fd(fd);
        kfree(context);
        return PTR_ERR(filp);
    }

    fd_install(fd, filp);
    pr_info("ksu fd installed: %d for pid %d\\n", fd, current->pid);
    return fd;
}

int ksu_install_fd(void)
{
    return ksu_install_fd_with_permissions(O_CLOEXEC, 0);
}

int ksu_install_su_fd(void)
{
    return ksu_install_fd_with_permissions(O_CLOEXEC, KSU_DRIVER_PERMISSION_SU_SESSION);
}

bool ksu_is_su_session_fd(const struct file *filp)
{
    const struct ksu_driver_context *context = filp->private_data;

    return context && (context->permissions & KSU_DRIVER_PERMISSION_SU_SESSION);
}
""",
    )

    replace_once(
        k / "supercall/dispatch.c",
        """        .handler = do_get_wrapper_fd,
        .perm_check = manager_or_root
""",
        """        .handler = do_get_wrapper_fd,
        .perm_check = manager_or_root,
        .allow_su_session = true
""",
    )

    replace_once(
        k / "supercall/dispatch.c",
        """        .handler = do_disable_escape_to_root, 
        .perm_check = only_root 
""",
        """        .handler = do_disable_escape_to_root, 
        .perm_check = only_root,
        .allow_su_session = true
""",
    )

    replace_once(
        k / "supercall/dispatch.c",
        "long ksu_supercall_handle_ioctl(unsigned int cmd, void __user *argp)",
        "long ksu_supercall_handle_ioctl(const struct file *filp, unsigned int cmd, void __user *argp)",
    )

    replace_once(
        k / "supercall/dispatch.c",
        """            if (ksu_ioctl_handlers[i].perm_check && !ksu_ioctl_handlers[i].perm_check()) {
                pr_warn("ksu ioctl: permission denied for cmd=0x%x uid=%d\\n", cmd, current_uid().val);
                return -EPERM;
            }
""",
        """            if (ksu_ioctl_handlers[i].perm_check && !ksu_ioctl_handlers[i].perm_check() &&
                !(ksu_ioctl_handlers[i].allow_su_session && ksu_is_su_session_fd(filp))) {
                pr_warn("ksu ioctl: permission denied for cmd=0x%x uid=%d\\n", cmd, current_uid().val);
                return -EPERM;
            }
""",
    )

    # Builtin+SUSFS sucompat path: install the scoped fd only after the
    # selected root profile was applied successfully.
    replace_once(
        k / "feature/sucompat.c",
        """    ret = escape_with_root_profile();
    if (ret)
        pr_err("escape_with_root_profile() failed: %d\\n", ret);

    const char __user *argv_user_ptr = get_user_arg_ptr(*((struct user_arg_ptr*)argv_user), 0);
""",
        """    ret = escape_with_root_profile();
    if (ret) {
        pr_err("escape_with_root_profile() failed: %d\\n", ret);
    } else {
        int su_fd = ksu_install_su_fd();
        if (su_fd < 0)
            pr_warn("install su session fd failed: %d\\n", su_fd);
    }

    const char __user *argv_user_ptr = get_user_arg_ptr(*((struct user_arg_ptr*)argv_user), 0);
""",
    )

    # Builtin non-SUSFS execve helper.
    replace_once(
        k / "feature/sucompat.c",
        """    ret = escape_with_root_profile();
    if (!!ret)
        return ret;

    // NOTE: we only check file existence, not exec success!
""",
        """    ret = escape_with_root_profile();
    if (!!ret)
        return ret;

    {
        int su_fd = ksu_install_su_fd();
        if (su_fd < 0)
            pr_warn("install su session fd failed: %d\\n", su_fd);
    }

    // NOTE: we only check file existence, not exec success!
""",
    )

    # Builtin non-SUSFS execveat path.
    replace_once(
        k / "feature/sucompat.c",
        """    ret = escape_with_root_profile();
    ksu_sulog_emit_pending(pending_root_execve, ret, GFP_KERNEL);
    if (!!ret)
        return 0;

    // NOTE: we only check file existence, not exec success!
""",
        """    ret = escape_with_root_profile();
    ksu_sulog_emit_pending(pending_root_execve, ret, GFP_KERNEL);
    if (!!ret)
        return 0;

    {
        int su_fd = ksu_install_su_fd();
        if (su_fd < 0)
            pr_warn("install su session fd failed: %d\\n", su_fd);
    }

    // NOTE: we only check file existence, not exec success!
""",
    )

    # Upstream UAPI 3 file-wrapper fix.
    replace_once(
        k / "infra/file_wrapper.c",
        """int ksu_install_file_wrapper(int fd)
{
    int out_fd, ret;
    struct file *orig_file = fget(fd);
""",
        """int ksu_install_file_wrapper(int fd)
{
    int out_fd, ret;
    const struct cred *old_cred;
    struct file *wrapper_file;
    struct file *orig_file = fget(fd);
""",
    )

    replace_once(
        k / "infra/file_wrapper.c",
        """    struct file *wrapper_file = ksu_anon_inode_create_getfile_compat("[ksu_fdwrapper]", &file_wrapper_data->ops,
                                                                     file_wrapper_data, orig_file->f_flags, NULL);
""",
        """    old_cred = override_creds(ksu_cred);
    wrapper_file = ksu_anon_inode_create_getfile_compat("[ksu_fdwrapper]", &file_wrapper_data->ops,
                                                        file_wrapper_data, orig_file->f_flags, NULL);
    revert_creds(old_cred);
""",
    )

    # ---- UAPI 4: bundled-LKM flag. It is inactive for this CONFIG_KSU=y
    # builtin target, but the ABI definition is complete and matches manager 40939.
    replace_once(
        k / "include/ksu.h",
        """extern bool allow_shell;
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)
""",
        """extern bool allow_shell;
#ifdef MODULE
extern bool ksu_bundled;
#endif
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)
""",
    )

    replace_once(
        k / "ksu.c",
        """bool ksu_no_custom_rc = false;
module_param_named(norc, ksu_no_custom_rc, bool, 0);

int __init kernelsu_init(void)
""",
        """bool ksu_no_custom_rc = false;
module_param_named(norc, ksu_no_custom_rc, bool, 0);

#ifdef MODULE
bool ksu_bundled = false;
module_param_named(bundled, ksu_bundled, bool, 0);
#endif

int __init kernelsu_init(void)
""",
    )

    replace_once(
        k / "supercall/dispatch.c",
        """    struct ksu_get_info_cmd cmd = { .version = KERNEL_SU_VERSION, .flags = 0 };

    if (is_manager()) {
""",
        """    struct ksu_get_info_cmd cmd = { .version = KERNEL_SU_VERSION, .flags = 0 };

#ifdef MODULE
    cmd.flags |= KSU_GET_INFO_FLAG_LKM;
    if (ksu_bundled)
        cmd.flags |= KSU_GET_INFO_FLAG_BUNDLED;
#endif

    if (is_manager()) {
""",
    )

    replace_once(
        k / "supercall/dispatch.c",
        """#ifdef MODULE
    cmd.flags |= KSU_GET_INFO_FLAG_LKM;
#endif

    if (is_manager()) {
""",
        """#ifdef MODULE
    cmd.flags |= KSU_GET_INFO_FLAG_LKM;
    if (ksu_bundled)
        cmd.flags |= KSU_GET_INFO_FLAG_BUNDLED;
#endif

    if (is_manager()) {
""",
    )

    # Freeze the driver generation to the exact official Manager generation.
    # The builtin Makefile otherwise derives this from the moving upstream
    # main commit count, which would recreate a version mismatch later.
    replace_once(
        k / "Makefile",
        "KSU_VERSION     := $(if $(LOCAL_COUNT),$(shell expr $(VERSION_BASE) + $(LOCAL_COUNT) - $(VERSION_OFFSET)),13000)",
        "KSU_VERSION     := 40939",
    )

    # ---- Static verification ----
    require(k / "include/uapi/supercall.h", "KERNEL_SU_UAPI_VERSION, 4")
    require(k / "include/uapi/supercall.h", "KSU_GET_INFO_FLAG_BUNDLED")
    require(k / "supercall/supercall.c", "KSU_DRIVER_PERMISSION_SU_SESSION")
    require(k / "supercall/supercall.c", "ksu_install_su_fd")
    require(k / "supercall/supercall.c", "ksu_is_su_session_fd")
    require(k / "supercall/dispatch.c", ".allow_su_session = true")
    require(k / "supercall/dispatch.c", "ksu_is_su_session_fd(filp)")
    require(k / "feature/sucompat.c", "install su session fd failed")
    require(k / "infra/file_wrapper.c", "override_creds(ksu_cred)")
    require(k / "Makefile", "KSU_VERSION     := 40939")

    if "KERNEL_SU_UAPI_VERSION, 2" in read(k / "include/uapi/supercall.h"):
        die("old UAPI 2 definition still present")

    provenance = root / "NP03J_UAPI4_BACKPORT_PROVENANCE.txt"
    provenance.write_text(
        "\n".join(
            [
                f"base={BASE}",
                f"uapi3_upstream={UAPI3}",
                f"uapi4_upstream={UAPI4}",
                f"manager_source={MANAGER_SOURCE}",
                f"generation={GENERATION}",
                "uapi=4",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("PASS: audited SukiSU builtin UAPI4 backport applied")
    print(f"base={BASE}")
    print(f"uapi3={UAPI3}")
    print(f"uapi4={UAPI4}")
    print(f"manager_source={MANAGER_SOURCE}")
    print(f"generation={GENERATION}")
    print("uapi=4")


if __name__ == "__main__":
    main()
