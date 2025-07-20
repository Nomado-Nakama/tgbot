function Get-LLMChanges {
<#
.SYNOPSIS
    Produce llm_changes.xml: repomix context + before/after diffs
.DESCRIPTION
    1. Detects modified (staged + unstaged) paths.
    2. Embeds last‑committed version and working‑copy diff for each file.
    3. Wraps Repomix XML (only the touched files) in <repo_context>.
    4. Emits UTF‑8 llm_changes.xml at repo root.
.PARAMETER Output
    Override output path (default: llm_changes.xml in repo root)
#>
    [CmdletBinding()]
    param(
        [string]$Output = "llm_changes.xml"
    )

    #---------- Console / encoding hygiene ----------#
    if ($PSVersionTable.PSVersion.Major -ge 5) {
        [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8
    }
    $PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
    $env:LC_ALL = 'C.UTF-8'

    Set-StrictMode -Version Latest

    #---------- Pre‑flight ----------#
    if (-not (Get-Command git  -ErrorAction SilentlyContinue)) {
        throw "Git is required but not found in PATH."
    }
    if (-not (Get-Command repomix -ErrorAction SilentlyContinue)) {
        throw "Repomix is required but not found in PATH."
    }

    $repoRoot = (git rev-parse --show-toplevel 2>$null).Trim()
    if (-not $repoRoot) { throw "Not inside a Git repository." }

    try {
        Push-Location $repoRoot

        # 1. what changed?
        $files = @(git diff --name-only           2>$null) +
                 @(git diff --cached --name-only 2>$null) |
                 Where-Object { $_ } | Sort-Object -Unique

        if (!$files) {
            Write-Warning 'No uncommitted changes detected.'; return
        }

        # 2. Repomix context for files that still exist
        $tempCtx = [IO.Path]::GetTempFileName()
        $files | Where-Object { Test-Path $_ } |
            repomix --stdin --style xml --output $tempCtx 2>$null

        # 3. Assemble XML
        $xml  = [xml]'<?xml version="1.0"?><llm_changes/>'
        $root = $xml.DocumentElement

        $ctx  = $xml.CreateElement('repo_context')
        $ctx.AppendChild(
            $xml.CreateCDataSection((Get-Content $tempCtx -Raw))
        ) | Out-Null
        $root.AppendChild($ctx) | Out-Null

        foreach ($f in $files) {
            $fileNode = $xml.CreateElement('file')
            ($pathAttr = $xml.CreateAttribute('path')).Value = $f
            $fileNode.Attributes.Append($pathAttr) | Out-Null

            # --- before (HEAD) ---
            $before = $xml.CreateElement('before')
            $before.AppendChild(
                $xml.CreateCDataSection(
                    (git show "HEAD:$f" 2>$null) -join "`n"
                )
            ) | Out-Null
            $fileNode.AppendChild($before) | Out-Null

            # --- diff (working copy) ---
            $diff = $xml.CreateElement('diff')
            $diff.AppendChild(
                $xml.CreateCDataSection(
                    (git diff --unified=3 -- $f 2>$null) -join "`n"
                )
            ) | Out-Null
            $fileNode.AppendChild($diff)  | Out-Null

            $root.AppendChild($fileNode)  | Out-Null
        }
        # ---------- 5. extra LLM tasks -----------------------------------------
		# latest commit message (may be multi‑line)
		$latestCommit = (git log -1 --pretty=%B 2>$null) -join "`n"

		# absolute path to CHANGELOG
		$clPath   = Join-Path $repoRoot 'docs/CHANGELOG.md'

		# read file or fall back to empty string
		$changelog = if (Test-Path $clPath) {
						 Get-Content $clPath -Raw
					 } else { '' }

		$taskRoot = $xml.CreateElement('llm_task')
		$root.AppendChild($taskRoot) | Out-Null

		# --- commit message task ---
		$t1 = $xml.CreateElement('task')
		($a1 = $xml.CreateAttribute('type')).Value = 'commit_message'
		$t1.Attributes.Append($a1) | Out-Null
		$t1.AppendChild($xml.CreateCDataSection(
@"
Based on the introduced changes, craft the next conventional‑style commit message.
Write new semantic version at the start of the commit message based of latest commit message + new changelog entry.
The latest commit on this branch is: $latestCommit
"@
		)
		) | Out-Null
		$taskRoot.AppendChild($t1) | Out-Null

		# --- changelog task ---
		$t2 = $xml.CreateElement('task')
		($a2 = $xml.CreateAttribute('type')).Value = 'changelog_update'
		$t2.Attributes.Append($a2) | Out-Null
		$t2.AppendChild($xml.CreateCDataSection(
@"
Generate the Markdown fragment that should be appended to CHANGELOG.md to reflect the new work.
The current CHANGELOG.md is: $changelog
"@
		)
		) | Out-Null
		$taskRoot.AppendChild($t2) | Out-Null

        # 4. list deletions too
        git diff --name-only --diff-filter=D 2>$null | ForEach-Object {
            $del = $xml.CreateElement('file')
            ($p  = $xml.CreateAttribute('path'   )).Value = $_
            ($d  = $xml.CreateAttribute('deleted')).Value = 'true'
            $del.Attributes.Append($p) | Out-Null
            $del.Attributes.Append($d) | Out-Null
            $root.AppendChild($del)    | Out-Null
        }

        $outPath = Join-Path $repoRoot $Output
        $xml.Save($outPath)
        Write-Host "✅  Generated $outPath"
    }
    finally {
        Pop-Location
        if ($tempCtx -and (Test-Path $tempCtx)) { Remove-Item $tempCtx }
    }
}

# run automatically when NOT dot‑sourced
if ($MyInvocation.ExpectingInput -eq $false) {
    Get-LLMChanges @PSBoundParameters
}
