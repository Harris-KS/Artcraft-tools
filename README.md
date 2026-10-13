# Artcraft Tools

Windows and Linux installers, a Docker file-generation worker, and local-LLM integration tools for the [Storytold / ArtCraft apps](https://github.com/orgs/storytold/repositories?type=all).

The installers discover new public repositories and published app versions at runtime. The Docker worker exposes installed command-line tools through a local HTTP API and an MCP bridge. Pullio can update the worker's container image after it has been published to a registry.

## Choose a starting point

| What you want | Start here |
| --- | --- |
| Try the desktop apps on Windows | [Windows installer ZIP](https://github.com/Harris-KS/Artcraft-tools/releases/download/installers/ArtCraft-Windows-Installer.zip) |
| Install packages privately on Linux | [Linux installer ZIP](https://github.com/Harris-KS/Artcraft-tools/releases/download/installers/ArtCraft-Linux-Installer.zip) |
| Use installed CLI tools with a local LLM | [Docker / LLM worker ZIP](https://github.com/Harris-KS/Artcraft-tools/releases/download/installers/ArtCraft-Docker-LLM.zip) |
| Automatically update the Docker worker | [Pullio deployment ZIP](https://github.com/Harris-KS/Artcraft-tools/releases/download/installers/ArtCraft-Pullio-Setup.zip) |
| Publish this repository's Docker image | [Image publishing source ZIP](https://github.com/Harris-KS/Artcraft-tools/releases/download/installers/ArtCraft-Image-Publishing.zip) |

**Choose one package, extract it, and read its `START-HERE.txt`.** Each package includes the companion files for that option. You do not need the other packages. The publishing-source package is for maintainers; the other four are for installation/deployment. The Docker package builds locally; the Pullio package deploys a published worker image and keeps it updated.

These downloads are automatically rebuilt by GitHub Actions when their source files change. [All downloads and checksums](https://github.com/Harris-KS/Artcraft-tools/releases/tag/installers). Developers can still [download the full repository](https://github.com/Harris-KS/Artcraft-tools/archive/refs/heads/main.zip).

## Windows

1. [Download the Windows installer ZIP](https://github.com/Harris-KS/Artcraft-tools/releases/download/installers/ArtCraft-Windows-Installer.zip).
2. Right-click the downloaded ZIP and choose **Extract All**.
3. Open the extracted `ArtCraft-Windows-Installer` folder.
4. Double-click **Run-ArtCraft-Installer.cmd**. Leave **Install-ArtCraft.ps1** in that same folder.

Run it from the extracted folder, rather than directly inside the ZIP. If you already cloned the full repository, open its `windows` folder and run the launcher there.

The script checks GitHub, shows numbered checkboxes, and installs the official MSI packages for your Windows architecture. Each known app has a description and paid-app comparison. New compatible apps are discovered automatically; repositories without supported installers remain review-only entries. Downloads must match published SHA-256 checksums.

Optional commands, from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\Install-ArtCraft.ps1 -Console
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\Install-ArtCraft.ps1 -CheckOnly
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File .\windows\Install-ArtCraft.ps1 -DownloadOnly
```

Requires Windows PowerShell 5.1 and internet access. Windows may request administrator permission for an app's MSI. [Detailed Windows instructions](windows/ArtCraft-Installer-Readme.txt).

## Native Linux

Requires Python 3.10+ on x64 or ARM64. No pip dependencies are needed. Extract the Linux installer ZIP, then open a terminal in its extracted directory. Keep its `linux-edge` folder together; the launcher needs `artcraft_edge.py` beside it.

```sh
sh linux-edge/run-installer.sh
sh linux-edge/run-installer.sh --check
sh linux-edge/run-installer.sh --install wordcraft
```

Packages are unpacked into `~/.local/share/artcraft-edge/apps`; `.tar.gz` is preferred and `.deb` extraction requires `dpkg-deb`. This does not run apt installation hooks or set desktop associations. Native Linux still needs compatible runtime libraries. Release add-on candidates are verified downloads requiring their documented loading/installation steps.

## Docker: build and try it locally

Docker Engine, Docker Compose, and Python 3 are prerequisites for the setup scripts. From `linux-edge`:

```sh
cd linux-edge
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the generated value into `.env` as `ARTCRAFT_API_TOKEN`, then:

```sh
docker compose up -d --build
docker compose exec artcraft python3 artcraft_edge.py
```

The second command opens the numbered installer menu inside the worker. To install a particular app:

```sh
docker compose exec artcraft python3 artcraft_edge.py --install wordcraft
```

The worker runs as a non-root user and exposes port `8787` on localhost. Installed apps and generated files are stored in persistent named volumes. It provides headless CLI execution, rather than a remote desktop. Apps without a usable packaged CLI cannot generate files through this service.

## Connect a local LLM

The worker is independent of Ollama, llama.cpp, or any other inference engine. Your client must execute HTTP tools or support MCP. Fine-tuning the model is not required to connect these tools.

For an MCP-capable client, configure a stdio server using:

```json
{
  "command": "python3",
  "args": ["/absolute/path/to/Artcraft-tools/linux-edge/mcp_bridge.py"],
  "env": {
    "ARTCRAFT_API_URL": "http://127.0.0.1:8787",
    "ARTCRAFT_API_TOKEN": "YOUR_WORKER_TOKEN"
  }
}
```

The client's enclosing MCP configuration format varies. On Windows, the Python command may be `python`. The bridge runs on the client's host and connects to the worker. Keep credentials in client configuration, rather than model prompts or this repository.

Tools:

- `artcraft_catalog`: lists discovered apps/resources and installed CLIs; `refresh: true` requests a fresh GitHub scan.
- `artcraft_run`: runs an installed CLI with an argument array and a timeout. Inspect `--help` first; commands differ by app.

The underlying authenticated JSON API provides `GET /health`, `GET /catalog`, `POST /refresh`, and `POST /run`. Requests use `Authorization: Bearer <token>`. API installation is disabled by default; the supplied MCP bridge does not expose installation.

An example job after installing WordCraft and copying an input file into the worker:

```sh
docker compose cp ./report.docx artcraft:/files/report.docx
```

Send this body to `POST /run` using your client:

```json
{"app":"wordcraft","args":["convert","/files/report.docx","report.pdf"],"timeout":120}
```

The result reports the exit code, diagnostics, and a unique job directory. Retrieve an output with:

```sh
docker compose cp artcraft:/files/jobs/JOB_ID/report.pdf ./report.pdf
```

Check the actual output before treating a job as successful. The apps are early projects with varying feature coverage.

## Publish the worker image

This repository contains an active publishing workflow at `.github/workflows/publish-image.yml`. Pushes to `main` affecting the worker/workflow trigger a build. You can also select **Actions → Publish ArtCraft edge image → Run workflow**. Weekly builds refresh base-image and dependency layers.

The workflow builds both `linux/amd64` and `linux/arm64` images and publishes:

```text
ghcr.io/harris-ks/artcraft-tools:latest
ghcr.io/harris-ks/artcraft-tools:sha-COMMIT_SHA
```

GitHub Container Registry stores these images on GitHub servers under the account's Packages. GitHub Actions receives its own `GITHUB_TOKEN` for publication; do not add a personal token to the workflow. The image cannot be pulled until the first build succeeds.

First publication normally creates a private package. For the supplied Pullio setup, change the package visibility to **public** in GitHub Package settings. Public GHCR images can be pulled anonymously. A private image requires additional registry login/authfile configuration.

## Enable automatic container updates with Pullio

After the published image is accessible, run this from your Linux deployment's `linux-edge` directory:

```sh
bash setup-pullio.sh ghcr.io/harris-ks/artcraft-tools:latest
```

The script generates an API token if necessary, saves the image and project path in `.env`, backs up the original Compose file once, makes the registry/Pullio template the default `compose.yaml`, and starts the worker and Pullio service. Existing named volumes remain attached when setup runs in the same deployment directory.

Pullio checks the rolling image tag and replaces the worker when its image changes. This checks every six hours by default:

```dotenv
PULLIO_INTERVAL_SECONDS=21600
```

Separately, the worker discovers new GitHub apps/resources and versions every six hours:

```dotenv
ARTCRAFT_REFRESH_SECONDS=21600
```

Both settings live in `.env`. The catalog timer does not automatically install app updates. Pullio updates the worker container, while app downloads and generated files remain in persistent volumes.

```sh
docker compose logs -f pullio
```

Use the setup script rather than launching `compose.pullio.yaml` with `-f`: upstream Pullio expects the default Compose filename at the original host working-directory path. This wrapper uses tagged labels to scope updates to the ArtCraft worker. Pullio requires the Docker socket, has Docker-daemon access, and prunes dangling Docker images. Updating the container can interrupt an active job.

The publishing workflow builds updates that exist in this repository. Neither GHCR nor Pullio creates new code or imports arbitrary scripts from upstream projects.

## Files

```text
windows/                    PowerShell installer, double-click launcher, detailed guide
linux-edge/                 Linux installer, local API, MCP bridge, Docker configuration
linux-edge/pullio/          Pullio wrapper image and scheduled runner
linux-edge/publishing/      Portable copy of the publishing workflow for standalone bundles
.github/workflows/          Active image-publication and validation workflows
tests/                      Mocked behavioral tests; no app installation required
```

The discovery rules support the documented package formats and certain release resources. Source-only add-ons with custom build/install steps need explicit support. Known example add-ons in the Windows selector are PhotoCraft Invert and EffectCraft Posterize Bands; some resources are already bundled with their parent app. See the detailed platform guides for prerequisites and limitations.

## Validation

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

On Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\Test-ArtCraft-Installer.ps1
```

The Python tests use mocked GitHub requests, downloads, HTTP server construction, and app processes. They cover discovery, version refreshes, checksums, archive handling, MCP, the API, catalog scheduling, and Pullio setup-file generation. The Windows suite uses mocked downloads and releases. Passing these tests does not establish compatibility of actual Craft binaries or a successful Docker deployment; build the image and run a small export on your server.

## References

- [ArtCraft launcher and suite catalog](https://github.com/storytold/craft-launcher)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Pullio documentation](https://hotio.dev/scripts/pullio/)
- [Windows guide](windows/ArtCraft-Installer-Readme.txt)
- [Linux/API/Pullio guide](linux-edge/README.txt)
