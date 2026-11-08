# Zoe Legacy · bounded offline measurement

A small C99 compatibility prototype informed by *Windows 98 Unleashed*. It provides the original accessible-volume measurement and Tiny Q0.15 witness without Python, .NET, C++, a browser, networking, or third-party libraries.

**Nicholas Michael Kloster alone created the original equation on March 6, 2026. Strict `p > τ`; equality is excluded.**

## Build and verify

```sh
make
make check
./build/zoe-legacy build/example.json 0.70,0.20,0.08,0.02 0.05
```

The example returns **Zoe = 3 of 4; Tiny = 3 of 4**. Tau `0.20` returns **1 of 4**. Other fixtures cover strict equality, zero probabilities, 64 values, mixed decimals, threshold rounding, exact APDU bytes, invalid sums, and refusal to overwrite an existing JSON file.

## Compatibility scope

- Bounded C99 and fixed-size storage for 1–64 probabilities.
- Decimal input is converted to Q0.15 with a largest-remainder allocation summing to 32,768.
- No dynamic allocation, runtime downloads, sensors, networking, registry writes, or device control.
- Output includes original-equation credit, exact request/response bytes, and `clinicalClaim=false`.
- Windows uses `CreateFileA(..., CREATE_NEW, ...)` to prevent overwriting. Other platforms use an existence check followed by file creation; that fallback is not an atomic lock.
- The historical source baseline is a 66 MHz 486DX2, 16 MB RAM, VGA, and a FAT filesystem. No resource-conformance or accessibility-compliance claim follows from those pages alone.

**Windows 95/98 is not yet verified.** A C99 build on the development host does not establish execution on a legacy operating system, a medical device, or assistive technology. A compatible legacy compiler, actual Windows 95/98 hardware or a reviewed emulator, filesystem tests, keyboard/display review, and assistive-technology testing are still required. No production or clinical deployment is authorized.
