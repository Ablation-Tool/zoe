"""Zoe-GEM OS — Bootable UEFI x86_64 Linux-HAL + Interactive Framebuffer GEM OS Builder."""

from .builder import (
    build_zoe_gem_os_iso,
    format_usb_stage2_guide,
    launch_zo3_cluster,
    launch_zoe_gem_os_kvm,
    verify_zo3_concurrent_kvm,
    verify_zoe_gem_os_qemu,
)
from .zoe_pixel_os import (
    PIXEL_DEVICES,
    PixelDeviceSpec,
    build_pixel_arm64_fb_binary,
    build_pixel_sovereign_bundle,
    detect_host_pixel_toolchain,
    format_pixel_safety_guide,
    list_pixel_devices,
    probe_connected_pixel_adb,
    resolve_pixel_device,
    verify_elf_aarch64_static,
)
from .os_unification import (
    UNIFIED_OS_LAYERS,
    list_unified_components,
    load_os_unification_manifest,
    os_suite_status,
    run_export_airlock,
    spotlight_route,
    unified_os_document,
    verify_unified_os,
)
from .zoe_uma import UmaBridge, find_guest_ivshmem_bar2

__all__ = [
    "PIXEL_DEVICES",
    "PixelDeviceSpec",
    "UNIFIED_OS_LAYERS",
    "UmaBridge",
    "build_pixel_arm64_fb_binary",
    "build_pixel_sovereign_bundle",
    "build_zoe_gem_os_iso",
    "detect_host_pixel_toolchain",
    "find_guest_ivshmem_bar2",
    "format_pixel_safety_guide",
    "format_usb_stage2_guide",
    "launch_zo3_cluster",
    "launch_zoe_gem_os_kvm",
    "list_pixel_devices",
    "list_unified_components",
    "load_os_unification_manifest",
    "os_suite_status",
    "probe_connected_pixel_adb",
    "resolve_pixel_device",
    "run_export_airlock",
    "spotlight_route",
    "unified_os_document",
    "verify_elf_aarch64_static",
    "verify_unified_os",
    "verify_zo3_concurrent_kvm",
    "verify_zoe_gem_os_qemu",
]
