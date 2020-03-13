<#******************************************************************
* Copyright 2020 Advanced Micro Devices, Inc
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*******************************************************************#>

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
