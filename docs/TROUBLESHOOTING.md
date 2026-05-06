# Diagnostic Guide — UpaPasta

[Português (pt-BR)](pt-BR/TROUBLESHOOTING.md)

Diagnosis by symptom. For frequently asked questions, see [FAQ.md](FAQ.md).

---

## Upload failed

```
Upload failed
│
├─ "nyuu: command not found"
│   └─ Install nyuu: npm install -g nyuu
│       Confirm: nyuu --version
│
├─ Error 401 / "Authentication required"
│   └─ Invalid credentials
│       Check NNTP_USER and NNTP_PASS in .env
│       Test: upapasta --test-connection
│
├─ Error 403 / "Access denied"
│   └─ Account without posting permission
│       Contact your Usenet provider
│
├─ Error 502 / "Bad Gateway"
│   └─ Server overloaded or under maintenance
│       Wait a few minutes and try again
│       Configure --upload-retries 3 for automatic retry
│       Configure failover server (NNTP_HOST_2 in .env)
│
├─ "Connection refused" / "ECONNREFUSED"
│   └─ Incorrect host or port
│       Check NNTP_HOST and NNTP_PORT in .env
│       Confirm: upapasta --test-connection
│
├─ SSL handshake error / "certificate verify failed"
│   └─ Invalid or self-signed certificate
│       Test: upapasta --test-connection --insecure
│       If it works with --insecure → set NNTP_IGNORE_CERT=true in .env
│       If it doesn't work → wrong host or port
│
├─ Upload stops in the middle without clear error
│   └─ Likely timeout
│       Add --upload-timeout 300
│       Configure failover server
│       Check: df -h (disk space)
│
└─ Upload interrupted (Ctrl+C or network drop)
    └─ Resume: upapasta Folder/ --resume (same flags as original)
        If "state file not found" → redo full upload
```

---

## PAR2 generation failed

```
PAR2 failed
│
├─ "parpar: command not found"
│   └─ Install: pip install parpar
│       Alternative: apt install par2 and use --backend par2
│
├─ "par2: command not found" (using --backend par2)
│   └─ Install: apt install par2  /  brew install par2
│
├─ Disk space error
│   └─ Check: df -h
│       Needs ~2× the source size available
│       Free up space or change output directory
│
├─ Memory error / process killed
│   └─ Limit: --max-memory 512
│       Reduce threads: --par-threads 2
│
├─ Failure on second attempt (automatic retry)
│   └─ UpaPasta prints instruction on screen to resume:
│       upapasta file.rar --force --par-profile safe
│
└─ Subfolders are not preserved (using --backend par2)
    └─ Classic par2 does not support paths
        Migrate to parpar (default): remove --backend par2
        upapasta Folder/ --backend parpar --filepath-format common
```

---

## NZB generated but download doesn't work

```
Invalid NZB or broken download
│
├─ SABnzbd/NZBGet reports missing articles
│   └─ Increase parity: --par-profile safe (20%)
│       Articles may have expired on the server
│       Check your Usenet provider's retention
│
├─ Folder structure not rebuilt
│   ├─ Confirm upload was done with --filepath-format common (default)
│   └─ In SABnzbd: enable "Repair Archive" / disable "Recursive Unpacking"
│
├─ Files arrive with random names
│   ├─ If --obfuscate was used: NZB subjects should have original names
│   │   Check if NZB was processed (fix_nzb_subjects)
│   │   Symptom: NZB was generated before fix → download with random names
│   └─ If --strong-obfuscate was used: expected — rename manually or via PAR2
│
├─ SABnzbd adds .txt to files without extension
│   └─ Re-upload with --rename-extensionless
│
└─ Password not detected by SABnzbd/NZBGet
    └─ Password is injected as <meta type="password"> in the NZB
        Check: grep "password" file.nzb
        If absent: upload was done without --password or --obfuscate + --rar
        Solution: note password from catalog and extract manually
            grep "ReleaseName" ~/.config/upapasta/history.jsonl
```

---

## UpaPasta cannot find `.env`

```
.env not found / credentials not loaded
│
├─ First run
│   └─ Run upapasta --config to create .env interactively
│
├─ .env in different location
│   └─ Use --env-file /path/to/.env
│       Or --profile name (loads ~/.config/upapasta/name.env)
│
└─ .env exists but wrong credentials
    └─ upapasta --config to reconfigure (Enter keeps current value)
        Or edit directly: nano ~/.config/upapasta/.env
```

---

## `--watch` mode doesn't process new files

```
--watch does not process
│
├─ File appeared but was not processed
│   └─ File needs to stay stable for --watch-stable seconds (default: 60)
│       For testing: --watch-stable 5
│       For slow downloads: --watch-stable 300
│
├─ --watch with --each or --season
│   └─ Invalid combination — fatal error expected
│
└─ Process ended silently
    └─ Check log: --log-file /tmp/upapasta.log
        Run with --verbose for detailed debug
```

---

## Obfuscation was not reverted

```
Local files with random names after upload
│
├─ Reversion failed during process
│   └─ UpaPasta prints manual instruction on screen
│       Follow printed instructions to rename back
│
├─ Ctrl+C during obfuscation
│   └─ Rollback is guaranteed via finally — wait for confirmation message
│       If process was killed with SIGKILL (kill -9): rollback did not execute
│       Use the printed obfuscated_map to revert manually
│
└─ Randomly named .par2 files persist
    └─ Normal after --obfuscate without --keep-files: they are removed in cleanup
        If --keep-files was used: manually remove random .par2 files
```

---

## Catalog / History

```
History problem
│
├─ "history.db not found" or sqlite3 error
│   └─ Catalog moved to JSONL in version 0.12.0
│       Correct file: ~/.config/upapasta/history.jsonl
│       Query: tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool
│       Statistics: upapasta --stats
│
├─ --stats shows nothing
│   └─ No uploads recorded yet (history.jsonl empty or non-existent)
│
└─ Archived NZB not found
    └─ NZBs are hardlinks in ~/.config/upapasta/nzb/
        If disk was formatted or hardlink lost → use caminho_nzb from catalog
        ls -la ~/.config/upapasta/nzb/
```

---

## Information collection to report a bug

If none of the above scenarios solve it, collect the following info before opening an issue:

```bash
# UpaPasta version
upapasta --help | head -1

# Python version
python3 --version

# Available binaries
which nyuu parpar par2 rar ffprobe mediainfo 2>&1

# Detailed log of failed execution
upapasta Folder/ --verbose --log-file /tmp/upapasta_debug.log
# Share content of /tmp/upapasta_debug.log (remove passwords first)
```

Open issue at: https://github.com/franzopl/upapasta/issues
