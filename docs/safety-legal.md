# Safety and legal

## Scope of use

- Use this toolkit only on hardware you own or are explicitly authorized to
  service.
- The default posture is read-only. The service terminal is read-only unless
  you pass `--owner-authorized-write`; that flag is an explicit statement that
  you accept the risk.
- The guardrails in the terminal server reduce accidents. They are not a
  security boundary and do not make a full shell safe.

## What is not included

This repository contains no Sony firmware, firmware extracts, boot ROM dumps,
camera binaries, service software, certificates, Sony Senser authentication
key tables, device serial numbers, or backup images. Sony-PMCA-RE is fetched
separately under its own MIT license.

## No rescue guarantee

There is no write-back path in this toolkit. A backup produced here is not a
proven rescue image: it has never been restored, it does not cover RPMB,
OTP/eFuse, or hidden areas, and the camera must be able to boot into service
mode for the read path to work at all.

## Legal considerations

Service-mode access is an undocumented vendor interface. Depending on where
you live, anti-circumvention rules (for example DMCA §1201 in the United
States, the Unfair Competition Prevention Act in Japan, and comparable rules
elsewhere), warranty terms, and Sony's terms of service may restrict what you
may do with it. Repair and security-research exceptions exist in some
jurisdictions, but their conditions differ.

This page is not legal advice. If you plan to redistribute a modified version
or use this commercially, consult a lawyer in your jurisdiction.

## Data handling

- Raw backups contain the camera's file systems and user data. Store them
  encrypted and do not upload them.
- Two copies on the same disk are not two independent copies. Copy the backup
  directory to an external disk and re-run the `sums` check there.
- Logs and manifests may contain device identifiers. Review them before
  sharing.

## Platform risk

Hosting this repository may attract a takedown request. Keeping the repository
free of Sony binaries, key material, and device data is the main practical
mitigation. Keep a local copy and mirror if the project matters to you.

This project is not affiliated with or endorsed by Sony.
