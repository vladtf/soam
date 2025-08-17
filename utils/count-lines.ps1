#Requires -Version 5.1

<#
.SYNOPSIS
    Counts lines of code by programming language in a repository.

.DESCRIPTION
    This script scans a repository directory and counts lines of code for various programming languages,
    including TypeScript, Python, JavaScript, JSON, HTML, CSS, YAML, PowerShell, and more.
    It excludes common directories like node_modules, .git, and build artifacts.

.PARAMETER Path
    The root path of the repository to scan. Defaults to current directory.

.PARAMETER ExcludeDirs
    Array of directory names to exclude from scanning.

.PARAMETER IncludeBlankLines
    Switch to include blank lines in the count.

.PARAMETER IncludeComments
    Switch to include comment lines in the count (basic detection).

.EXAMPLE
    .\count-lines.ps1
    Scans the current directory with default settings.

.EXAMPLE
    .\count-lines.ps1 -Path "C:\MyRepo" -IncludeBlankLines -IncludeComments
    Scans a specific path including blank lines and comments.
#>

param(
    [Parameter(Position = 0)]
    [string]$Path = (Get-Location).Path,
    
    [string[]]$ExcludeDirs = @(
        'node_modules', '.git', '.vscode', '.vs', 'bin', 'obj', 'dist', 'build', 
        '__pycache__', '.pytest_cache', '.mypy_cache', 'venv', '.venv', 
        'coverage', '.coverage', '.nyc_output', 'target', '.gradle', 
        'logs', 'temp', 'tmp', '.terraform', 'vendor'
    ),
    
    [switch]$IncludeBlankLines,
    [switch]$IncludeComments
)

# Language definitions with file extensions and comment patterns
$LanguageMap = @{
    'TypeScript' = @{
        Extensions = @('.ts', '.tsx')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'JavaScript' = @{
        Extensions = @('.js', '.jsx', '.mjs')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Python' = @{
        Extensions = @('.py', '.pyw', '.pyi')
        LineComment = '#'
        BlockComment = @('"""', '"""', "'''", "'''")
    }
    'JSON' = @{
        Extensions = @('.json', '.jsonl', '.json5')
        LineComment = $null
        BlockComment = $null
    }
    'HTML' = @{
        Extensions = @('.html', '.htm', '.xhtml')
        LineComment = $null
        BlockComment = @('<!--', '-->')
    }
    'CSS' = @{
        Extensions = @('.css', '.scss', '.sass', '.less')
        LineComment = $null
        BlockComment = @('/*', '*/')
    }
    'YAML' = @{
        Extensions = @('.yml', '.yaml')
        LineComment = '#'
        BlockComment = $null
    }
    'PowerShell' = @{
        Extensions = @('.ps1', '.psm1', '.psd1')
        LineComment = '#'
        BlockComment = @('<#', '#>')
    }
    'Dockerfile' = @{
        Extensions = @('.dockerfile')
        LineComment = '#'
        BlockComment = $null
    }
    'Shell' = @{
        Extensions = @('.sh', '.bash', '.zsh')
        LineComment = '#'
        BlockComment = $null
    }
    'Markdown' = @{
        Extensions = @('.md', '.markdown', '.mdown', '.mkd')
        LineComment = $null
        BlockComment = $null
    }
    'XML' = @{
        Extensions = @('.xml', '.xaml', '.xsd', '.xslt')
        LineComment = $null
        BlockComment = @('<!--', '-->')
    }
    'SQL' = @{
        Extensions = @('.sql', '.ddl', '.dml')
        LineComment = '--'
        BlockComment = @('/*', '*/')
    }
    'C#' = @{
        Extensions = @('.cs', '.csx')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Java' = @{
        Extensions = @('.java')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Go' = @{
        Extensions = @('.go')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Rust' = @{
        Extensions = @('.rs')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'PHP' = @{
        Extensions = @('.php', '.phtml', '.php3', '.php4', '.php5', '.phps')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Ruby' = @{
        Extensions = @('.rb', '.rbw')
        LineComment = '#'
        BlockComment = @('=begin', '=end')
    }
    'Swift' = @{
        Extensions = @('.swift')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Kotlin' = @{
        Extensions = @('.kt', '.kts')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
    'Scala' = @{
        Extensions = @('.scala', '.sc')
        LineComment = '//'
        BlockComment = @('/*', '*/')
    }
}

# Add special file handling for files without extensions
$SpecialFiles = @{
    'Dockerfile' = @('Dockerfile')
    'Makefile' = @('Makefile', 'makefile')
    'Shell' = @('.gitignore', '.dockerignore')
    'YAML' = @('.gitattributes')
}

function Test-IsExcludedDirectory {
    param([string]$DirPath)
    
    $dirName = Split-Path $DirPath -Leaf
    return $ExcludeDirs -contains $dirName
}

function Get-FileLanguage {
    param([System.IO.FileInfo]$File)
    
    $extension = $File.Extension.ToLower()
    $fileName = $File.Name
    
    # Check special files first
    foreach ($lang in $SpecialFiles.Keys) {
        if ($SpecialFiles[$lang] -contains $fileName) {
            return $lang
        }
    }
    
    # Check by extension
    foreach ($lang in $LanguageMap.Keys) {
        if ($LanguageMap[$lang].Extensions -contains $extension) {
            return $lang
        }
    }
    
    return 'Other'
}

function Count-LinesInFile {
    param(
        [System.IO.FileInfo]$File,
        [string]$Language
    )
    
    try {
        $content = Get-Content $File.FullName -ErrorAction Stop
        
        if (-not $content) {
            return @{ Total = 0; Code = 0; Blank = 0; Comments = 0 }
        }
        
        $totalLines = $content.Count
        $blankLines = 0
        $commentLines = 0
        $codeLines = 0
        
        $langInfo = $LanguageMap[$Language]
        $inBlockComment = $false
        $blockCommentEnd = $null
        
        foreach ($line in $content) {
            $trimmedLine = $line.Trim()
            
            # Count blank lines
            if ([string]::IsNullOrWhiteSpace($line)) {
                $blankLines++
                continue
            }
            
            $isComment = $false
            
            # Check for block comments (if language supports them)
            if ($langInfo -and $langInfo.BlockComment) {
                $blockStart = $langInfo.BlockComment[0]
                $blockEnd = $langInfo.BlockComment[1]
                
                if ($inBlockComment) {
                    $isComment = $true
                    if ($trimmedLine.Contains($blockEnd)) {
                        $inBlockComment = $false
                    }
                }
                elseif ($trimmedLine.Contains($blockStart)) {
                    $isComment = $true
                    $inBlockComment = $true
                    if ($trimmedLine.Contains($blockEnd)) {
                        $inBlockComment = $false
                    }
                }
            }
            
            # Check for line comments (if not already identified as block comment)
            if (-not $isComment -and $langInfo -and $langInfo.LineComment) {
                if ($trimmedLine.StartsWith($langInfo.LineComment)) {
                    $isComment = $true
                }
            }
            
            if ($isComment) {
                $commentLines++
            }
            else {
                $codeLines++
            }
        }
        
        return @{
            Total = $totalLines
            Code = $codeLines
            Blank = $blankLines
            Comments = $commentLines
        }
    }
    catch {
        Write-Warning "Failed to read file: $($File.FullName) - $($_.Exception.Message)"
        return @{ Total = 0; Code = 0; Blank = 0; Comments = 0 }
    }
}

function Format-Number {
    param([int]$Number)
    return $Number.ToString('N0')
}

function Write-ProgressUpdate {
    param([int]$Current, [int]$Total, [string]$CurrentFile)
    
    $percent = if ($Total -gt 0) { [math]::Round(($Current / $Total) * 100, 1) } else { 0 }
    $activity = "Scanning files... ($Current/$Total)"
    $status = "Processing: $(Split-Path $CurrentFile -Leaf)"
    
    Write-Progress -Activity $activity -Status $status -PercentComplete $percent
}

# Main execution
Write-Host "🔍 Scanning repository for code statistics..." -ForegroundColor Cyan
Write-Host "📁 Path: $Path" -ForegroundColor Gray
Write-Host "⚙️  Settings: Blank Lines: $IncludeBlankLines, Comments: $IncludeComments" -ForegroundColor Gray
Write-Host

if (-not (Test-Path $Path)) {
    Write-Error "Path not found: $Path"
    exit 1
}

# Get all files, excluding specified directories
Write-Host "🗂️  Discovering files..." -ForegroundColor Yellow

$allFiles = Get-ChildItem -Path $Path -Recurse -File | Where-Object {
    $filePath = $_.FullName
    $relativePath = $filePath.Substring($Path.Length).TrimStart('\', '/')
    $pathParts = $relativePath -split '[\\/]'
    
    # Check if any path component is an excluded directory
    $isExcluded = $false
    foreach ($part in $pathParts) {
        if ($ExcludeDirs -contains $part) {
            $isExcluded = $true
            break
        }
    }
    
    return -not $isExcluded
}

Write-Host "📊 Found $(Format-Number $allFiles.Count) files to analyze" -ForegroundColor Green
Write-Host

# Initialize statistics
$stats = @{}
$totalFiles = 0
$processedFiles = 0

# Process each file
foreach ($file in $allFiles) {
    $processedFiles++
    Write-ProgressUpdate -Current $processedFiles -Total $allFiles.Count -CurrentFile $file.FullName
    
    $language = Get-FileLanguage -File $file
    
    if (-not $stats.ContainsKey($language)) {
        $stats[$language] = @{
            Files = 0
            Total = 0
            Code = 0
            Blank = 0
            Comments = 0
        }
    }
    
    $stats[$language].Files++
    $totalFiles++
    
    $lineCount = Count-LinesInFile -File $file -Language $language
    $stats[$language].Total += $lineCount.Total
    $stats[$language].Code += $lineCount.Code
    $stats[$language].Blank += $lineCount.Blank
    $stats[$language].Comments += $lineCount.Comments
}

Write-Progress -Activity "Complete" -Completed

# Calculate totals
$grandTotal = @{
    Files = $totalFiles
    Total = ($stats.Values | Measure-Object -Property Total -Sum).Sum
    Code = ($stats.Values | Measure-Object -Property Code -Sum).Sum
    Blank = ($stats.Values | Measure-Object -Property Blank -Sum).Sum
    Comments = ($stats.Values | Measure-Object -Property Comments -Sum).Sum
}

# Display results
Write-Host
Write-Host "📈 Code Statistics Report" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Gray

# Sort languages by total lines (descending)
$sortedStats = $stats.GetEnumerator() | Sort-Object { $_.Value.Total } -Descending

# Display header
$headerFormat = "{0,-15} {1,8} {2,12} {3,10} {4,10} {5,12}"
Write-Host ($headerFormat -f "Language", "Files", "Total Lines", "Code", "Blank", "Comments") -ForegroundColor White
Write-Host ("-" * 80) -ForegroundColor Gray

# Display each language
foreach ($entry in $sortedStats) {
    $lang = $entry.Key
    $data = $entry.Value
    
    $color = switch ($lang) {
        'TypeScript' { 'Blue' }
        'JavaScript' { 'Yellow' }
        'Python' { 'Green' }
        'JSON' { 'Magenta' }
        'HTML' { 'Red' }
        'CSS' { 'Cyan' }
        'YAML' { 'White' }
        'PowerShell' { 'DarkBlue' }
        default { 'Gray' }
    }
    
    $lineFormat = $headerFormat -f $lang,
                                (Format-Number $data.Files),
                                (Format-Number $data.Total),
                                (Format-Number $data.Code),
                                (Format-Number $data.Blank),
                                (Format-Number $data.Comments)
    
    Write-Host $lineFormat -ForegroundColor $color
}

# Display totals
Write-Host ("-" * 80) -ForegroundColor Gray
$totalFormat = $headerFormat -f "TOTAL",
                              (Format-Number $grandTotal.Files),
                              (Format-Number $grandTotal.Total),
                              (Format-Number $grandTotal.Code),
                              (Format-Number $grandTotal.Blank),
                              (Format-Number $grandTotal.Comments)
Write-Host $totalFormat -ForegroundColor White -BackgroundColor DarkGreen

Write-Host
Write-Host "📊 Summary:" -ForegroundColor Cyan
Write-Host "  • Languages detected: $($stats.Keys.Count)" -ForegroundColor Gray
Write-Host "  • Files processed: $(Format-Number $grandTotal.Files)" -ForegroundColor Gray
Write-Host "  • Total lines: $(Format-Number $grandTotal.Total)" -ForegroundColor Gray
Write-Host "  • Code lines: $(Format-Number $grandTotal.Code)" -ForegroundColor Gray

if ($IncludeBlankLines) {
    Write-Host "  • Blank lines: $(Format-Number $grandTotal.Blank)" -ForegroundColor Gray
}
if ($IncludeComments) {
    Write-Host "  • Comment lines: $(Format-Number $grandTotal.Comments)" -ForegroundColor Gray
}

# Show top languages as percentages
Write-Host
Write-Host "🏆 Top Languages by Code Lines:" -ForegroundColor Cyan
$topLanguages = $sortedStats | Select-Object -First 5
foreach ($entry in $topLanguages) {
    $lang = $entry.Key
    $codeLines = $entry.Value.Code
    $percentage = if ($grandTotal.Code -gt 0) { [math]::Round(($codeLines / $grandTotal.Code) * 100, 1) } else { 0 }
    Write-Host "  • $lang`: $(Format-Number $codeLines) lines ($percentage%)" -ForegroundColor Gray
}

Write-Host
Write-Host "✅ Analysis complete!" -ForegroundColor Green
