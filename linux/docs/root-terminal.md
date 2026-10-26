# Root terminal

After service authentication, the camera can expose a debug terminal. On the
tested ZV-E10 firmware the shell runs with Uid/Gid 0.

## Opening and closing

- `camera.setTerminalEnable(True)` enables it.
- `dev.readTerminal()` reads output; `dev.writeTerminal(...)` writes input.
- `setTerminalEnable(False)` closes it; the server always does this in a
  `finally` block.

Each command is wrapped with unique begin/end markers so replies can be
attributed even when output is fragmented.

## Root identity

`/proc/$$/status` reports `Uid: 0 0 0 0` and `Gid: 0 0 0 0`. The camera's
busybox build may not include the `id` applet; that does not change the
privilege level.

## Default mode: read-only

Without `--owner-authorized-write`, only a small allow-list is accepted:
`cat`, `ls`, `find`, `ps`, `du`, `df`, `grep`, `head`, `tail`, `wc`,
`sha256sum`, `md5sum`, `stat`, `readlink`, `pwd`, `uptime`, `date`, `uname`,
`free`, `echo`, `id`, `dmesg` (optionally prefixed with `busybox`).

Also refused in read-only mode:

- shell metacharacters outside single quotes;
- `/dev/` access;
- `find` action flags such as `-exec`, `-delete`, `-fprint`.

Commands are single-line ASCII, up to 200 characters. The session ends after
10 idle minutes.

## Full shell

`--owner-authorized-write` lifts the allow-list for that session. The
catastrophic-command denylist remains: filesystem/partition tools, block-device
writes, recursive removal, mount operations, kernel modules, and power
commands. `--allow-module-swap` additionally permits `insmod`/`rmmod` and
requires write mode.

These checks are guardrails, not a security boundary. A full shell can still
damage the camera; it is intended for the device owner.
