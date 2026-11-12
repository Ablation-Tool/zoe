# Zoe HP-UX Tools

`hpux-tools` exposes HP-UX SOM debugging and PA-RISC emulation through Zoe. It does not execute anything during component inspection or manifest generation.

## Commands

```bash
zoe launch hpux-tools -- doctor
zoe launch hpux-tools -- gdb -q -batch -ex 'file /scratch/INPUT' -ex 'info files'
zoe launch hpux-tools -- guest 'uname -a'
zoe launch hpux-tools -- qemu --version
zoe launch hpux-tools -- boot
zoe launch hpux-tools -- boot --write
zoe launch hpux-tools -- install
```

`boot` uses snapshot mode unless `--write` is explicit and adds the documented Tulip/user-mode network. `qemu` adds the locally unpacked firmware data directory. `install` boots the verified HP-UX 10.20 installation disc with the legacy SEAGATE SCSI disk model. `guest` logs into HP-UX, runs one noninteractive command, and returns that command's exit status. Commands too long for the legacy serial tty are transferred as an octal-encoded temporary script and removed after execution. `gdb` mounts the scratch disk when present and uses the native GDB built inside the guest at `/scratch/gdb-install/bin/hppa-hp-hpux-gdb`.

Defaults live under `/home/cowboy/security-tools`. Override them with `ZOE_HPUX_GUEST_GDB`, `ZOE_HPUX_QEMU`, `ZOE_HPUX_QEMU_DATA`, `ZOE_HPUX_IMAGE`, `ZOE_HPUX_SCRATCH_DISK`, `ZOE_HPUX_INSTALL_ISO`, and `ZOE_HPUX_INSTALL_DISK`.

The component is only a launcher and availability report. It does not claim that a guest OS is installed, a target is compatible, or dynamic validation has succeeded. The preinstalled image is acquired separately with a published MD5 check; the installation ISO has a separate MD5 and SHA256 record. The native build uses a separate 2 GB scratch disk, leaving the guest root image available for controlled writes only.

## Build provenance

- QEMU 10.2.1 from `qemu-system-misc` with the matching system common/data packages and PA-RISC firmware.
- GDB 6.8a source archive, SHA256 `921b3b3f28ed173b3469ab3b1436bbe8826c62da2cfa045f7853e50585d154f7`. The native HP-UX build uses the guest compiler and SOM headers; `gdb` verifies availability when the guest boots.
- HP-UX 10.20 installation ISO, MD5 `9ea11531abba61524c8ad65b35aa81c2`, SHA256 `91507d759a25f733ac85d93c3ace9dd87bed712f8b0a3b3054b8e4346bd494d1`.
- Preinstalled HP-UX 10.20 image, MD5 `bdee2fe02cbfc79f64364b2ab0213495`, acquired as a sparse raw file with size and digest verification.
