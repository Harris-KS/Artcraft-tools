# Validation

Run the Python tests from the repository root:

```sh
python3 -m unittest discover -s tests -p "test_*.py" -v
```

On Windows, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\Test-ArtCraft-Installer.ps1`.

Tests use mocks and do not install Craft applications.
