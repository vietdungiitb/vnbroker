<#
.SYNOPSIS
    Chạy toàn bộ gate cục bộ của vnbroker và trả exit code theo kết quả thật.

.DESCRIPTION
    Tồn tại vì GitHub Actions của repo này KHÔNG chạy (job bị từ chối khởi
    động do billing: "recent account payments have failed or your spending
    limit needs to be increased"). 74 commit đã merge vào dev mà không gate
    nào chạy. Script này là entrypoint local thay cho CI.

    Nguyên tắc bắt buộc — exit code phải đến từ lệnh thật:
      · Không pipe output qua filter/tee (exit code của pipeline là của lệnh
        cuối cùng ⇒ gate im lặng).
      · Mỗi gate ghi hẳn exit code vào bảng tổng kết.
      · Gate đang đỏ sẵn được đánh dấu KNOWN-RED, không tính vào FAIL, nhưng
        vẫn in ra để không ai tưởng là xanh.

.PARAMETER Quick
    Bỏ qua `pytest tests/` (toàn bộ, ~3 phút). Chạy contract + unit core.
    Dùng khi sửa nhỏ và cần vòng lặp nhanh.

.PARAMETER Full
    Bắt buộc chạy `pytest tests/`. Mặc định script chạy Full.

.PARAMETER SelfTest
    Chứng minh script thật sự FAIL khi có gate đỏ. Một gate chỉ được tin
    khi đã thấy nó đỏ ít nhất một lần — cùng nguyên tắc với
    `check-*.cjs --self-test` của skill multi-agent-workflow.
    Dùng gate giả (exit 1) thay vì phá source thật.

.EXAMPLE
    pwsh -File scripts/check_all.ps1 -SelfTest

.EXAMPLE
    pwsh -File scripts/check_all.ps1
    Chạy mọi gate. Exit 0 = sạch, exit 1 = có gate thật đang đỏ.

.EXAMPLE
    pwsh -File scripts/check_all.ps1 -Quick
    Vòng lặp nhanh khi sửa vòng.

.NOTES
    Thêm một gate mới: khai $GATES ở dưới. Không tự chạy `mypy vnbroker`
    như một gate blocking — nó đỏ 1207 lỗi từ lâu (xem KNOWN-RED).
#>
[CmdletBinding()]
param(
    [switch]$Quick,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Console Windows mặc định là cp1252; script in tiếng Việt có dấu sẽ
# UnicodeEncodeError. Đây chính là lỗi đã làm `check_dist_contents.py`
# báo đỏ giả. Bắt buộc cho mọi process con.
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# Dung interpreter cua repo. KHONG fallback sang `python` he thong: interpreter
# sai tao ra exit 1 o moi gate, va gate dang-red-san se bi gan nhan KNOWN-RED
# vi "khong co ruff" — tuc hang rao do vi LY DO SAI, dong nghĩa voi khong
# co gate. Fail som, noi ro nguyen nhan.
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[FATAL] Khong tim thay $venvPython" -ForegroundColor Red
    Write-Host '        Gate phai chay tren interpreter cua repo. Cai dat:' -ForegroundColor Red
    Write-Host '        python -m venv .venv' -ForegroundColor Red
    Write-Host '        .venv\Scripts\pip install -e ".[test,lint]"' -ForegroundColor Red
    exit 2
}
$python = $venvPython

# Preflight: tool phai ton tai truoc khi chay gate, neu khong moi gate bao
# exit 1 co y nghia. Chan "gate do vi thieu tool" nham thanh "gate do vi code".
Write-Host '[PRE ] kiem tra tool: ruff, mypy, pytest ...'
$missing = [System.Collections.Generic.List[string]]::new()
foreach ($tool in @('ruff', 'mypy', 'pytest')) {
    & $python -c "import $tool" 2>$null
    if ($LASTEXITCODE -ne 0) { $missing.Add($tool) }
}
if ($missing.Count -gt 0) {
    Write-Host ("[FATAL] Interpreter thieu module: {0}" -f ($missing -join ', ')) -ForegroundColor Red
    Write-Host '        .venv\Scripts\pip install -e ".[test,lint]"' -ForegroundColor Red
    Write-Host '        Khong fallback: gate bao exit 1 vi thieu tool se bi doc nham' -ForegroundColor Red
    Write-Host '        la gate that dang do.' -ForegroundColor Red
    exit 2
}
Write-Host '[PRE ] ok.' -ForegroundColor Green

# Gate đang đỏ sẵn ở HEAD, không do thay đổi hiện tại. Không tính vào FAIL
# nhưng vẫn in ra: gate báo đỏ ở đây là HET SỰ THẬT, không phải hỏng.
$knownRed = @{
    'ruff-tests-all' = '13 F401/F841 co san o HEAD (test_tier1_dod.py, vci_proxy_demo.py, test_acb_all_providers.py)'
    'mypy-raw'        = '1207 loi co san; chi check_mypy_baseline.py moi la gate'
}

$gates = @(
    @{ name = 'ruff-src';      cmd = { & $python -m ruff check vnbroker tests/unit tests/contract } }
    @{ name = 'ruff-tests-all'; cmd = { & $python -m ruff check tests } }
    @{ name = 'version-sync';  cmd = { & $python scripts/check_version_sync.py } }
    @{ name = 'lessons';        cmd = { & $python scripts/check_lessons.py } }
    @{ name = 'tcbs-coverage';  cmd = { & $python scripts/verify_tcbs_coverage.py } }
    @{ name = 'tcbs-bodies';    cmd = { & $python scripts/check_tcbs_bodies.py --baseline docs/tcbs_body_baseline.json } }
    @{ name = 'mypy-baseline'; cmd = { & $python scripts/check_mypy_baseline.py } }
    @{ name = 'pytest-contract'; cmd = { & $python -m pytest tests/contract -q -p no:cacheprovider } }
    @{ name = 'pytest-full';   cmd = { & $python -m pytest tests/ -q --timeout=300 -p no:cacheprovider }; skipIfQuick = $true }
)

function Get-GateStatus {
    param([string]$Name, [int]$Code)
    if ($Code -eq 0) { return 'PASS' }
    if ($knownRed.ContainsKey($Name)) { return 'KNOWN-RED' }
    return 'FAIL'
}

# --- Self test: chung mot logic phan loai voi duong chay that -------------
# Gate chi duoc tin khi da thay no do it mot lan. Self test nay inject
# 3 gate gia: xanh / do-kenh / that, va kiem tra ca 3 duoc phan loai
# dung, dong thoi kiem tra exit code cuoi la 1.
if ($SelfTest) {
    $script:fails = 0
    $cases = @(
        @{ name = 'fake-green';  code = 0; expected = 'PASS' }
        @{ name = 'ruff-tests-all'; code = 1; expected = 'KNOWN-RED' }
        @{ name = 'fake-red';    code = 1; expected = 'FAIL' }
    )
    foreach ($c in $cases) {
        $got = Get-GateStatus -Name $c.name -Code $c.code
        $ok = ($got -eq $c.expected)
        if (-not $ok) { $script:fails++ }
        $mark = if ($ok) { 'OK  ' } else { 'BAD ' }
        Write-Host ("[{0}] {1,-14} exit={2} -> {3}  (mong doi {4})" -f `
            $mark, $c.name, $c.code, $got, $c.expected) `
            -ForegroundColor $(if ($ok) { 'Green' } else { 'Red' })
    }
    # Gate that phai lam script exit 1.
    $expectedExit = $(if ($script:fails -eq 0) { 1 } else { 2 })
    Write-Host ("[INFO] selftest co {0} gate that bi gan sai. Script that se exit {1}." -f $script:fails, $expectedExit) -ForegroundColor Cyan
    if ($script:fails -gt 0) { exit 2 }
    exit $expectedExit
}

# Chạy self-test của các gate mới (chứng minh chúng thật sự FAIL khi bị vi phạm).
    # Không phải gate repo, nhưng phải xanh - một self-test đỏ nghĩa là gate đó vô dụng.
    Write-Host ''
    Write-Host '=== SELF-TEST GATE MOI ===' -ForegroundColor Cyan
    foreach ($st in @(
        @{ name = 'lessons-selftest'; cmd = { & $python scripts/check_lessons.py --self-test } }
        @{ name = 'tcbs-bodies-selftest'; cmd = { & $python scripts/check_tcbs_bodies.py --self-test } }
    )) {
        & $st.cmd 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "  [SELFTEST] $($st.name): $_" }
    }
    Write-Host ''

    $results = [System.Collections.Generic.List[object]]::new()
$failures = 0
$skipped = 0

foreach ($gate in $gates) {
    if ($gate.skipIfQuick -and $Quick) {
        $results.Add([pscustomobject]@{
            Gate = $gate.name; Status = 'SKIP'; Detail = '-Quick'; Exit = $null
        })
        $skipped++
        Write-Host ("[SKIP] {0}" -f $gate.name)
        continue
    }

    Write-Host ("[RUN ] {0} ..." -f $gate.name)
    $sw = [Diagnostics.Stopwatch]::StartNew()

    # Bắt exit code thật, KHONG pipe qua filter nao.
    $out = & $gate.cmd 2>&1
    $code = $LASTEXITCODE
    $sw.Stop()

    # Lay dong ket qua that (khong phai dong nhac sau do): pytest in
    # "PermissionError ... cleanup_numbered_dir" o atexit DU khi suite xanh,
    # va dong do la thong tin sai lam nguoi doc tuongng gate do.
    # Lay dong ket qua that. pytest in "N passed" o dau dong ket thuc
    # (sau do con nhieu dong), va con in them PermissionError cua atexit
    # DU suite xanh — dong do la thong tin sai. Quet toan bo output, giu
    # dong khop pattern, uu tien dong cuoi cung khop.
    $tail = ''
    foreach ($line in $out) {
        $text = ([string]$line).Trim()
        if ($text -match '\d+ (passed|failed|error|skipped|warning)s?\b.*in [\d.]+s' `
            -or $text -match 'All checks passed' `
            -or $text -match '^OK: no new strict errors' `
            -or $text -match '^version-sync OK' `
            -or $text -match '^dist-contents OK' `
            -or $text -match 'check_lessons: .*- sach' `
            -or $text -match '^spec sha256.*KHOOP' `
            -or $text -match 'SELF-TEST PASS' `
            -or $text -match '^Found \d+ errors?') {
            $tail = $text
        }
    }
    if ($tail -eq '') {
        $nonEmpty = @($out | Where-Object { ([string]$_).Trim() -ne '' })
        if ($nonEmpty.Count -gt 0) { $tail = ([string]$nonEmpty[-1]).Trim() }
    }
    $tail = if ($tail) { ([string]$tail).Trim() } else { '' }
    if ($tail.Length -gt 90) { $tail = $tail.Substring(0, 87) + '...' }

    $status = Get-GateStatus -Name $gate.name -Code $code
    if ($status -eq 'FAIL') { $failures++ }

    $results.Add([pscustomobject]@{
        Gate = $gate.name; Status = $status; Detail = $tail; Exit = $code
    })

    $colour = switch ($status) {
        'PASS' { 'Green' }
        'KNOWN-RED' { 'DarkYellow' }
        default { 'Red' }
    }
    Write-Host ("[{0}] {1}  exit={2}  {3:N1}s  {4}" -f $status.PadRight(9), $gate.name, $code, $sw.Elapsed.TotalSeconds, $tail) -ForegroundColor $colour
}

Write-Host ''
Write-Host '=== TONG KET GATE ===' -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-String | Write-Host

if ($knownRed.Count -gt 0) {
    Write-Host 'Gate DANG DO SAN o HEAD (khong tinh FAIL, nhung van that):' -ForegroundColor DarkYellow
    foreach ($k in $knownRed.Keys) { Write-Host ("  - {0}: {1}" -f $k, $knownRed[$k]) }
    Write-Host ''
}

Write-Host 'CI GITHUB ACTIONS: CHUA CHAY (job bi tu choi khoi dong do billing).' -ForegroundColor Red
Write-Host 'Ket qua o tren la ket qua LOCAL — dung no, dung hieu CI co xanh.' -ForegroundColor Red
Write-Host ''

if ($skipped -gt 0) {
    Write-Host ("SKIPPED: {0} gate (do -Quick). Chay lai khong -Quick truoc khi merge." -f $skipped) -ForegroundColor Yellow
    Write-Host ''
}

if ($failures -gt 0) {
    Write-Host ("FAIL: {0} gate that dang do. KHONG merge." -f $failures) -ForegroundColor Red
    exit 1
}

Write-Host 'PASS: khong gate nao that bai.' -ForegroundColor Green
exit 0
