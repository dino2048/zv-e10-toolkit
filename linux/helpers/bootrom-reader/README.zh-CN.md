[English](README.md) | **简体中文**

# BootROM 助手

`read_page.S` / `read_page.elf` —— 一个 460 字节、无重定位的 ARM EABI
可执行文件，供 `host/zve10_bootrom_dump.py` 使用。

## 作用

`read_page.elf <0..5>`：

1. 检查页索引（0..5）；
2. `open("/dev/mem", O_RDONLY)`；
3. `mmap2` 在 `0xffff0000 + index * 0x1000` 映射一个 4 KiB 页，`PROT_READ`、
   `MAP_SHARED`；
4. 以 16 行、每行 512 个十六进制字符输出 4096 字节；
5. 退出码 0。

它只读取映射页；唯一的写入是 stdout。

## 已验证

- 源码 SHA-256：`5210faa9d38bad75ff2215ddde9be18683fbb13f9f2fa640815649c7091a3f68`
- ELF SHA-256：`a7a8aa74f4e9645af45a94e68719f583389ecfc726d0e5bb97ff1ca6893e1226`
- 大小：460 字节
- 用于 `0xffff0000–0xffff5fff` 的 24 KiB 两遍读取

## 重建

```sh
pip install pyelftools
python helpers/bootrom-reader/build_page_helper.py
```

需要带 `arm-linux-gnueabi` target 的 `clang`。重建应得到同样的 460 字节 ELF
和同样的 SHA-256；如果不一样，不要直接使用，先检查反汇编。
