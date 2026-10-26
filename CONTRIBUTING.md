# Development and validation / 开发与验证

Keep the published repository focused on Linux service-interface tools and the
paired bare-metal read/write and partition-recovery path. Research snapshots, test-pattern
drills, private device data and unsupported payload variants belong outside it.

发布仓库只保留 Linux 服务接口工具、配套裸机读写程序和分区恢复工具。研究快照、
测试图案演练、私有设备数据和非正式 payload 变体不应加入这里。

## Offline checks / 离线检查

From the repository root, with Python 3.10+, make and clang:

```sh
make -C bootrom test PYTHON=python3
```

This checks release payload hashes and capabilities, C partition/eMMC/fastboot
logic with undefined-behavior sanitization, Python USB protocol handling,
and the Linux slice-report-to-recovery preparation flow. It also checks that
invalid backup data stops recovery before any device access. Tests need no
camera, Pico, Sony-PMCA-RE checkout or Python USB packages.

测试不连接设备，不写入相机，也不需要安装 Sony-PMCA-RE 或 Python USB 包。

## Rebuild the published pair / 重建正式配对

The byte-identical build was checked with Apple clang 17.0.0
(`clang-1700.6.4.2`) and ARM GNU binutils 2.47.20260726 on macOS.
Install the `arm-none-eabi-binutils` Homebrew package and use Apple's clang.
Different compiler versions may produce different bytes or addresses; the
fixed stage1 hash deliberately rejects an unreviewed ABI change.

```sh
make -C bootrom build PYTHON=python3
python3 -B bootrom/tools/check_abi.py --build --image
cmp bootrom/stage1/build/fastboot.bin bootrom/prebuilt/stage1.bin
cmp bootrom/stage2/build-flash/stage2-fastboot-flash.bin bootrom/prebuilt/stage2-flash.bin
make -C bootrom clean
```

`build/` directories contain local intermediates only. `make -C bootrom clean` preserves
`prebuilt/`. Never replace release images just to silence a hash or ABI failure.
Changes to stage1 require reviewing `bootrom/stage2/include/usb_link.h`, the pinned hash in
`bootrom/tools/check_abi.py`, and the stage2 pair. A changed image needs fresh hardware
validation before publication. Update the release manifest and `SHA256SUMS`
together with any approved payload change.

`prebuilt/` 仅存放已验证配套镜像。源码清理应重建出原字节；功能修改若改变镜像，
应重新进行实机验证后才更新正式镜像和校验清单。

## Other components / 其他组件

- Linux installation: `linux/scripts/setup.sh` creates a local environment and pins Sony-PMCA-RE to commit `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0`.
- Linux BootROM helper: see [build instructions](linux/helpers/bootrom-reader/README.md). The 460-byte ELF is an intentional runtime asset; it is not a discarded intermediate.
- Pico firmware: see [Pico setup](bootrom/pico/README.md). The checked-in PIO header is required source. Build UF2 files outside the repository.
- Keep English and Chinese user guides consistent, including paths, tested firmware, supported recovery targets and limitations.

No automated check replaces hardware validation. This cleanup preserves the
two published payload binaries; it does not claim a new hardware session.
