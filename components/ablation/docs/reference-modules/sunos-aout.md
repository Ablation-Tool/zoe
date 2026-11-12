# SunOS SPARC a.out Analysis

`ablation.sunos` parses big-endian SunOS SPARC OMAGIC a.out images and recovers symbols, relocation records, and direct calls using only the Python standard library. It is intended for bounded static analysis of legacy drivers and objects, not execution or general a.out linking.

## Why this exists

1. **SunOS a.out is not ELF.** Header fields, symbol records, text/data layout, and relocation entries require a separate parser.
2. **Raw call placeholders are not final destinations.** Internal relocation records carry explicit signed addends that must be applied to the PC-relative displacement.
3. **Relocations need exact record semantics.** The supported OMAGIC layout uses twelve-byte records with big-endian address, flags, and addend fields.

## Usage

```bash
ablation sunos info INPUT
ablation sunos info INPUT --json
ablation sunos calls INPUT --target 0xADDRESS --json
ablation sunos render INPUT --target 0xADDRESS
```

Zoe users can run the same interface with `zoe launch ablation -- sunos ...`. Python callers use `read_aout(path)` or `parse_aout(data)`. `SunosAout.calls()` returns typed direct calls with raw and resolved targets, external symbol names, delay-slot words, and relocation records.

## Relocation model

Each twelve-byte record contains `r_address:u32`, `flags:u32`, and `r_addend:u32`. The decoder uses:

- `symbol_index=(flags>>8)&0xffffff`;
- `extern=(flags>>7)&1`;
- `pcrel=(flags>>2)&1`;
- `length_code=flags&3`.

For an internal text record with `pcrel=1` and `length_code=2`, the direct-call target is `instruction_VA + sign_extend(displacement30)*4 + signed_addend`. External records resolve to their undefined symbol name. Other relocation records are preserved but not applied.

## Validated evidence

The Lotus Sybase DataLens driver has SHA256 `88a7ce88f9d1ead09508d0b01e636616d14442c98f4c74171d468680e73a5cce`, 1,417 symbols, and 5,800 text/data relocation records. The parser resolves `0xb1b0 -> 0xf624`, `0xb270 -> 0x2998`, and `0xb31c -> 0xd0d8`, including external `_strlen` calls and direct dispatcher calls. These corrected targets supersede raw self-call interpretations.

## Limits

- Only SunOS SPARC OMAGIC is accepted. Other a.out magic values, architectures, and relocation layouts are rejected.
- Direct calls are decoded; indirect calls and complete linker behavior are not claimed.
- Recovered static evidence does not establish protocol state, runtime behavior, or a vulnerability.
- No original executable is run by the parser or CLI.
