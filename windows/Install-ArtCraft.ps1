#requires -Version 5.1
<#
Windows installer selector. Run with Windows PowerShell -STA.
Every run queries GitHub's latest stable release; versions are never hardcoded.
Optional GITHUB_TOKEN environment variable increases GitHub's API allowance.
#>
[CmdletBinding()]
param([switch]$Console, [switch]$CheckOnly, [switch]$DownloadOnly)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$script:Headers = @{ 'User-Agent' = 'ArtCraft-Windows-Selector'; Accept = 'application/vnd.github+json' }
if ($env:GITHUB_TOKEN) { $script:Headers.Authorization = 'Bearer ' + $env:GITHUB_TOKEN }

function Get-Catalog {
    $rows = @(
        @('photocraft','PhotoCraft','Layers, masks and raster image editing','Adobe Photoshop'),
        @('lightcraft','LightCraft','Photo library and non-destructive RAW development','Adobe Lightroom Classic'),
        @('vectorcraft','VectorCraft','Vector illustration, paths and SVG graphics','Adobe Illustrator'),
        @('filmcraft','FilmCraft','Timeline-based video editing, color and audio','Adobe Premiere Pro'),
        @('effectcraft','EffectCraft','Motion graphics, animation and compositing','Adobe After Effects'),
        @('designcraft','DesignCraft','Page layout and print publishing','Adobe InDesign'),
        @('pdfcraft','PdfCraft','Read, organize and edit PDF documents','Adobe Acrobat Pro'),
        @('wordcraft','WordCraft','Word processing and document layout','Microsoft Word'),
        @('gridcraft','GridCraft','Spreadsheets, formulas and data','Microsoft Excel'),
        @('deckcraft','DeckCraft','Slide presentations and slide shows','Microsoft PowerPoint'),
        @('cadcraft','CADCraft','Computer-aided design and drafting','Autodesk AutoCAD'),
        @('soundcraft','SoundCraft','Audio recording, editing and mixing','Avid Pro Tools'),
        @('artcraft','ArtCraft','AI-assisted image and video creation','Creative AI studio; no single direct paid counterpart'),
        @('craft-launcher','ArtCraft Launcher','Install, update and open the Craft suite','Suite manager; no direct paid counterpart')
    )
    foreach ($r in $rows) {
        [pscustomobject]@{ Repo=$r[0]; Name=$r[1]; Description=$r[2]; Compare=$r[3]; Kind='App'; SourcePath=''; Parent=''; Available=$false; Version=''; Status='Not checked'; Release=$null; Asset=$null; Source=$null }
    }
    [pscustomobject]@{ Repo='photocraft'; Name='PhotoCraft Invert example plug-in'; Description='Optional sample WASM filter. Downloads the file; load it with Filter > Plug-ins > Install Plug-in in PhotoCraft.'; Compare='Similar to Photoshop Invert; sample, not a commercial plug-in replacement'; Kind='Wasm'; SourcePath='crates/plugins/tests/fixtures/invert.wasm'; Parent='photocraft'; Available=$false; Version=''; Status='Not checked'; Release=$null; Asset=$null; Source=$null }
    [pscustomobject]@{ Repo='effectcraft'; Name='EffectCraft Posterize Bands example plug-in'; Description='Optional sample effect that creates tinted luminance bands. Builds with Rust and installs in EffectCraft Plug-ins. Requires cargo and rustup.'; Compare='Posterize/stylize effect for an After Effects-style workflow'; Kind='Build'; SourcePath='examples/plugins/posterize-bands'; Parent='effectcraft'; Available=$false; Version=''; Status='Not checked'; Release=$null; Asset=$null; Source=$null }
}

function Get-WindowsArchitecture {
    $cpu = $env:PROCESSOR_ARCHITEW6432
    if (-not $cpu) { $cpu = $env:PROCESSOR_ARCHITECTURE }
    switch ($cpu) { 'AMD64' { 'x64' }; 'ARM64' { 'arm64' }; 'x86' { 'x86' }; default { throw "Unsupported Windows architecture: $cpu" } }
}

function Get-ReleaseAssetKey([string]$Name) {
    $Name -replace '\d+\.\d+\.\d+(?:[-+]\d+)?','VERSION'
}

function Expand-LiveCatalog($Catalog, [string]$Architecture) {
    # Refresh the organization itself, so newly posted projects need no script edit.
    $repos = @()
    $page = 1
    do {
        $batch = @(Get-GitHubJson "orgs/storytold/repos?type=public&per_page=100&page=$page&sort=full_name")
        $repos += $batch
        $page++
    } while ($batch.Count -eq 100)
    $known = @($Catalog | ForEach-Object { $_.Repo } | Select-Object -Unique)
    $script:DiscoveryReleases = @{}
    foreach ($repo in $repos) {
        if ($repo.owner.login -ne 'storytold' -or $repo.name -notmatch '^[A-Za-z0-9_.-]+$') { continue }
        if ($repo.archived -or $repo.fork -or $repo.disabled) { continue }
        Write-Host "Discovering $($repo.name)..."
        $release = $null; $reason = ''
        try { $release = Get-GitHubJson "repos/storytold/$($repo.name)/releases/latest" }
        catch { $reason = $_.Exception.Message }
        if ($release) { $script:DiscoveryReleases[$repo.name] = $release }
        if ($known -notcontains $repo.name) {
            $item = [pscustomobject]@{ Repo=$repo.name; Name=('Discovered: ' + $repo.name); Description=([string]$repo.description); Compare='Not documented; see repository README'; Kind='Repository'; SourcePath=''; Parent=''; Available=$false; Version=''; Status=$reason; Release=$null; Asset=$null; Source=$null }
            if (-not $item.Description) { $item.Description='Newly discovered GitHub repository; no description provided.' }
            if ($release) {
                $item.Version=$release.tag_name; $item.Release=$release
                try { $item.Asset=Select-WindowsMsi $release $Architecture; $item.Kind='App' }
                catch { $item.Status='Repository discovered; no unambiguous Windows MSI. Review its README for installation.' }
            }
            $Catalog += $item
        }
        if ($release -and -not $release.draft -and -not $release.prerelease) {
            foreach ($asset in $release.assets) {
                # Unknown resources are offered as verified downloads, never silently deployed.
                if ($asset.name -notmatch '\.(wasm|jsx)$' -and $asset.name -notmatch '(?i)(plugin|addon|add-on|extension).*\.zip$') { continue }
                $Catalog += [pscustomobject]@{ Repo=$repo.name; Name=('Release add-on candidate: ' + $asset.name); Description='Optional release resource. Downloads with checksum verification; follow the repository instructions to load it. Compatibility is not inferred from the name.'; Compare='Not documented; see repository README'; Kind='ReleaseResource'; SourcePath=(Get-ReleaseAssetKey $asset.name); Parent=$repo.name; Available=$false; Version=$release.tag_name; Status='Not checked'; Release=$release; Asset=$asset; Source=$null }
            }
        }
    }
    $Catalog
}

function Get-GitHubJson([string]$Path) {
    # Tokens are only sent to api.github.com, never to installer downloads.
    try { Invoke-RestMethod -Uri ('https://api.github.com/' + $Path) -Headers $script:Headers -TimeoutSec 45 }
    catch {
        $status = 0
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        switch ($status) {
            404 { throw 'No published release or requested file was found.' }
            403 { throw 'GitHub refused the request (possibly API rate limit). Wait or set GITHUB_TOKEN and rerun.' }
            429 { throw 'GitHub rate limit reached. Wait or set GITHUB_TOKEN and rerun.' }
            default { throw "GitHub request failed: $($_.Exception.Message)" }
        }
    }
}

function Select-WindowsMsi($Release, [string]$Architecture) {
    $archPattern = switch ($Architecture) { 'x64' { '(?:x64|x86_64|amd64)' }; 'arm64' { '(?:arm64|aarch64)' }; 'x86' { '(?:x86|i686)' } }
    $candidates = @($Release.assets | Where-Object {
        $_.name -match '\.msi$' -and $_.name -match ("(?:^|[-_])" + $archPattern + "(?:[-_.]|$)")
    })
    if ($candidates.Count -eq 0) { throw "No Windows $Architecture MSI in the latest release." }
    if ($candidates.Count -gt 1) { throw 'Multiple matching MSI packages; select a package manually on the release page.' }
    $candidates[0]
}

function Update-Catalog($Catalog, [string]$Architecture, [switch]$UseDiscoveryCache) {
    $releases = @{}
    foreach ($item in $Catalog) {
        Write-Host "Checking $($item.Name)..."
        try {
            if ($item.Kind -eq 'Repository') { continue }
            if (-not $releases.ContainsKey($item.Repo)) {
                try {
                    if ($UseDiscoveryCache -and $script:DiscoveryReleases.ContainsKey($item.Repo)) { $releases[$item.Repo]=$script:DiscoveryReleases[$item.Repo] }
                    else { $releases[$item.Repo] = Get-GitHubJson "repos/storytold/$($item.Repo)/releases/latest" }
                }
                catch { $releases[$item.Repo] = $_.Exception.Message }
            }
            $release = $releases[$item.Repo]
            if ($release -is [string]) { throw $release }
            if ($release.draft -or $release.prerelease) { throw 'Latest endpoint returned an unpublished or prerelease build.' }
            $item.Release = $release
            $item.Version = $release.tag_name
            if ($item.Kind -eq 'App') {
                $item.Asset = Select-WindowsMsi $release $Architecture
                $item.Status = 'Ready'
            } elseif ($item.Kind -eq 'ReleaseResource') {
                $matches = @($release.assets | Where-Object { (Get-ReleaseAssetKey $_.name) -ceq $item.SourcePath })
                if ($matches.Count -ne 1) { throw 'Resource is missing or ambiguous in the latest release.' }
                $item.Asset=$matches[0]
                $item.Status='Verified download; manual installation per repository README'
            } else {
                $ref = [uri]::EscapeDataString($release.tag_name)
                $item.Source = Get-GitHubJson "repos/storytold/$($item.Repo)/contents/$($item.SourcePath)?ref=$ref"
                if ($item.Kind -eq 'Build') {
                    if (-not (Get-Command cargo -ErrorAction SilentlyContinue) -or -not (Get-Command rustup -ErrorAction SilentlyContinue)) {
                        throw 'Source available; install Rust (cargo + rustup) from rustup.rs, then rerun to enable.'
                    }
                    $item.Status = 'Build from release source (may download Rust WASM target)'
                } else {
                    if ($item.Source.type -ne 'file' -or $item.Source.encoding -ne 'base64') { throw 'Example WASM file is not available through GitHub contents.' }
                    $item.Status = 'Download sample; load inside PhotoCraft'
                }
            }
            $item.Available = $true
        } catch { $item.Available = $false; $item.Status = $_.Exception.Message }
    }
}

function Assert-ReleaseUrl([string]$Url, [string]$Repo) {
    $uri = [uri]$Url
    if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'github.com' -or -not $uri.AbsolutePath.StartsWith("/storytold/$Repo/releases/download/", [StringComparison]::Ordinal)) {
        throw 'Download URL is outside the official repository release assets.'
    }
}

function Save-VerifiedInstaller($Item, [string]$Folder) {
    $asset = $Item.Asset
    $name = [string]$asset.name
    if ([IO.Path]::GetFileName($name) -cne $name -or $name -notmatch '^[A-Za-z0-9_. -]+\.(msi|wasm|jsx|zip)$') { throw 'Unsafe package filename.' }
    Assert-ReleaseUrl $asset.browser_download_url $Item.Repo
    $expected = ''
    if ($asset.digest -match '^sha256:([a-fA-F0-9]{64})$') { $expected = $Matches[1] }
    if (-not $expected) {
        $sums = @($Item.Release.assets | Where-Object { $_.name -ieq 'SHA256SUMS.txt' })
        if ($sums.Count -ne 1) { throw 'No published SHA-256 digest or SHA256SUMS.txt; refusing to run an unverified installer.' }
        Assert-ReleaseUrl $sums[0].browser_download_url $Item.Repo
        $sumFile = Join-Path $Folder 'SHA256SUMS.txt'
        Invoke-WebRequest -UseBasicParsing -Uri $sums[0].browser_download_url -OutFile $sumFile -TimeoutSec 120
        foreach ($line in (Get-Content -LiteralPath $sumFile)) {
            if ($line -match '^([a-fA-F0-9]{64})\s+\*?(.+?)\s*$') {
                if ($Matches[2] -ceq $name) { $expected = $Matches[1]; break }
            }
        }
        if (-not $expected) { throw 'Installer is missing from SHA256SUMS.txt.' }
    }
    $path = Join-Path $Folder $name
    Write-Host "Downloading $name..."
    Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $path -TimeoutSec 900
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $expected) { throw 'SHA-256 mismatch. This download will not be installed.' }
    $path
}

function Save-GitHubSourceFile($Source, [string]$Destination) {
    if ($Source.type -ne 'file' -or $Source.encoding -ne 'base64') { throw 'Expected a base64-encoded GitHub source file.' }
    $bytes = [Convert]::FromBase64String($Source.content)
    # Verify GitHub's Git blob ID: SHA1("blob <byte-count>\0" + file bytes).
    $prefix = [Text.Encoding]::ASCII.GetBytes("blob $($bytes.Length)`0")
    $sha = [Security.Cryptography.SHA1]::Create()
    try { $actual = [BitConverter]::ToString($sha.ComputeHash([byte[]]($prefix + $bytes))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($actual -cne $Source.sha) { throw 'GitHub source blob verification failed.' }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Destination)) | Out-Null
    [IO.File]::WriteAllBytes($Destination, $bytes)
}

function Install-Addon($Item, [string]$Folder, [switch]$OnlyDownload) {
    if ($Item.Kind -eq 'ReleaseResource') {
        $path = Save-VerifiedInstaller $Item $Folder
        return "Verified resource saved: $path. Load/install using https://github.com/storytold/$($Item.Repo) instructions."
    }
    if ($Item.Kind -eq 'Wasm') {
        $destination = Join-Path $Folder 'photocraft-invert.wasm'
        Save-GitHubSourceFile $Item.Source $destination
        return "Saved $destination. In PhotoCraft: Filter > Plug-ins > Install Plug-in; choose this file."
    }
    $ref = [uri]::EscapeDataString($Item.Release.tag_name)
    $buildFolder = Join-Path $Folder 'posterize-bands'
    foreach ($relative in @('Cargo.toml','src/lib.rs')) {
        $source = Get-GitHubJson "repos/storytold/effectcraft/contents/$($Item.SourcePath)/$($relative)?ref=$ref"
        Save-GitHubSourceFile $source (Join-Path $buildFolder $relative)
    }
    if ($OnlyDownload) { return "Source saved to $buildFolder; no build or installation performed." }
    & rustup target add wasm32-unknown-unknown
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the Rust WebAssembly target.' }
    & cargo build --manifest-path (Join-Path $buildFolder 'Cargo.toml') --release --target wasm32-unknown-unknown --offline
    if ($LASTEXITCODE -ne 0) { throw 'Posterize Bands build failed. A recent stable Rust toolchain is required.' }
    $module = Join-Path $buildFolder 'target/wasm32-unknown-unknown/release/posterize_bands.wasm'
    $settings = Join-Path $env:APPDATA 'EffectCraft'
    if ($env:EFFECTCRAFT_CONFIG_DIR) { $settings = $env:EFFECTCRAFT_CONFIG_DIR }
    $pluginFolder = Join-Path $settings 'Plug-ins'
    [IO.Directory]::CreateDirectory($pluginFolder) | Out-Null
    $destination = Join-Path $pluginFolder 'posterize_bands.wasm'
    if (Test-Path -LiteralPath $destination) {
        Copy-Item -LiteralPath $destination -Destination ($destination + '.backup-' + [guid]::NewGuid().ToString('N'))
    }
    Copy-Item -LiteralPath $module -Destination $destination -Force
    "Installed $destination. Restart EffectCraft to load it."
}

function Show-ConsoleSelector($Catalog) {
    $checked = @{}
    while ($true) {
        Write-Host "`nArtCraft selector - toggle numbers, A = all apps, N = none, I = install/download, Q = quit"
        for ($i = 0; $i -lt $Catalog.Count; $i++) {
            $item = $Catalog[$i]
            $mark = ' '; if ($checked.ContainsKey($i)) { $mark = 'x' }; if (-not $item.Available) { $mark = '-' }
            Write-Host ('{0,2}. [{1}] {2} {3} | {4}' -f ($i+1),$mark,$item.Name,$item.Version,$item.Status)
            Write-Host "       $($item.Description) | Compare: $($item.Compare)"
        }
        $answer = (Read-Host 'Selection').Trim()
        switch ($answer.ToUpperInvariant()) {
            'Q' { return }
            'N' { $checked.Clear(); continue }
            'A' { for ($i=0; $i -lt $Catalog.Count; $i++) { if ($Catalog[$i].Available -and $Catalog[$i].Kind -eq 'App') { $checked[$i]=$true } }; continue }
            'I' { foreach ($i in ($checked.Keys | Sort-Object)) { $Catalog[$i] }; return }
        }
        foreach ($token in ($answer -split '[,\s]+')) {
            $number = 0
            if (-not [int]::TryParse($token,[ref]$number) -or $number -lt 1 -or $number -gt $Catalog.Count) { Write-Host "Invalid choice: $token"; continue }
            $index = $number-1
            if (-not $Catalog[$index].Available) { Write-Host 'This item is unavailable.'; continue }
            if ($checked.ContainsKey($index)) { $checked.Remove($index) } else { $checked[$index]=$true }
        }
    }
}

function Show-CheckboxSelector($Catalog, [string]$Architecture) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [Windows.Forms.Application]::EnableVisualStyles()
    $form = New-Object Windows.Forms.Form
    $form.Text = "ArtCraft - latest Windows $Architecture releases"
    $form.Size = New-Object Drawing.Size(1040,760)
    $form.MinimumSize = $form.Size
    $form.StartPosition = 'CenterScreen'
    $form.Font = New-Object Drawing.Font('Segoe UI',10)
    $intro = New-Object Windows.Forms.Label
    $intro.Text = 'Check numbered apps and optional add-ons. Select a row for its description. Unavailable items cannot be checked.'
    $intro.SetBounds(15,15,990,40)
    $list = New-Object Windows.Forms.CheckedListBox
    $list.CheckOnClick = $true
    $list.HorizontalScrollbar = $true
    $list.SetBounds(15,60,990,405)
    $list.Anchor = 'Top,Left,Right'
    for ($i=0; $i -lt $Catalog.Count; $i++) {
        $item=$Catalog[$i]
        [void]$list.Items.Add(('{0,2}. {1} | {2} | {3}' -f ($i+1),$item.Name,$item.Version,$item.Status))
    }
    $detail = New-Object Windows.Forms.TextBox
    $detail.Multiline=$true; $detail.ReadOnly=$true; $detail.ScrollBars='Vertical'
    $detail.SetBounds(15,480,990,145)
    $detail.Anchor='Top,Left,Right'
    $detail.Text = 'Paid-app names describe similar workflows, not full feature parity. Optional examples are separate from the apps. EffectCraft Ease Presets is already bundled. craft-fonts and craft-libs are build resources, not separately required plug-ins.'
    $list.Add_SelectedIndexChanged({
        if ($list.SelectedIndex -ge 0) {
            $item=$Catalog[$list.SelectedIndex]
            $detail.Text="$($item.Name)`r`n$($item.Description)`r`nCompare: $($item.Compare)`r`n$($item.Status)`r`nhttps://github.com/storytold/$($item.Repo)"
        }
    })
    $list.Add_ItemCheck({ param($sender,$eventArgs) if (-not $Catalog[$eventArgs.Index].Available) { $eventArgs.NewValue=[Windows.Forms.CheckState]::Unchecked } })
    $all=New-Object Windows.Forms.Button
    $all.Text='Select all apps'; $all.SetBounds(15,645,160,38)
    $all.Add_Click({ for ($i=0;$i -lt $Catalog.Count;$i++) { if ($Catalog[$i].Available -and $Catalog[$i].Kind -eq 'App') { $list.SetItemChecked($i,$true) } } })
    $none=New-Object Windows.Forms.Button
    $none.Text='Clear'; $none.SetBounds(190,645,100,38)
    $none.Add_Click({ for ($i=0;$i -lt $Catalog.Count;$i++) { $list.SetItemChecked($i,$false) } })
    $go=New-Object Windows.Forms.Button
    $go.Text='Install selected'; if ($DownloadOnly) { $go.Text='Download selected' }
    $go.SetBounds(650,645,190,38)
    $go.Add_Click({ if ($list.CheckedIndices.Count -gt 0) { $form.DialogResult=[Windows.Forms.DialogResult]::OK; $form.Close() } })
    $cancel=New-Object Windows.Forms.Button
    $cancel.Text='Cancel'; $cancel.SetBounds(855,645,150,38); $cancel.DialogResult='Cancel'
    $form.Controls.AddRange(@($intro,$list,$detail,$all,$none,$go,$cancel))
    $form.CancelButton=$cancel
    try { if ($form.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) { foreach ($i in $list.CheckedIndices) { $Catalog[$i] } } }
    finally { $form.Dispose() }
}

# Main: keeping helpers separate also permits tests without downloads/installs.
if ($env:OS -ne 'Windows_NT') { throw 'This script requires Windows.' }
$architecture = Get-WindowsArchitecture
$catalog = @(Get-Catalog)
try { $catalog = @(Expand-LiveCatalog $catalog $architecture) }
catch { Write-Warning "New-item discovery failed: $($_.Exception.Message). Showing known apps; this is not a complete organization scan." }
Update-Catalog $catalog $architecture -UseDiscoveryCache:([bool]$script:DiscoveryReleases)
if ($CheckOnly) {
    $catalog | Select-Object Name,Version,Available,Status,Description,Compare | Format-List
    if (@($catalog | Where-Object { $_.Kind -eq 'App' -and $_.Available }).Count -eq 0) { exit 1 }
    exit 0
}
if ($Console) { $selection = @(Show-ConsoleSelector $catalog) }
else {
    try { $selection = @(Show-CheckboxSelector $catalog $architecture) }
    catch { Write-Warning "Checkbox window could not open: $($_.Exception.Message). Using console menu."; $selection = @(Show-ConsoleSelector $catalog) }
}
if ($selection.Count -eq 0) { Write-Host 'No items selected.'; exit 0 }
$runFolder = Join-Path $env:LOCALAPPDATA ('ArtCraft-Installer/runs/' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($runFolder) | Out-Null
$results = @()
foreach ($item in $selection) {
    try {
        # Recheck immediately before processing: a newer release may have appeared while the menu was open.
        Update-Catalog @($item) $architecture
        if (-not $item.Available) { throw $item.Status }
        $folder = Join-Path $runFolder ($item.Repo + '-' + $item.Kind)
        [IO.Directory]::CreateDirectory($folder) | Out-Null
        if ($item.Kind -ne 'App') { $status = Install-Addon $item $folder -OnlyDownload:$DownloadOnly }
        else {
            $installer = Save-VerifiedInstaller $item $folder
            if ($DownloadOnly) { $status = "Verified installer saved: $installer" }
            else {
                $log = Join-Path $folder 'install.log'
                $arguments = '/i "' + $installer + '" /norestart /L*v "' + $log + '"'
                Write-Host "Installing $($item.Name) $($item.Version). Complete the Windows installer wizard."
                $process = Start-Process -FilePath "$env:SystemRoot/System32/msiexec.exe" -ArgumentList $arguments -Wait -PassThru
                switch ($process.ExitCode) {
                    0 { $status='Installed successfully' }
                    3010 { $status='Installed successfully; restart Windows when convenient' }
                    1641 { $status='Installed; restart initiated by Windows Installer' }
                    1602 { throw 'Installation canceled by user.' }
                    default { throw "Windows Installer exit code $($process.ExitCode). See $log" }
                }
            }
        }
        Write-Host $status -ForegroundColor Green
        $results += [pscustomobject]@{ Name=$item.Name; Version=$item.Version; Success=$true; Result=$status }
    } catch {
        Write-Warning "$($item.Name): $($_.Exception.Message)"
        $results += [pscustomobject]@{ Name=$item.Name; Version=$item.Version; Success=$false; Result=$_.Exception.Message }
    }
}
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runFolder 'results.json') -Encoding UTF8
$results | Format-Table Name,Version,Success,Result -Wrap
Write-Host "Downloads, results and MSI logs: $runFolder"
if (@($results | Where-Object { -not $_.Success }).Count -gt 0) { exit 1 }
