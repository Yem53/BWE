---
name: All BWE memory must mirror to H drive
description: Every auto-memory write must go to both ~/.claude AND H:\BWE\.claude_memory_shared\ so it travels between 5090 and Mac mini
type: feedback
---

When saving ANY new memory file in this BWE Autoresearch project (feedback / project / reference / user types), write to BOTH locations:

1. `~/.claude/projects/<machine-specific-hash>/memory/<file>.md`
   - On 5090 Windows: `C:\Users\Admin\.claude\projects\H--\memory\<file>.md`
   - On Mac mini: `~/.claude/projects/-Volumes-T9-BWE/memory/<file>.md` (path will differ — check actual cwd hash)
2. `H:\BWE\.claude_memory_shared\<file>.md` (Mac: `/Volumes/T9/BWE/.claude_memory_shared/<file>.md`)

Same rule applies to `MEMORY.md` index file — keep both copies in sync on every update.

Plus: `H:\BWE\CLAUDE.md` is the project-level permanent memory, auto-loaded by Claude Code on any machine. Stable, curated content goes there. Per-conversation auto-learned memory goes in the structured `.claude_memory_shared/<file>.md` files.

**Why:** User runs Claude Code on two machines (5090 Windows + Mac mini macOS) and the H: drive (4TB exFAT, label "T9") travels between them. Each machine has its own `~/.claude/projects/<hash>/` folder (different hash per cwd), so memory does NOT auto-share. The H: drive shared folder is the only portable location. exFAT does NOT support symlinks, so we mirror by copy — not symlink.

User's exact request (2026-04-27):
> "现在就做，然后之后的每一步都需要将这些memory注入到硬盘中"
> ("Do it now, and from now on every step needs to inject these memories into the hard drive")

**How to apply:**
- Every Write call for a memory file must be followed by a second Write call to the H: drive mirror, OR a single cp command after the primary write
- If the H: drive is not mounted (e.g., user moved it), warn the user and skip the H: write — do NOT silently lose the sync
- When entering a fresh Claude Code session on a new machine, check if `~/.claude/projects/<hash>/memory/` is empty; if so, copy from `H:/BWE/.claude_memory_shared/` to bootstrap, then continue normal dual-write behavior
- This rule is project-specific to BWE Autoresearch — does not apply to other projects
