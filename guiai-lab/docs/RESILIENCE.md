# Zoe Resilience Atlas

The Resilience Atlas is an educational native scene about essential services, interdependencies, and signal evidence. It combines the 16 US critical-infrastructure sectors with a small waveform-signature laboratory inspired by CERN's evidence-constrained mapper.

**It is not a live monitoring system, a risk score, a critical-infrastructure controller, or an authorization to act.** No sector is assigned a security rating, and dependency links are selected examples rather than an exhaustive model.

## Open and export

```bash
zoe resilience
zoe resilience --sector water --trace host40
zoe resilience --sector energy --trace host80 --output resilience.svg
zoe resilience --output resilience.gem
```

The native atlas exposes sector and trace selectors alongside SVG, PNG, and GEM VDI export. The `gem resilience` command provides the same options. Output paths must be new.

## The 16 sectors

The sector descriptions are short original summaries of official public pages. Follow the links for the full context, responsibilities, and sector-specific plans.

| Sector | Official source |
|:---|:---|
| Chemical | [Chemical Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/chemical-sector) |
| Commercial Facilities | [Commercial Facilities Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/commercial-facilities-sector) |
| Communications | [Communications Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/communications-sector) |
| Critical Manufacturing | [Critical Manufacturing Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/critical-manufacturing-sector) |
| Dams | [Dams Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/dams-sector) |
| Defense Industrial Base | [Defense Industrial Base Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/defense-industrial-base-sector) |
| Emergency Services | [Emergency Services Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/emergency-services-sector) |
| Energy | [Energy Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/energy-sector) |
| Financial Services | [Financial Services Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/financial-services-sector) |
| Food and Agriculture | [Food and Agriculture Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/food-and-agriculture-sector) |
| Government Services and Facilities | [Government Services and Facilities Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/government-facilities-sector) |
| Healthcare and Public Health | [Healthcare and Public Health Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/healthcare-and-public-health-sector) |
| Information Technology | [Information Technology Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/information-technology-sector) |
| Nuclear Reactors, Materials and Waste | [Nuclear Reactors, Materials and Waste Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/nuclear-reactors-materials-and-waste-sector) |
| Transportation Systems | [Transportation Systems Sector](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors/transportation-systems-sector) |
| Water and Wastewater Systems | [Water and Wastewater Systems Sector](https://www.cisa.gov/water-and-wastewater-systems-sector) |

The main [CISA sector overview](https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors) explains why these systems matter to public health, safety, economic security, and national security. Energy and communications provide enabling functions across other sectors. Water, food, healthcare, manufacturing, transportation, and emergency response illustrate why a local disruption can have wider consequences.

## Dependency examples

Selecting a sector highlights documented examples from its public description. For example:

- **Energy:** communications, transportation, water, and critical manufacturing.
- **Communications:** energy, information technology, financial services, emergency services, and transportation.
- **Critical manufacturing:** transportation, energy, chemical, and water.
- **Food and agriculture:** water, transportation, energy, and chemical.
- **Water:** energy, critical manufacturing, healthcare, and communications.

The graph does not infer causality, measure cascade risk, or claim that a dependency is the only path. The Defense Industrial Base is included as an infrastructure sector, not as a reason to build weapon-control software.

## Waveform evidence

The supplied CERN waveform mapper processed **10,759,544 events across 363 storage streams**. Its documented result was one corroborated clock, two ambiguous streams, and 360 unmapped streams. Those aggregate results are cited in the report; the large waveform and external analyzer code are not bundled in Zoe.

Zoe implements a small, independently tested signature preview with four synthetic traces:

| Trace | Classification | Reason |
|:---|:---|:---|
| `host80` | `corroborated` | One reviewed 12,500 ps clock signature matches the complete initial pattern. |
| `host40` | `ambiguous` | Two distinct 25,000 ps candidates match the same pattern. |
| `amac40` | `ambiguous` | The same two candidates cannot be separated by this evidence. |
| `unmapped` | `unmapped` | The reviewed clock signatures do not match. |

The initial 33 events are examined: the first payload and 32 following intervals and level transitions. Event timestamps are strictly increasing integers and the input is bounded to 32–64 events. Matching a complete reviewed source signature is corroboration, not recovery of an embedded name or proof of identity throughout a waveform. Matching only a period, event count, or similarity score is not sufficient.

The source methodology comes from the local CERN `analysis/wdb/MAPPER.md` research record. No WDB file, HDL, simulator, or hardware is executed by this module. The synthetic traces are illustrative, not a replay of the original WDB.

## Evidence and agency

The atlas follows the covenant in the root [Declaration](../../DECLARATION.md) and [Constitution](../../CONSTITUTION.md): measurement, evidence, belief updates, and action remain distinct. Fluorescent color distinguishes channels and relationships; it is not a biological, medical, or security interpretation.

The atlas does not monitor a sector, contact CISA or CERN, control a device, or launch an analyzer. It is a visual way to inspect public concepts and an evidence rule.

## Verification

```bash
PYTHONPATH=guiai-lab python -m unittest stress.resilience_stress -v
```

Tests cover every sector and URL, dependency validity, all three signature outcomes, invalid traces, source and VDI geometry, no-overwrite exports, and actual native sector/trace changes.
