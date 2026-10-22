# Root terminal

After service authentication, the camera can expose a debug terminal. In the
observed ZV-E10 firmware the shell runs with Uid/Gid 0. This is a root shell,
but it is also a vendor debug facility, not a memory-corruption exploit.

## How the terminal is opened

- `camera.setTerminalEnable(True)` enables the terminal.
- Output is read with `dev.readTerminal()`; input is written with
  `dev.writeTerminal(...)`.
- `setTerminalEnable(False)` closes it. The server always does this in a
  `finally` block, including on errors.

The toolkit wraps each command with unique begin/end markers so that replies
can be attributed reliably even when output is fragmented or late.

## Root identity

The service shell reports `Uid: 0 0 0 0` and `Gid: 0 0 0 0` in
`/proc/$$/status`. `busybox id` may be missing from the camera's busybox build;
that does not mean the shell is unprivileged.

## Default mode: read-only

The terminal server is read-only unless the owner passes
`--owner-authorized-write`. In read-only mode:

- only a small allow-list is accepted: `cat`, `ls`, `find`, `ps`, `du`, `df`,
  `grep`, `head`, `tail`, `wc`, `sha256sum`, `md5sum`, `stat`, `readlink`,
  `pwd`, `uptime`, `date`, `uname`, `free`, `echo`, `id`, `dmesg` (optionally
  prefixed with `busybox`);
- shell metacharacters are refused outside single quotes;
- `/dev/` access is refused;
- `find` action flags such as `-exec`, `-delete`, and `-fprint` are refused.

Commands are single-line, ASCII, and limited to 200 characters. The session
times out after 10 idle minutes.

## Full shell

`--owner-authorized-write` lifts the allow-list for that session. The
catastrophic-command denylist remains: filesystem/partition tools, block-device
writes, recursive removal, mount operations, kernel modules, and power
commands are still refused. `--allow-module-swap` additionally permits
`insmod`/`rmmod` and requires write mode.

These checks are **guardrails, not a security boundary**. A determined user
with a full shell can still damage the camera. The server is meant for the
owner of the device, not as a sandbox for untrusted users.

## What this tool does not do

- It does not read eMMC images; use `zve10_backup_raw.py`.
- It does not write block devices or restore backups.
- It does not persist anything across a reboot by itself.
