$ErrorActionPreference='Stop'
$scriptPath=Join-Path $PSScriptRoot '../windows/Install-ArtCraft.ps1'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($scriptPath,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]},$false) | ForEach-Object { Invoke-Expression $_.Extent.Text }
$script:Headers=@{'User-Agent'='test'}
$script:checks=0
function Assert($Condition,[string]$Message) { if (-not $Condition) { throw $Message }; $script:checks++ }
function Assert-Throws([scriptblock]$Action,[string]$Message) { $threw=$false; try { & $Action | Out-Null } catch { $threw=$true }; Assert $threw $Message }
$release=[pscustomobject]@{tag_name='v99.0.0';draft=$false;prerelease=$false;assets=@(
    [pscustomobject]@{name='photocraft-99.0.0-windows-x64.msi';browser_download_url='https://github.com/storytold/photocraft/releases/download/v99.0.0/photocraft-99.0.0-windows-x64.msi';digest=''},
    [pscustomobject]@{name='photocraft-99.0.0-windows-arm64.msi'},
    [pscustomobject]@{name='photocraft-99.0.0-windows-x86.msi'},
    [pscustomobject]@{name='photocraft-99.0.0-windows-x64-portable.zip'},
    [pscustomobject]@{name='photocraft-99.0.0-linux-x86_64.deb'}
)}
Assert ((Select-WindowsMsi $release 'x64').name -eq 'photocraft-99.0.0-windows-x64.msi') 'x64 selection'
Assert ((Select-WindowsMsi $release 'arm64').name -match 'arm64.msi$') 'arm64 selection'
Assert ((Select-WindowsMsi $release 'x86').name -match 'x86.msi$') 'x86 selection'
Assert-Throws { Select-WindowsMsi ([pscustomobject]@{assets=@()}) 'x64' } 'Missing package must fail'
Assert-Throws { Select-WindowsMsi ([pscustomobject]@{assets=@($release.assets[0],$release.assets[0])}) 'x64' } 'Ambiguous package must fail'
$art=[pscustomobject]@{assets=@([pscustomobject]@{name='ArtCraft_0.41.0_x64_en-US.msi'})}
Assert ((Select-WindowsMsi $art 'x64').name -match 'en-US') 'ArtCraft naming convention'
Assert-Throws { Assert-ReleaseUrl 'https://example.com/setup.msi' 'photocraft' } 'Reject third party URL'
Assert-Throws { Assert-ReleaseUrl 'https://github.com/another/photocraft/releases/download/a/b.msi' 'photocraft' } 'Reject other repo URL'
Assert-Throws { Assert-ReleaseUrl 'http://github.com/storytold/photocraft/releases/download/a/b.msi' 'photocraft' } 'Require HTTPS'
Assert-ReleaseUrl $release.assets[0].browser_download_url 'photocraft'
$catalog=@(Get-Catalog)
Assert ($catalog.Count -eq 16) '14 apps plus 2 optional examples'
Assert (@($catalog | Where-Object { -not $_.Description -or -not $_.Compare }).Count -eq 0) 'Descriptions and comparisons exist'
$script:requests=0
function Get-GitHubJson([string]$Path) { $script:requests++; if ($Path -match '/contents/') { throw 'No source in fixture' }; $release }
Update-Catalog @($catalog[0]) 'x64'
Assert ($catalog[0].Available -and $catalog[0].Version -eq 'v99.0.0') 'Discover current release'
$release.tag_name='v100.0.0'
Update-Catalog @($catalog[0]) 'x64'
Assert ($catalog[0].Version -eq 'v100.0.0' -and $script:requests -eq 2) 'Subsequent check must refresh version'
$release.prerelease=$true
Update-Catalog @($catalog[0]) 'x64'
Assert (-not $catalog[0].Available) 'Reject prerelease'
$release.prerelease=$false
function Get-GitHubJson([string]$Path) { throw 'Rate limit fixture' }
Update-Catalog @($catalog[0]) 'x64'
Assert (-not $catalog[0].Available -and $catalog[0].Status -eq 'Rate limit fixture') 'Do not use stale release on failure'
$testFolder=Join-Path $PSScriptRoot 'installer-tests'
[IO.Directory]::CreateDirectory($testFolder) | Out-Null
$bytes=[Text.Encoding]::UTF8.GetBytes('fixture installer bytes')
$sha256=[Security.Cryptography.SHA256]::Create()
$digest=[BitConverter]::ToString($sha256.ComputeHash($bytes)).Replace('-','').ToLowerInvariant(); $sha256.Dispose()
$prefix=[Text.Encoding]::ASCII.GetBytes("blob $($bytes.Length)`0")
$sha1=[Security.Cryptography.SHA1]::Create()
$blob=[BitConverter]::ToString($sha1.ComputeHash([byte[]]($prefix+$bytes))).Replace('-','').ToLowerInvariant(); $sha1.Dispose()
$source=[pscustomobject]@{type='file';encoding='base64';content=[Convert]::ToBase64String($bytes);sha=$blob}
$destination=Join-Path $testFolder 'source/fixture.wasm'
Save-GitHubSourceFile $source $destination
Assert ((Get-FileHash $destination -Algorithm SHA256).Hash -ieq $digest) 'Source bytes and git blob verification'
$source.sha='0000000000000000000000000000000000000000'
Assert-Throws { Save-GitHubSourceFile $source $destination } 'Reject bad source blob hash'
function Invoke-WebRequest { param($UseBasicParsing,$Uri,$OutFile,$TimeoutSec) if ($Uri -match 'SHA256SUMS') { [IO.File]::WriteAllText($OutFile,($digest+'  '+$release.assets[0].name)) } else { [IO.File]::WriteAllBytes($OutFile,$bytes) } }
# Use a switch parameter for the mocked built-in switch.
Remove-Item function:Invoke-WebRequest
function Invoke-WebRequest { param([switch]$UseBasicParsing,$Uri,$OutFile,$TimeoutSec) if ($Uri -match 'SHA256SUMS') { [IO.File]::WriteAllText($OutFile,($digest+'  '+$release.assets[0].name)) } else { [IO.File]::WriteAllBytes($OutFile,$bytes) } }
$catalog[0].Release=$release; $catalog[0].Asset=$release.assets[0]
$catalog[0].Asset.digest='sha256:'+$digest
$saved=Save-VerifiedInstaller $catalog[0] $testFolder
Assert (Test-Path -LiteralPath $saved) 'Verified installer saved'
$catalog[0].Asset.digest='sha256:'+('0'*64)
Assert-Throws { Save-VerifiedInstaller $catalog[0] $testFolder } 'Reject checksum mismatch'
$catalog[0].Asset.digest=''
Assert-Throws { Save-VerifiedInstaller $catalog[0] $testFolder } 'Reject missing checksums'
$release.assets+= [pscustomobject]@{name='SHA256SUMS.txt';browser_download_url='https://github.com/storytold/photocraft/releases/download/v99.0.0/SHA256SUMS.txt'}
$saved=Save-VerifiedInstaller $catalog[0] $testFolder
Assert (Test-Path -LiteralPath $saved) 'SHA256SUMS fallback'
$release.assets[0].name='../evil.msi'
Assert-Throws { Save-VerifiedInstaller $catalog[0] $testFolder } 'Reject unsafe filename'
$release.assets[0].name='photocraft-99.0.0-windows-x64.msi'
$release.assets += [pscustomobject]@{name='new-filter-99.0.0.wasm';browser_download_url='https://github.com/storytold/newcraft/releases/download/v99.0.0/new-filter-99.0.0.wasm'}
$script:fixtureRelease = $release
function Get-GitHubJson([string]$Path) {
    if ($Path -match '^orgs/') {
        return @(
            [pscustomobject]@{name='newcraft';owner=@{login='storytold'};description='New editor';archived=$false;fork=$false;disabled=$false},
            [pscustomobject]@{name='newlibrary';owner=@{login='storytold'};description='Library';archived=$false;fork=$false;disabled=$false},
            [pscustomobject]@{name='oldfork';owner=@{login='storytold'};archived=$false;fork=$true;disabled=$false}
        )
    }
    if ($Path -match '/newlibrary/') { throw 'No release' }
    $script:fixtureRelease
}
$live=@(Expand-LiveCatalog @(Get-Catalog) 'x64')
Assert (@($live | Where-Object { $_.Repo -eq 'newcraft' -and $_.Kind -eq 'App' }).Count -eq 1) 'Discover new Windows app'
Assert (@($live | Where-Object { $_.Repo -eq 'newlibrary' -and $_.Kind -eq 'Repository' }).Count -eq 1) 'Show new library without trying to install it'
Assert (@($live | Where-Object { $_.Repo -eq 'oldfork' }).Count -eq 0) 'Do not offer unrelated fork'
Assert (@($live | Where-Object { $_.Kind -eq 'ReleaseResource' }).Count -eq 1) 'Discover optional release resource'
Assert ((Get-ReleaseAssetKey 'filter-1.2.3.wasm') -eq (Get-ReleaseAssetKey 'filter-9.0.0.wasm')) 'Resource identity survives new versions'
$resource=@($live | Where-Object { $_.Kind -eq 'ReleaseResource' })[0]
Update-Catalog @($resource) 'x64' -UseDiscoveryCache
Assert $resource.Available 'Discovered resource can be selected'
$script:pages=0
function Get-GitHubJson([string]$Path) {
    if ($Path -match '^orgs/') {
        $script:pages++
        if ($script:pages -eq 1) { 1..100 | ForEach-Object { [pscustomobject]@{name="fork$_";owner=@{login='storytold'};fork=$true} } }
        else { [pscustomobject]@{name='page-two';owner=@{login='storytold'};description='Second page';fork=$false} }
    } else { throw 'No release' }
}
$live=@(Expand-LiveCatalog @() 'x64')
Assert ($script:pages -eq 2 -and $live[0].Repo -eq 'page-two') 'Paginate beyond first 100 repositories'
Write-Host "PASS: $script:checks assertions; no real downloads or installs performed."
