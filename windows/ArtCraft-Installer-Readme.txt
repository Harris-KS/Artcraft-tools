ARTCRAFT WINDOWS INSTALLER SELECTOR

GET STARTED
1. Extract the ZIP into a folder.
2. Keep Run-ArtCraft-Installer.cmd and Install-ArtCraft.ps1 together.
3. Double-click Run-ArtCraft-Installer.cmd.
4. Wait for the GitHub release checks. Check the numbered entries you want,
   then click Install selected. Select a row to read its description/comparison.
5. Complete each official Windows installer wizard. Windows may request admin
   permission for apps that install into Program Files.

No installations were performed while developing this script.

HOW THE LATEST-VERSION CHECK WORKS
Each run fetches /repos/storytold/<app>/releases/latest from GitHub's API.
It uses GitHub's latest published stable release, excluding drafts and prereleases;
it does not build unreleased development commits. Versions and asset URLs are
discovered at runtime, never hardcoded. The selected items are checked again
immediately before downloading, in case a release appeared while the menu was open.

Windows CPU architecture is detected (x64, arm64, or x86). Only an MSI matching
that architecture is selectable. An app without a matching package, or whose
release cannot be checked, appears unavailable with an explanation. There is no
silent fallback to an old download. The script uses official GitHub packages
directly, so neither winget nor Git is required.

Existing installations are handled by each app's own Windows installer. Running
this selector again installs the current release, which may upgrade or offer
maintenance/repair depending on the app. It does not detect installed versions
or schedule background updates. It never automatically restarts Windows.

The catalog starts with the 12 current Craft suite apps, ArtCraft, and its launcher.
Each run also scans ALL public organization repositories, following pagination.
Additional active, non-fork repositories appear as discovered items with their
GitHub descriptions. Compatible Windows MSI releases automatically become
installable entries, without editing this script. Repositories without suitable
installers are listed for review, including libraries and source-only projects.
Archived/forked/disabled projects are excluded from the Windows selection menu.

Release files ending in .wasm or .jsx, and ZIPs named as plug-ins/add-ons/extensions,
are automatically listed as optional release-resource candidates. Selecting them
downloads and verifies their published SHA-256; follow each repository's README
to load/install them. The script does not guess their target app or compatibility.
The latest release is rechecked before downloading the selected resource.
This is live catalog discovery, not automatic replacement of this script's code.
New package formats or source-only add-ons with special requirements may still
need a future script implementation. It does not scan every file in source trees.
Discovery failures are explicitly reported; the known catalog remains usable.

APP DESCRIPTIONS AND PAID-APP COMPARISONS
PhotoCraft   - Layers, masks, image editing: Adobe Photoshop-style workflow.
LightCraft   - Photo library and RAW development: Adobe Lightroom Classic.
VectorCraft  - Vector illustration and SVG: Adobe Illustrator.
FilmCraft    - Video timeline, color and audio: Adobe Premiere Pro.
EffectCraft  - Motion graphics and compositing: Adobe After Effects.
DesignCraft  - Page layout and publishing: Adobe InDesign.
PdfCraft     - Reading, organizing and editing PDFs: Adobe Acrobat Pro.
WordCraft    - Writing and document layout: Microsoft Word.
GridCraft    - Spreadsheets, formulas and data: Microsoft Excel.
DeckCraft    - Slide presentations: Microsoft PowerPoint.
CADCraft     - Computer-aided design and drafting: Autodesk AutoCAD.
SoundCraft   - Audio recording, editing and mixing: Avid Pro Tools.
ArtCraft     - AI image/video studio: no single direct paid counterpart.
Launcher     - Install/update/open the suite: no direct paid counterpart.

Comparisons describe intended workflow and product category, not full feature
parity or compatibility with the paid apps' plug-ins. These projects are young;
their individual READMEs and roadmaps describe the current limits.

OPTIONAL ADD-ONS FOUND IN THE REPOSITORIES
The menu includes two documented examples, using the latest stable parent app's
release tag as the source version. If a sample is absent from that tag, the menu
explains that it is unavailable.

PhotoCraft Invert example:
- Fetches the repository's prebuilt invert.wasm test/example module and checks
  its Git blob ID before saving it in the run folder.
- After download, in PhotoCraft choose Filter > Plug-ins > Install Plug-in and
  select photocraft-invert.wasm. The summary prints its full location.
- This is an optional example filter, not a separate commercial plug-in pack.
- It requires this manual loading step; the script does not edit PhotoCraft's
  preferences or automatically activate it in a running session.

EffectCraft Posterize Bands example:
- Reduces luminance into tinted bands, with levels, mix, tint and invert controls.
- It is source code, not a published standalone installer. Requires a recent
  Rust toolchain with cargo and rustup on PATH (https://rustup.rs).
- The entry is disabled if those commands are missing. The script does not
  install the full Rust toolchain automatically.
- Selecting it fetches Cargo.toml and src/lib.rs from the current release tag,
  verifies Git blob IDs, adds the wasm32-unknown-unknown Rust target if needed,
  builds the standalone example, and copies posterize_bands.wasm into
  %APPDATA%\EffectCraft\Plug-ins (or EFFECTCRAFT_CONFIG_DIR\Plug-ins).
- Restart EffectCraft to load it. Selecting the add-on alone does not install
  its parent app: also check EffectCraft if you do not already have it.
- An existing copy of the module is backed up before replacement.

EffectCraft's Ease Presets panel and bundled ScriptUI examples already ship with
the app. Open Ease Presets through its Window menu; no extra installation needed.
craft-fonts is an optional font input for source builds; craft-libs contains Rust
source libraries. They are not separately required end-user plug-ins. The script
does not install them as add-ons, or assume native Adobe plug-ins will work.

OTHER RUN OPTIONS (IN POWERSHELL, FROM THE EXTRACTED FOLDER)

Numbered console menu with [x] toggles:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-ArtCraft.ps1 -Console
Type 1,3,5 to toggle those entries; A selects all available apps (not add-ons),
N clears the selection, I installs/downloads selected entries, Q exits.

Check versions and availability without installing or opening a selection window:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-ArtCraft.ps1 -CheckOnly

Download verified packages without running installers:
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File .\Install-ArtCraft.ps1 -DownloadOnly
For Posterize Bands, this option saves source without building or installing it.

GitHub may rate-limit repeated runs. Wait and rerun, or optionally set an existing
GitHub token for the current PowerShell session before launching the script:
$env:GITHUB_TOKEN = '<your-token>'
No private-repository permissions are needed for these public repositories.
The script sends that token only to api.github.com, not to asset downloads.

VERIFICATION AND LOGS
MSI packages must match the release asset's SHA-256 digest or SHA256SUMS.txt.
Missing or incorrect hashes stop that item before installation. Add-on source
files are checked against the Git blob IDs returned by GitHub's contents API.
This checks file integrity against GitHub metadata, not an independent audit
of the app or add-on's source code.

Downloads are retained with results.json and each MSI's install.log under:
%LOCALAPPDATA%\ArtCraft-Installer\runs\<unique-run-folder>
The script continues with other selected items if one fails, and reports results.
UAC cancellation and installer errors are shown in the summary. Exit code 1 means
one or more items failed; 0 means completion or no selection.

REQUIREMENTS AND VALIDATION
Windows 10/11, built-in Windows PowerShell 5.1, internet access to GitHub.
The CMD launcher uses STA mode for the checkbox window and a process-local
execution policy setting; it does not change your machine's execution policy.
PowerShell 5.1 syntax and 29 mocked behavioral checks passed. Actual GitHub API
downloads and MSI installations were not tested in this restricted environment.

SOURCES
Suite catalog and Windows installation formats:
https://github.com/storytold/craft-launcher
PhotoCraft packages, example and plug-in loading:
https://github.com/storytold/photocraft/releases/latest
https://github.com/storytold/photocraft/blob/main/docs/plugins.md
EffectCraft extension paths, bundled tools and sample build instructions:
https://github.com/storytold/effectcraft/blob/main/docs/plugins.md
Source font resources:
https://github.com/storytold/craft-fonts

LINUX / DOCKER / LOCAL LLM EDITION
See linux-edge/README.txt for the Python Linux installer, Docker Compose worker,
HTTP API and stdio MCP bridge. The catalog scans newly posted repositories and
stable release resources. An LLM tool client can query current installed CLI
tools and generate files; model training is not needed. It is independent of
Ollama, llama.cpp or any specific inference engine. The LLM setup must support
tool execution over HTTP or MCP. Linux file generation is limited to apps that
ship compatible command-line tools; desktop GUIs are not hosted by the worker.
