# FAQ — UpaPasta

[Português (pt-BR)](pt-BR/FAQ.md)

Direct answers to the most common questions. For step-by-step diagnosis, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Installation and Configuration

**Q: `upapasta: command not found` after `pip install upapasta`.**

A: The pip script directory is not in your PATH. Add it to your `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Then run `source ~/.bashrc` and try again.

---

**Q: `nyuu: command not found`.**

A: Install it via npm: `npm install -g nyuu`. If Node is not installed: `apt install nodejs npm`. Confirm with `nyuu --version`.

---

**Q: `parpar: command not found`.**

A: Install it via pip: `pip install parpar`. Confirm with `parpar --version`.

---

**Q: SSL handshake fails when connecting to the NNTP server.**

A: First test: `upapasta --test-connection`. If it fails with a certificate error, your server has a self-signed or expired certificate. Options:
1. Set `NNTP_IGNORE_CERT=true` in `.env` (trusted environments only)
2. Use `upapasta --test-connection --insecure` to confirm this is the issue before modifying `.env`

---

**Q: `upapasta --config` does not update credentials.**

A: Pressing Enter without typing anything **keeps** the current value. To clear a field, press space and then Enter (it will store a space) — then edit `.env` directly with a text editor.

---

## Upload

**Q: nyuu error 401 or 403.**

A: Invalid credentials. Check `NNTP_USER` and `NNTP_PASS` in `.env`. If using failover, also check `NNTP_USER_2`, `NNTP_PASS_2`, etc. Use `upapasta --test-connection` to validate.

---

**Q: nyuu error 502 / Bad Gateway.**

A: The NNTP server is overloaded or under maintenance. Try again in a few minutes. Configure `--upload-retries 3` for automatic retry with exponential backoff.

---

**Q: Upload stops in the middle without a clear error message.**

A: Likely a connection timeout. Add `--upload-timeout 300` (5 minutes). If the problem persists, configure a failover server — see [DOCS.md § 7](DOCS.md#7-multiple-nntp-servers).

---

**Q: How to resume an upload that was interrupted with Ctrl+C?**

A: Use `--resume` with the same flags as the original upload:
```bash
upapasta Folder/ --resume
# or with the original flags:
upapasta Folder/ --obfuscate --par-profile safe --resume
```
UpaPasta detects the saved `.upapasta-state.json` and uploads only the remaining files.

---

**Q: `--resume` says state file not found.**

A: The `.upapasta-state.json` file is saved in the same directory as the output NZB. If it was deleted, moved, or never created (upload failed before starting), you will need to perform a full upload without `--resume`.

---

## PAR2

**Q: PAR2 generation fails with an error message from parpar.**

A: Most common causes:
1. **Disk space:** UpaPasta needs approximately 2× the source size. Check with `df -h`.
2. **Permissions:** The destination directory must be writable.
3. **Insufficient memory:** Add `--max-memory 512` to limit usage.

UpaPasta automatically tries a second time with fewer threads and the `safe` profile. If it still fails, see the instruction message printed on the screen to resume manually.

---

**Q: `par2: command not found` (using `--backend par2`).**

A: Install it: `apt install par2` (Debian/Ubuntu) or `brew install par2` (macOS). Recommended alternative: use `--backend parpar` (faster, supports subfolders).

---

**Q: SABnzbd does not rebuild the folder structure after downloading.**

A: Two options:
1. Ensure you used `--filepath-format common` (default) when uploading with `parpar`. SABnzbd must have "Repair Archive" active.
2. If SABnzbd has "Recursive Unpacking" active, **disable it** — it may disrupt the structure.

---

## Obfuscation

**Q: What is the difference between `--obfuscate` and `--strong-obfuscate`?**

A:

| | `--obfuscate` | `--strong-obfuscate` |
|--|--------------|---------------------|
| Filenames on Usenet | random | random |
| Subjects in NZB | **original names** | random |
| Do indexers see content? | no | no |
| Does downloader see names? | yes (via NZB) | no (requires PAR2) |

Use `--obfuscate` for normal use (DMCA protection with download convenience). Use `--strong-obfuscate` only when maximum privacy is critical.

---

**Q: I used `--obfuscate` and local files kept random names after upload.**

A: This should not happen — rollback is guaranteed via `finally`. Check if the terminal showed any "reversion failed" warning. If so, manual reversion instructions were printed. If not, it might be a bug — open an issue with the log (`--log-file`).

---

**Q: Does `--password` without `--rar` work?**

A: `--password` automatically implies `--rar` since version 0.18.0. You don't need to type `--rar` separately. The combination `--skip-rar --password` is still a fatal error.

---

## Catalog

**Q: `history.db not found` or sqlite3 error.**

A: The catalog moved to JSONL in version 0.12.0. The correct file is `~/.config/upapasta/history.jsonl`. `history.db` no longer exists. To query:
```bash
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool
upapasta --stats
```

---

**Q: `upapasta --stats` shows nothing.**

A: There are no recorded uploads yet. The `history.jsonl` file is created on the first successful upload.

---

**Q: How to recover the password for an obfuscated upload?**

A: The password is recorded in the `senha_rar` field of the catalog:
```bash
grep "ReleaseName" ~/.config/upapasta/history.jsonl | python3 -m json.tool
```
NZBs also have the password injected in `<meta type="password">` — SABnzbd and NZBGet read it automatically.

---

## SABnzbd

**Q: SABnzbd adds `.txt` to files without an extension.**

A: Use `--rename-extensionless` when uploading. UpaPasta renames files to `.bin` before upload and reverts at the end. SABnzbd receives files as `.bin` and does not add `.txt`.

---

**Q: SABnzbd unpacks internal `.zip` files that should be preserved.**

A: Disable "Recursive Unpacking" in SABnzbd settings (`Config → General → Recursive Unpacking`).

---

## Folders and Structure

**Q: Empty subfolders disappear after downloading.**

A: Usenet and PAR2 only transport files. Without RAR, empty directories do not exist. Solution:
- Add `--rar` to preserve the structure via a RAR container
- Or place a sentinel file (`.keep`) in each empty subfolder before uploading

---

**Q: I have a folder with a single file. Does UpaPasta create a RAR?**

A: Not by default. RAR is only created with `--rar`, `--password`, or `--obfuscate` on a single file. If you don't use any of these flags, the file is uploaded directly.
