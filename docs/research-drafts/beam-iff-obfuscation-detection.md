# BEAM IFF Container & Atom-Table Obfuscation Detection

> Preserved from Google Drive draft (`No obfuscation detection -- stripped atom tables,....docx`).

---

Missing these signals leaves a significant blind spot in BEAM analysis. Modern Erlang/Elixir obfuscators explicitly target the IFF (Interchange File Format) container structure and the string pool to crash decompilers while keeping the bytecode completely valid for the underlying BEAM virtual machine.

To close this gap in your analysis pipeline, you need to parse the .beam container strictly and apply heuristic checks to the specific chunks.

1. Detecting Corrupted Chunk Sequences

BEAM files are standard EA IFF 85 containers. The Erlang VM's C-level loader (beam_load.c) is highly forgiving—it silently ignores unknown chunks and garbage data. Decompilers often crash when they attempt to parse this same malformed data sequentially.

Implementation Logic:

Header vs. Physical Size: Read the first 4 bytes (FOR1), followed by the container size (uint32). If this declared size does not match the actual physical file size on disk, flag it as a Container Anomaly. Obfuscators frequently append malicious payloads or garbage data past the declared EOF.

Boundary Violations: Iterate through the chunk headers. If any individual chunk's offset + size pointer extends beyond the EOF or overlaps with another chunk's memory space, flag it as a Corrupted Sequence.

Rogue Chunks: Maintain a strict whitelist of known chunk IDs (Atom, AtU8, Code, StrT, ImpT, ExpT, FunT, LitT, LocT, Attr, CInf, Dbgi, Line). Flag the presence of any unregistered chunk IDs.

2. Analyzing Stripped or Hashed Atom Tables

The BEAM VM relies entirely on the atom table (Atom or AtU8 chunks) for function calls, module references, and control flow routing. An obfuscator cannot completely remove the atom table without breaking the module, so they mutate it instead.

Implementation Logic:

Shannon Entropy Spikes: Extract the AtU8 chunk and parse the string pool. Legitimate Erlang/Elixir atoms (e.g., start_link, handle_cast) possess predictable English-language entropy. Calculate the Shannon entropy across the pool; a sudden spike indicates that function and variable names have been hashed or randomized (e.g., a1b2c3d4).

Character Bounds: Iterate through the atom names and flag the file if the table contains non-printable ASCII characters, zero-width spaces, or control characters outside standard UTF-8 Elixir macro bounds.

Atom Starvation: Compare the total number of atoms against the size of the Code chunk. A massive bytecode payload with an artificially minimal atom table indicates heavy control-flow flattening or dynamic module loading.

3. Profiling Missing Debug and Line Chunks

Stripping debug information (no_debug_info) is a standard compiler flag for production releases, meaning its absence alone is not inherently malicious. However, it becomes a strong obfuscation signal when combined with other missing chunks.

Implementation Logic:

Line Chunk Stripping: Look for the absence of the Line chunk. While Dbgi (Debug Info) or Abst (Abstract Syntax Tree) are routinely stripped to save space, the Line chunk—which maps bytecode instructions to source lines for stack traces—is usually preserved. Its deliberate removal strongly signals anti-analysis intent.

Poisoned Payloads: If the Dbgi or Abst chunks are present, attempt to decompress their internal zlib payloads. A common obfuscator tactic is to leave the chunk header intact but corrupt the zlib payload. The BEAM VM ignores it, but automated analysis pipelines that blindly attempt decompression will crash. Flag any decompression failures as Tampered Payloads.
