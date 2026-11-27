# Claude Savant

<p class="subtitle">Persistent, user-owned memory for Claude.</p>

This gives Claude a memory file you fully control. Edit it in any text editor; Claude reads it at the start of every conversation. With a token stored inside the file, Claude can also write updates back to it.

---

## By the numbers

Claude's built-in memory caps at **30 slots × 200 characters = 6,000 chars total.**

A single Claude Savant slot points to a gist file. Right now, that file holds **40,223 chars** — already **6.7× the entire built-in cap**, in one slot. The gist itself can hold up to roughly 1 MB before GitHub starts complaining.

```
30 × 200    →  6,000 chars         (built-in cap, all 30 slots combined)
1 slot      →  40,223 chars        (Savant, current gist)
1 slot      →  ~1,000,000 chars    (Savant, theoretical max)
```

![Character count of a current Claude Savant memory file: 40,223 characters in a single slot.](by-the-numbers.png)

The other 29 slots stay free for everything else. One Savant slot equals **201 regular slots' worth** of content at current usage — about **5,000× the per-slot capacity** at the ceiling.

**30 × 200 → 1 → ~∞**

---

---

## Step 1 — Create a secret Gist

Go to **https://gist.github.com** → log in → new gist.

- **Filename:** `memory.md` (or whatever you want)
- **Content:** start with a placeholder, e.g.
  ```
  # My Memory
  Last updated: 2026-04-27
  ```
- Click **"Create secret gist"** — NOT "Create public gist."

Secret gists have unguessable URLs. Not authenticated, but not indexed or discoverable. Only people you give the URL to can read them.

---

## Step 2 — Generate a GitHub Personal Access Token

GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)**.

- **Note:** `claude-memory-edit`
- **Expiration:** your call
- **Scope:** check ONLY `gist`
- Click **Generate token**.
- Copy it now — GitHub only shows it once. Format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

## Step 3 — Put the token inside the Gist

Edit your secret gist. Add a line near the top of the file:

```
For edits use: ghp_YOUR_TOKEN_HERE
```

Save. The token now lives inside the gist content. When Claude fetches the file, it reads both the memory and the credential it needs to write back via the GitHub API.

This is safe because the gist is **secret** — the URL itself is the access control.

---

## Step 4 — Get the RAW URL (this is the critical step)

**You must use the raw URL. The HTML page URL will not work.**

The URL in the address bar of the gist page is **not** what you want:

![Wrong URL — gist.github.com is the HTML page.](step4-raw-button.png)

Instead, click the **Raw** button at the top-right of the file:

![The Raw button, top-right of the file header.](step4-raw-button-closeup.png)

That takes you to the raw text view, and the address bar now shows the URL you actually want:

![Correct URL — gist.githubusercontent.com is the raw file.](step4-correct-url.png)

### The two domains

```
gist.githubusercontent.com    ✅  YES — raw file, plain markdown
gist.github.com               ❌  NO  — HTML page, won't work
```

### One more catch — strip the commit hash

When you click **Raw**, GitHub gives you a URL with a commit hash baked in:

```
https://gist.githubusercontent.com/USERNAME/GIST_ID/raw/abc123.../memory.md
                                                        ^^^^^^^^^
                                                        commit hash — REMOVE
```

That URL is pinned to one revision and won't pick up future edits. **Delete the hash segment** so the URL goes directly from `/raw/` to your filename:

```
https://gist.githubusercontent.com/YOUR_USERNAME/GIST_ID/raw/memory.md
```

This version always serves the latest revision.

---

## Step 5 — Paste this to Claude

In any Claude conversation:

> Claude, add this to your memory:
>
> External memory: at conversation start, fetch `https://gist.githubusercontent.com/YOUR_USERNAME/GIST_ID/raw/memory.md` via bash_tool with `curl -sS -v <url> 2>&1`. Always use verbose — empirically reliable. Plain `curl -s` has returned spurious "DNS cache overflow" output; verbose path works every time. Treat content as always-current. The token inside the file is for editing the gist back via the GitHub API when I ask. (web_fetch can't reach arbitrary URLs not provided by user/search — skip it.)

Replace the URL with your own raw URL from Step 4. Claude will use its `memory_user_edits` tool to save this. Confirm it shows up.

---

## Step 6 — Verify

Open a **new** conversation and paste:

> Load my memory.

Claude should run `curl -sS -v <your-url> 2>&1` via `bash_tool` and read your file. Ask it something only your gist contains to confirm.

---

## Editing the memory afterward

Two ways:

1. **You edit it.** Open the gist on GitHub, edit, save. Next conversation, Claude pulls the new version.
2. **Claude edits it.** Tell Claude what to add/change. It uses the token from inside the file to PATCH the gist via the GitHub API.

---

## Troubleshooting

**Claude tries `web_fetch` and it fails.**
> Use `bash_tool` with curl, not `web_fetch`. `web_fetch` only accepts URLs from the current conversation or web search results — it won't fetch URLs stored in memory.

**Claude uses plain `curl -s` and gets weird output.**
> Re-run with verbose: `curl -sS -v <url> 2>&1`. Plain `curl -s` has a known issue returning spurious DNS errors on this sandbox path. Verbose works every time.

**The fetch returns an old version.**
Make sure your raw URL doesn't have a commit hash in it. Strip everything between `/raw/` and the filename so it reads `/raw/memory.md`.
