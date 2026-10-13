# Updating without ArtCraft Launcher

Run the installer again. It discovers current stable GitHub releases, shows the installed and available versions, and asks whether to select available updates. Review the selection, then click **Install / update selected** on Windows or enter **I** on Linux. **Select updates only** (Windows) or **U** (console/Linux) limits the selection to detected updates. Nothing installs merely because you accept the initial selection prompt.

Current versions are skipped. A locally newer version is never downgraded. If a version cannot be compared reliably, the installer reports that and skips replacing an existing installation; review the official release manually. Download-only mode remains available. New apps and add-ons remain optional selections.

## What installations are detected?

- **Windows:** Apps & features / uninstall registry entries for the current user and machine, including 32-bit entries. This includes official MSI installs made by this script, by hand, or through the launcher. Matching uses the app's exact normalized name. Portable copies without an uninstall entry are not detected. No `Win32_Product` scan or MSI repair is used.
- **Linux / Docker:** Private installations recorded by this installer, provided their installation directory still exists. Updating creates a new private version and retains the previous directory; save work and close the old app, then launch the new copy from the returned `desktop` path. The installer does not migrate launcher shortcuts.
- **Linux system packages:** Installed Debian/RPM packages are reported when their package database is available. Update those using the native package manager or the launcher; the script skips them to avoid creating a duplicate private copy. AppImages, Flatpaks and unrelated portable/source installations are not detected. Missing package metadata and unusual version strings may require manual review.

Windows performs a fresh registry/release check before each selected action; Linux uses a fresh stable release before downloading. The catalog API includes `installed_version`, `installed_source`, and `update_state` for app rows. Catalog refresh timers discover updates; they do not install them. Pullio updates the worker image separately from the installed Craft apps.

## Built-in update features checked October 12, 2026

This audit inspected the latest published stable tag for each app, including release source archives, update-related code, menus, and manifests. “Not found” means no software updater was found in those reviewed sources; it is not a guarantee about future releases or every installation. The installer does not invoke app updaters or run installed apps to discover their versions.

| App | Release inspected | Built-in software update behavior |
| --- | --- | --- |
| ArtCraft Launcher | [v0.3.2](https://github.com/storytold/craft-launcher/tree/v0.3.2) | Checks installed apps, offers installation of updates, and has its own self-update implementation. [Self-update source](https://github.com/storytold/craft-launcher/blob/v0.3.2/crates/native/src/self_update.rs). |
| PdfCraft | [v0.7.1](https://github.com/storytold/pdfcraft/tree/v0.7.1) | **Help → Check for updates** checks when requested and offers the release download page. It explicitly does not download or install updates and does not check at startup. [Implementation](https://github.com/storytold/pdfcraft/blob/v0.7.1/crates/ui-egui/src/updates.rs). |
| PhotoCraft | [v0.8.2](https://github.com/storytold/photocraft/tree/v0.8.2) | Not found. Its released [distribution scorecard](https://github.com/storytold/photocraft/blob/v0.8.2/scorecard/distribution.toml) marks update checks as missing; a planned feature is not a shipped updater. |
| LightCraft | [v0.7.1](https://github.com/storytold/lightcraft/tree/v0.7.1) | Not found in reviewed release sources. |
| VectorCraft | [v0.10.0](https://github.com/storytold/vectorcraft/tree/v0.10.0) | Not found in reviewed release sources. |
| FilmCraft | [v0.7.2](https://github.com/storytold/filmcraft/tree/v0.7.2) | Not found in reviewed release sources. |
| EffectCraft | [v0.9.2](https://github.com/storytold/effectcraft/tree/v0.9.2) | Not found in reviewed release sources. |
| DesignCraft | [v0.7.1](https://github.com/storytold/designcraft/tree/v0.7.1) | Not found in reviewed release sources. |
| WordCraft | [v0.6.1](https://github.com/storytold/wordcraft/tree/v0.6.1) | Not found in reviewed release sources. |
| GridCraft | [v0.6.1](https://github.com/storytold/gridcraft/tree/v0.6.1) | Not found in reviewed release sources. |
| DeckCraft | [v0.6.1](https://github.com/storytold/deckcraft/tree/v0.6.1) | Not found in reviewed release sources. |
| CADCraft | [v0.6.2](https://github.com/storytold/cadcraft/tree/v0.6.2) | Not found in reviewed release sources. |
| SoundCraft | [v0.6.1](https://github.com/storytold/soundcraft/tree/v0.6.1) | Not found. “Auto-update active configuration” updates a window layout, not the installed software. |
| ArtCraft AI studio | [artcraft-v0.41.0](https://github.com/storytold/artcraft/tree/artcraft-v0.41.0) | A software updater was not confirmed in the reviewed release sources/manifests. Do not assume the studio maintains the other Craft apps. |

These audited versions are documentation only. The installer always queries GitHub at runtime rather than hardcoding these versions.
