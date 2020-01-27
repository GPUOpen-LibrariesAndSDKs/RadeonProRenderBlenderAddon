$targetPath = "..\src\rprblender\__init__.py"

if (-not (Test-Path $targetPath)) {
	exit 1
}

$content = Get-Content -Path $targetPath

$mask = '\s*"version"\s*:\s*\(\s*(?<VersionMj>\d+?),\s*(?<VersionMn>\d+?),\s*(?<VersionBld>\d+?)\),'

foreach ($line in $content) {
	$tline = $line.trim()

	if ($tline -match $mask) {
		$version = $Matches.VersionMj + "." + $Matches.VersionMn + "." + $Matches.VersionBld
		$version
		exit 0
	}
}

exit 2
