param(
    [string]$BaseUrl = "http://127.0.0.1:18002/business",
    [int]$Days = 30
)

$ErrorActionPreference = "Stop"

function Invoke-BusinessApi {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body
    )

    $parameters = @{
        Method = $Method
        Uri = "$BaseUrl$Path"
        TimeoutSec = 30
    }
    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 8 -Compress
        $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
        $parameters.ContentType = "application/json; charset=utf-8"
    }

    $response = Invoke-RestMethod @parameters
    if (-not $response.success) {
        throw "Business API failed: $Path - $($response.message)"
    }
    return $response.content
}

function Get-TimeText {
    param([datetime]$BaseTime, [int]$Minutes)
    return $BaseTime.AddMinutes($Minutes).ToString("HH:mm:ss")
}

# Unicode escapes keep this script compatible with Windows PowerShell 5.1,
# which otherwise reads a UTF-8 file without BOM using the system code page.
function Convert-UnicodeName([string]$Value) {
    return [System.Text.RegularExpressions.Regex]::Unescape($Value)
}

$stations = @(
    @{ name = Convert-UnicodeName "\u5317\u4eac\u5357"; namePinyin = "beijingnan"; namePy = "bjn" },
    @{ name = Convert-UnicodeName "\u6d4e\u5357\u897f"; namePinyin = "jinanxi"; namePy = "jnx" },
    @{ name = Convert-UnicodeName "\u5357\u4eac\u5357"; namePinyin = "nanjingnan"; namePy = "njn" },
    @{ name = Convert-UnicodeName "\u4e0a\u6d77\u8679\u6865"; namePinyin = "shanghaihongqiao"; namePy = "shhq" },
    @{ name = Convert-UnicodeName "\u676d\u5dde\u4e1c"; namePinyin = "hangzhoudong"; namePy = "hzd" },
    @{ name = Convert-UnicodeName "\u5357\u660c\u897f"; namePinyin = "nanchangxi"; namePy = "ncx" },
    @{ name = Convert-UnicodeName "\u6b66\u6c49"; namePinyin = "wuhan"; namePy = "wh" },
    @{ name = Convert-UnicodeName "\u957f\u6c99\u5357"; namePinyin = "changshanan"; namePy = "csn" },
    @{ name = Convert-UnicodeName "\u5e7f\u5dde\u5357"; namePinyin = "guangzhounan"; namePy = "gzn" },
    @{ name = Convert-UnicodeName "\u6df1\u5733\u5317"; namePinyin = "shenzhenbei"; namePy = "szb" }
)

$existingStations = @(Invoke-BusinessApi -Method Get -Path "/station/query-all")
$stationPinyins = @{}
foreach ($station in $existingStations) { $stationPinyins[$station.namePinyin.ToLowerInvariant()] = $true }

foreach ($station in $stations) {
    if (-not $stationPinyins.ContainsKey($station.namePinyin)) {
        Invoke-BusinessApi -Method Post -Path "/admin/station/save" -Body $station | Out-Null
        Write-Host "Added station: $($station.name)"
    }
}

$forwardDistances = @(0, 410, 620, 300, 180, 480, 350, 360, 650, 140)
$reverseStations = @($stations[($stations.Count - 1)..0])
$reverseDistances = @(0, 140, 650, 360, 350, 480, 180, 300, 620, 410)
$routes = @(
    @{ code = "G9101"; type = "G"; base = "06:00:00"; stations = $stations; distances = $forwardDistances },
    @{ code = "G9102"; type = "G"; base = "07:00:00"; stations = $reverseStations; distances = $reverseDistances },
    @{ code = "D9201"; type = "D"; base = "12:00:00"; stations = $stations; distances = $forwardDistances },
    @{ code = "D9202"; type = "D"; base = "12:30:00"; stations = $reverseStations; distances = $reverseDistances }
)

$existingTrains = @(Invoke-BusinessApi -Method Get -Path "/admin/train/query-all")
$trainCodes = @{}
foreach ($train in $existingTrains) { $trainCodes[$train.code] = $true }

foreach ($route in $routes) {
    $baseTime = [datetime]::ParseExact($route.base, "HH:mm:ss", $null)
    $lastMinutes = ($route.stations.Count - 1) * 65
    if (-not $trainCodes.ContainsKey($route.code)) {
        $trainBody = @{
            code = $route.code
            type = $route.type
            start = $route.stations[0].name
            startPinyin = $route.stations[0].namePinyin
            startTime = $route.base
            end = $route.stations[-1].name
            endPinyin = $route.stations[-1].namePinyin
            endTime = Get-TimeText -BaseTime $baseTime -Minutes $lastMinutes
        }
        Invoke-BusinessApi -Method Post -Path "/admin/train/save" -Body $trainBody | Out-Null
        Write-Host "Added train: $($route.code)"
    }

    $stationPage = Invoke-BusinessApi -Method Get -Path "/admin/train-station/query-list?page=1&size=100&trainCode=$($route.code)"
    $existingIndexes = @{}
    foreach ($item in @($stationPage.list)) { $existingIndexes[[int]$item.index] = $true }
    for ($i = 0; $i -lt $route.stations.Count; $i++) {
        $index = $i + 1
        if ($existingIndexes.ContainsKey($index)) { continue }
        $arrivalMinutes = $i * 65
        $isFirst = $i -eq 0
        $isLast = $i -eq ($route.stations.Count - 1)
        $stationBody = @{
            trainCode = $route.code
            index = $index
            name = $route.stations[$i].name
            namePinyin = $route.stations[$i].namePinyin
            inTime = if ($isFirst) { $null } else { Get-TimeText -BaseTime $baseTime -Minutes $arrivalMinutes }
            outTime = if ($isLast) { $null } elseif ($isFirst) { $route.base } else { Get-TimeText -BaseTime $baseTime -Minutes ($arrivalMinutes + 5) }
            stopTime = if ($isFirst -or $isLast) { $null } else { "00:05:00" }
            km = $route.distances[$i]
        }
        Invoke-BusinessApi -Method Post -Path "/admin/train-station/save" -Body $stationBody | Out-Null
    }

    $carriagePage = Invoke-BusinessApi -Method Get -Path "/admin/train-carriage/query-list?page=1&size=100&trainCode=$($route.code)"
    $carriageIndexes = @{}
    foreach ($item in @($carriagePage.list)) { $carriageIndexes[[int]$item.index] = $true }
    $carriages = @(
        @{ trainCode = $route.code; index = 1; seatType = "1"; rowCount = 2 },
        @{ trainCode = $route.code; index = 2; seatType = "2"; rowCount = 2 }
    )
    foreach ($carriage in $carriages) {
        if (-not $carriageIndexes.ContainsKey([int]$carriage.index)) {
            Invoke-BusinessApi -Method Post -Path "/admin/train-carriage/save" -Body $carriage | Out-Null
        }
    }

    Invoke-BusinessApi -Method Get -Path "/admin/train/gen-seat/$($route.code)" | Out-Null
    Write-Host "Prepared route, carriages and seats: $($route.code)"
}

for ($offset = 0; $offset -lt $Days; $offset++) {
    $date = (Get-Date).Date.AddDays($offset).ToString("yyyy-MM-dd")
    Invoke-BusinessApi -Method Get -Path "/admin/daily-train/gen-daily/$date" | Out-Null
    Write-Host "Generated daily tickets: $date"
}

Write-Host "Seed completed: $($stations.Count) stations, $($routes.Count) test trains, $Days days."
