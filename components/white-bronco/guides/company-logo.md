---
name: company-logo
description: How to add a vendor company logo to a disclosure report in LaTeX. Covers file placement, format selection, title-page patterns, and logo sources for all vendors in the PSIRT directory.
tools:
  - Read
  - Edit
  - Write
  - Bash
---

# Adding a Company Logo to a Disclosure Report

## File placement

Put logo files in `logos/` at the repo root. The template references them via relative path `../logos/<name>`. Reference the file without its extension. LaTeX resolves PDF first when using pdflatex.

```latex
\includegraphics[height=1.4cm]{../logos/cisco}       % resolves logos/cisco.pdf
\includegraphics[height=1.4cm]{../logos/cisa}        % resolves logos/cisa.png (PNG-only vendor)
```

## Format decision

| Format | When to use |
|--------|-------------|
| PDF    | Always prefer for `pdflatex`. Vector, scales losslessly at any print size. |
| SVG    | Use with `lualatex`/`xelatex` + `svg` package. Not supported by `pdflatex` natively. |
| PNG    | Fallback when no vector exists. Use high-res source (200px+ per cm of display size). |

## Template usage

The template (`templates/disclosure-report.tex`) already loads `graphicx` and includes a logo block on the title page. Replace the logo path to match the target vendor:

```latex
% Pattern A: corporate wordmark only
\begin{flushright}
  \includegraphics[height=1.4cm]{../logos/cisco}
\end{flushright}

% Pattern B: wordmark + product logo side-by-side
\begin{flushright}
  \includegraphics[height=1.4cm]{../logos/fortinet}\quad
  \includegraphics[height=1.4cm]{../logos/fortimanager}
\end{flushright}

% Pattern C: no logo (delete the block entirely)
```

`height=1.4cm` is the standard for the title page block. For the page header (`fancyhdr`), use `height=0.5cm` so it fits within `headheight`.

## Logo in the page header

To repeat a small logo in every page header, add this after the fancyhdr setup:

```latex
\fancyhead[L]{%
  \raisebox{-0.15\height}{\includegraphics[height=0.5cm]{../logos/<vendor>}}\quad
  \small\textit{[VENDOR] [PRODUCT]: Vulnerability Disclosure}%
}
```

The `\raisebox` keeps the logo baseline aligned with the text.

## Vendor logo inventory

All logos ship as `logos/<vendor>.pdf` + `logos/<vendor>.svg` (vector pair) or `logos/<vendor>.png` (raster fallback). The PDF is the primary asset for pdflatex.

### Coordinators

| Vendor | File | Formats |
|--------|------|---------|
| CISA | `cisa` | PNG |
| CERT/CC | `certcc` | PDF, SVG |
| FIRST | `first-org` | PDF, SVG |

### Networking / Security Appliances

| Vendor | File | Formats |
|--------|------|---------|
| Cisco | `cisco` | PDF, SVG |
| Fortinet (corporate) | `fortinet` | PDF, SVG, PNG |
| Palo Alto Networks | `paloalto` | PDF, SVG |
| Juniper Networks | `juniper` | PDF, SVG |
| F5 Networks | `f5` | PDF, SVG |
| SonicWall | `sonicwall` | PDF, SVG |
| Check Point | `checkpoint` | PNG |
| Aruba Networks | `aruba` | PDF, SVG |

### Enterprise IT / Software

| Vendor | File | Formats |
|--------|------|---------|
| Microsoft | `microsoft` | PDF, SVG |
| Google | `google` | PDF, SVG |
| Apple | `apple` | PDF, SVG |
| IBM | `ibm` | PDF, SVG |
| Oracle | `oracle` | PDF, SVG |
| VMware / Broadcom | `broadcom-vmware` | PDF, SVG |
| SAP | `sap` | PDF, SVG |
| Atlassian | `atlassian` | PDF, SVG, PNG |
| GitLab | `gitlab` | PDF, SVG |
| Adobe | `adobe` | PDF, SVG |
| SolarWinds | `solarwinds` | PNG |
| Ivanti | `ivanti` | PDF, SVG |
| Citrix | `citrix` | PDF, SVG, PNG |

### Infrastructure / Cloud

| Vendor | File | Formats |
|--------|------|---------|
| Amazon AWS | `aws` | PDF, SVG |
| Akamai | `akamai` | PDF, SVG |
| Cloudflare | `cloudflare` | PDF, SVG |
| HashiCorp | `hashicorp` | PNG |
| Red Hat | `redhat` | PDF, SVG |

### Hardware / Workstations / Servers

| Vendor | File | Formats |
|--------|------|---------|
| HPE | `hpe` | PDF, SVG |
| HP Inc. | `hp` | PDF, SVG |
| Dell | `dell` | PDF, SVG |
| Lenovo | `lenovo` | PDF, SVG |
| Intel | `intel` | PDF, SVG, PNG |
| AMD | `amd` | PDF, SVG |
| NVIDIA | `nvidia` | PDF, SVG |
| Qualcomm | `qualcomm` | PDF, SVG |
| ARM | `arm` | PDF, SVG, PNG |

### ICS / OT / Industrial

| Vendor | File | Formats |
|--------|------|---------|
| Siemens | `siemens` | PDF, SVG |
| Schneider Electric | `schneider` | PDF, SVG, PNG |
| Rockwell Automation | `rockwell` | PDF, SVG |
| Honeywell | `honeywell` | PDF, SVG |
| ABB | `abb` | PDF, SVG |
| Emerson | `emerson` | PNG |
| GE Vernova | `ge-vernova` | PDF, SVG |
| Mitsubishi Electric | `mitsubishi-elec` | PDF, SVG |
| Phoenix Contact | `phoenixcontact` | PNG |
| Moxa | `moxa` | PDF, SVG |
| AVEVA | `aveva` | PDF, SVG |

### Telecom / Semiconductor

| Vendor | File | Formats |
|--------|------|---------|
| Ericsson | `ericsson` | PDF, SVG, PNG |
| Nokia | `nokia` | PDF, SVG, PNG |
| Huawei | `huawei` | PDF, SVG |
| NXP Semiconductors | `nxp` | PNG |
| Broadcom | `broadcom` | PDF, SVG |

## Adding logos for new vendors

1. **Check the vendor's press kit / brand portal first.** Most large vendors have one.
2. **Wikimedia Commons** (`commons.wikimedia.org/wiki/Special:FilePath/<File_Name.svg>`): most corporate logos are there as SVG.
3. **Official Visio stencil ZIPs**: many vendors publish these for network diagrams; the embedded PNG icons are 200x200 RGBA.
4. Convert SVG to PDF with `rsvg-convert` (package: `librsvg2-bin`):
   ```bash
   rsvg-convert -f pdf -o vendor.pdf vendor.svg
   ```
5. Place both files in `logos/` and reference without extension in `\includegraphics`.

