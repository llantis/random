<#
.SYNOPSIS
    Compares two audiobook libraries and reports what is missing from each.

.DESCRIPTION
    Finds every "book" in both folders (a folder of mp3/m4a/etc. files, or a
    single .m4b file), cleans up the names (drops "Star Wars", "Legends",
    "Unabridged", [tags], years, bitrates, track numbers...) and matches books
    by title words, so "Star Wars - Darth Plagueis (Legends) [2012] [M4B]" in
    one library matches "Darth Plagueis" in the other.

    It produces:
      - OnlyInNew : books in the new folder that the old library doesn't have
      - OnlyInOld : books in the old library the new folder doesn't have
      - Incomplete: books in both, but the old copy is much smaller or has
                    fewer files (likely damaged/partial after the drive loss)
      - Matched   : books found in both

    Nothing is changed unless you pass -CopyMissing, which copies the
    "OnlyInNew" books into the old library (never overwrites or deletes).

.EXAMPLE
    .\Compare-Audiobooks.ps1

.EXAMPLE
    .\Compare-Audiobooks.ps1 -NewNameFilter 'star ?wars|jedi|sith' -GridView

.EXAMPLE
    .\Compare-Audiobooks.ps1 -CopyMissing -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$NewPath = '\\LWLNAS\data\torrents\audiobooks',
    [string]$OldPath = '\\LWLNAS\data\media\Star wars legends',

    # Only consider new-side books whose folder/file path matches this regex
    # (e.g. 'star ?wars'). Empty = look at everything.
    [string]$NewNameFilter = '',

    # Folder for the CSV/text reports. Defaults to your Desktop.
    [string]$OutDir = [Environment]::GetFolderPath('Desktop'),

    # 0..1 - how much of the shorter title must appear in the longer one.
    [double]$MatchThreshold = 0.75,

    # Flag a matched book as incomplete if old size is below this fraction of new.
    [double]$IncompleteRatio = 0.6,

    [switch]$GridView,
    [switch]$CopyMissing
)

$ErrorActionPreference = 'Stop'

$AudioExt = @('.mp3', '.m4a', '.m4b', '.aac', '.flac', '.ogg', '.opus', '.wma', '.wav', '.aax')

# Words that say nothing about which book it is.
$NoiseWords = @(
    'star', 'wars', 'legends', 'legend', 'expanded', 'universe', 'eu', 'canon',
    'unabridged', 'abridged', 'audiobook', 'audio', 'book', 'books', 'novel',
    'dramatized', 'dramatised', 'full', 'cast', 'edition', 'retail', 'complete',
    'mp3', 'm4b', 'm4a', 'aac', 'flac', 'kbps', 'kbs', 'vbr', 'cbr', 'khz', 'mono', 'stereo',
    'read', 'narrated', 'by', 'narrator', 'disc', 'disk', 'cd', 'part', 'pt', 'vol', 'volume',
    'the', 'a', 'an', 'of', 'and', 'in', 'on', 'to', 'at', 'for', 'with', 'from'
)
$NoiseSet = @{}
foreach ($w in $NoiseWords) { $NoiseSet[$w] = $true }

# Folder names that are just pieces of a bigger book ("CD 1", "Disc 02", "Part 3").
$PieceFolderRegex = '^\s*(cd|disc|disk|part|pt|vol|volume)\s*[-_.]?\s*\d+\s*$'

function Get-TitleTokens([string]$Name) {
    $s = $Name.ToLowerInvariant()
    $s = $s -replace "['\u2019]", ''                     # Jedi's -> jedis
    $s = $s -replace '\[[^\]]*\]|\{[^}]*\}', ' '         # [M4B] {64kbps}
    $s = $s -replace '\b\d+\s*k(bps|bs)?\b', ' '          # 64k, 128kbps
    $s = $s -replace '[^a-z0-9]+', ' '
    $tokens = @()
    foreach ($t in $s.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)) {
        if ($t -match '^\d+$') { continue }               # years, series numbers, track numbers
        if ($t.Length -lt 2) { continue }
        if ($NoiseSet.ContainsKey($t)) { continue }
        $tokens += $t
    }
    return , ($tokens | Select-Object -Unique)
}

function Get-Books([string]$Root, [string]$Filter) {
    if (-not (Test-Path -LiteralPath $Root)) { throw "Can't reach '$Root'. Is the NAS online and are you signed in to it?" }
    Write-Host "Scanning $Root ..." -ForegroundColor Cyan

    $files = Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $AudioExt -contains $_.Extension.ToLowerInvariant() }

    $books = @{}
    foreach ($f in $files) {
        $dir = $f.Directory
        # A .m4b/.aax is normally a whole book, so a folder full of them = several books.
        $isSingleFileBook = @('.m4b', '.aax') -contains $f.Extension.ToLowerInvariant()
        if ($isSingleFileBook) {
            $siblings = @(Get-ChildItem -LiteralPath $dir.FullName -File -Filter "*$($f.Extension)" -ErrorAction SilentlyContinue)
            $isSingleFileBook = $siblings.Count -gt 1
        }

        if ($isSingleFileBook) {
            $key = $f.FullName
            $name = [IO.Path]::GetFileNameWithoutExtension($f.Name)
        }
        else {
            # Roll "CD1"/"Disc 2" folders up into their parent book folder.
            while ($dir.Name -match $PieceFolderRegex -and $dir.Parent -and
                   $dir.Parent.FullName.TrimEnd('\', '/').Length -ge $Root.TrimEnd('\', '/').Length) {
                $dir = $dir.Parent
            }
            $key = $dir.FullName
            $name = $dir.Name
            # Loose files sitting directly in the root are each their own book.
            if ($dir.FullName.TrimEnd('\', '/') -eq (Get-Item -LiteralPath $Root).FullName.TrimEnd('\', '/')) {
                $key = $f.FullName
                $name = [IO.Path]::GetFileNameWithoutExtension($f.Name)
            }
        }

        if (-not $books.ContainsKey($key)) {
            $rel = $key.Substring([Math]::Min($Root.Length, $key.Length)).TrimStart('\', '/')
            # Use the parent folder too when the book folder name is generic.
            $display = $name
            $tokens = Get-TitleTokens $name
            if ($tokens.Count -eq 0) {
                $display = $rel
                $tokens = Get-TitleTokens ($rel -replace '[\\/]', ' ')
            }
            $books[$key] = [pscustomobject]@{
                Name      = $display
                Path      = $key
                Relative  = $rel
                Tokens    = $tokens
                Files     = 0
                SizeBytes = [long]0
            }
        }
        $books[$key].Files++
        $books[$key].SizeBytes += $f.Length
    }

    $list = @($books.Values)
    if ($Filter) { $list = @($list | Where-Object { $_.Relative -match $Filter }) }
    Write-Host ("  found {0} books" -f $list.Count)
    return , $list
}

function Get-MatchScore($a, $b) {
    if ($a.Count -eq 0 -or $b.Count -eq 0) { return 0.0 }
    $setB = @{}
    foreach ($t in $b) { $setB[$t] = $true }
    $common = 0
    foreach ($t in $a) { if ($setB.ContainsKey($t)) { $common++ } }
    $min = [Math]::Min($a.Count, $b.Count)
    $union = $a.Count + $b.Count - $common
    # Mostly "how much of the shorter title is in the longer one", nudged by
    # overall overlap so exact-ish matches win ties.
    return [Math]::Round(0.85 * ($common / $min) + 0.15 * ($common / $union), 3)
}

function Format-Size([long]$Bytes) {
    if ($Bytes -ge 1GB) { return '{0:N2} GB' -f ($Bytes / 1GB) }
    return '{0:N0} MB' -f ($Bytes / 1MB)
}

# ---------------------------------------------------------------------------

$newBooks = Get-Books -Root $NewPath -Filter $NewNameFilter
$oldBooks = Get-Books -Root $OldPath -Filter ''

# Best match for each book on the other side.
function Find-Best($book, $candidates) {
    $best = $null; $bestScore = 0.0
    foreach ($c in $candidates) {
        $s = Get-MatchScore $book.Tokens $c.Tokens
        if ($s -gt $bestScore) { $best = $c; $bestScore = $s }
    }
    return [pscustomobject]@{ Book = $best; Score = $bestScore }
}

$rows = New-Object System.Collections.Generic.List[object]
$matchedOld = @{}

foreach ($n in $newBooks | Sort-Object Name) {
    $m = Find-Best $n $oldBooks
    if ($m.Book -and $m.Score -ge $MatchThreshold) {
        $o = $m.Book
        $matchedOld[$o.Path] = $true
        $status = 'Matched'
        $note = ''
        if ($n.SizeBytes -gt 0 -and $o.SizeBytes -lt $n.SizeBytes * $IncompleteRatio) {
            $status = 'Incomplete'
            $note = 'old copy is much smaller'
        }
        elseif ($o.Files -lt $n.Files -and $n.Files -gt 1 -and $o.Files -gt 1) {
            $status = 'Incomplete'
            $note = 'old copy has fewer files'
        }
        $rows.Add([pscustomobject]@{
            Status = $status; Title = $n.Name; MatchedTo = $o.Name; Score = $m.Score
            NewFiles = $n.Files; NewSize = Format-Size $n.SizeBytes
            OldFiles = $o.Files; OldSize = Format-Size $o.SizeBytes
            Note = $note; NewPath = $n.Path; OldPath = $o.Path
        })
    }
    else {
        $near = ''
        if ($m.Book -and $m.Score -ge 0.4) { $near = "closest old: '$($m.Book.Name)' ($($m.Score)) - check by hand" }
        $rows.Add([pscustomobject]@{
            Status = 'OnlyInNew'; Title = $n.Name; MatchedTo = ''; Score = $m.Score
            NewFiles = $n.Files; NewSize = Format-Size $n.SizeBytes
            OldFiles = ''; OldSize = ''
            Note = $near; NewPath = $n.Path; OldPath = ''
        })
    }
}

foreach ($o in $oldBooks | Sort-Object Name) {
    if ($matchedOld.ContainsKey($o.Path)) { continue }
    $m = Find-Best $o $newBooks
    # An old book might still match a new one that was already paired with a
    # different old book (e.g. duplicates in the old library).
    if ($m.Book -and $m.Score -ge $MatchThreshold) {
        $rows.Add([pscustomobject]@{
            Status = 'Matched'; Title = $m.Book.Name; MatchedTo = $o.Name; Score = $m.Score
            NewFiles = $m.Book.Files; NewSize = Format-Size $m.Book.SizeBytes
            OldFiles = $o.Files; OldSize = Format-Size $o.SizeBytes
            Note = 'extra/duplicate copy in old library'; NewPath = $m.Book.Path; OldPath = $o.Path
        })
        continue
    }
    $rows.Add([pscustomobject]@{
        Status = 'OnlyInOld'; Title = $o.Name; MatchedTo = ''; Score = $m.Score
        NewFiles = ''; NewSize = ''
        OldFiles = $o.Files; OldSize = Format-Size $o.SizeBytes
        Note = ''; NewPath = ''; OldPath = $o.Path
    })
}

# --- Report -----------------------------------------------------------------

$order = @{ OnlyInNew = 0; Incomplete = 1; OnlyInOld = 2; Matched = 3 }
$rows = @($rows | Sort-Object @{ Expression = { $order[$_.Status] } }, Title)

$stamp = Get-Date -Format 'yyyy-MM-dd_HHmm'
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$csvPath = Join-Path $OutDir "Audiobook-Compare_$stamp.csv"
$txtPath = Join-Path $OutDir "Audiobook-Compare_$stamp.txt"
$rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("Audiobook comparison - $(Get-Date)")
[void]$sb.AppendLine("NEW: $NewPath  ($($newBooks.Count) books)")
[void]$sb.AppendLine("OLD: $OldPath  ($($oldBooks.Count) books)")
[void]$sb.AppendLine('')
$sections = @(
    @{ Status = 'OnlyInNew';  Header = 'In NEW but missing from OLD (copy these over)' },
    @{ Status = 'Incomplete'; Header = 'In both, but OLD copy looks incomplete/damaged' },
    @{ Status = 'OnlyInOld';  Header = 'In OLD but not in NEW (only copy you have - keep these!)' },
    @{ Status = 'Matched';    Header = 'In both' }
)
foreach ($sec in $sections) {
    $items = @($rows | Where-Object Status -eq $sec.Status)
    [void]$sb.AppendLine(('=== {0}: {1} ===' -f $sec.Header, $items.Count))
    foreach ($r in $items) {
        $line = '  ' + $r.Title
        if ($r.MatchedTo -and $r.MatchedTo -ne $r.Title) { $line += "   <->   $($r.MatchedTo)" }
        if ($r.Status -eq 'Incomplete') { $line += "   [new $($r.NewSize)/$($r.NewFiles) files, old $($r.OldSize)/$($r.OldFiles) files]" }
        if ($r.Note -and $r.Status -ne 'Incomplete') { $line += "   ($($r.Note))" }
        [void]$sb.AppendLine($line)
    }
    [void]$sb.AppendLine('')
}
$report = $sb.ToString()
Set-Content -LiteralPath $txtPath -Value $report -Encoding UTF8
Write-Host ''
Write-Host $report
Write-Host "Saved: $txtPath" -ForegroundColor Green
Write-Host "Saved: $csvPath (open in Excel for sorting/filtering)" -ForegroundColor Green

if ($GridView) { $rows | Out-GridView -Title 'Audiobook comparison' }

# --- Optional copy ------------------------------------------------------------

if ($CopyMissing) {
    foreach ($r in @($rows | Where-Object Status -eq 'OnlyInNew')) {
        $src = Get-Item -LiteralPath $r.NewPath
        $dest = Join-Path $OldPath $src.Name
        if (Test-Path -LiteralPath $dest) { Write-Warning "Skipping, already exists: $dest"; continue }
        if ($PSCmdlet.ShouldProcess($dest, "Copy '$($src.Name)' from new library")) {
            Copy-Item -LiteralPath $src.FullName -Destination $dest -Recurse
            Write-Host "Copied: $($src.Name)"
        }
    }
}
