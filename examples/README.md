# Examples

These files illustrate formats. They are not real device data.

- `manifest.sample.json` — schema of a raw-backup manifest. Hashes are
  placeholders.
- `SHA256SUMS.sample` — standard `sha256sum` format. Hashes are placeholders.
- `offline-verification.sample.json` — schema of the `slices` report.
- `partitions.sample.tsv` — the partition layout observed on the tested
  firmware. Verify it against `/proc/partitions` and
  `/sys/class/block/nflasha*` on your camera before relying on it.

---

# 示例

这些文件只用于说明格式，不是真实设备数据。

- `manifest.sample.json`——原始备份 manifest 的结构，哈希为占位值。
- `SHA256SUMS.sample`——标准 `sha256sum` 格式，哈希为占位值。
- `offline-verification.sample.json`——`slices` 报告的结构。
- `partitions.sample.tsv`——实测固件上的分区布局。使用前请与相机的
  `/proc/partitions` 和 `/sys/class/block/nflasha*` 核对。
