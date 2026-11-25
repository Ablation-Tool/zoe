"""Google DeepMind Science Bridge for Zoe Milestone 1 & Shared Reasoning.

Integrates Google DeepMind's open scientific platforms cleanly into Zoe with
strict ``CONSTITUTION.md`` epistemic boundaries:
  1. AlphaFold Protein Structure Database v6 REST API (zero API key)
  2. AlphaMissense genome-wide amino-acid substitution pathogenicity CSV analyzer
  3. AlphaFold 3 Server JSON complex job builder (protein + ligand / DNA / RNA)
  4. AlphaGenome 1-Mbp regulatory variant locus planner & SDK readiness adapter
  5. TxGemma / MedGemma / Gemma 4 TDC prompt builders & open-weight catalog
  6. Digital Research GEM VDI Spatial IR visualization scene builder

Constitutional Invariants (always enforced):
  measurement != evidence != belief update != action
  external_actions = 0 · sentience_claimed = False · l5_agi_qualified = False
  clinical_action_authorized = False · cure_claim = False
  wet_lab_validation_required = True
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
import urllib.request

DEEPMIND_SCIENCE_CONTRACT = "zoe-deepmind-science/v1"
ALPHAFOLD_API_BASE = "https://alphafold.ebi.ac.uk/api/prediction"
USER_AGENT = "Zoe-DeepMind-Science-Bridge/1.0 (Preclinical Research; Non-Clinical)"

CONSTITUTIONAL_FLAGS: dict[str, Any] = {
    "measurement_only": True,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "zoe_clone_claimed": False,
    "external_actions": 0,
    "wet_lab_validation_required": True,
    "attribution": "Nicholas Michael Kloster, March 6, 2026; Google DeepMind AlphaFold/AlphaMissense",
}


@dataclass(frozen=True)
class GliomaTargetSpec:
    """Curated preclinical H3K27M DMG / GBM protein target specification."""

    gene: str
    uniprot: str
    role: str
    canonical_variants: tuple[str, ...]
    hg38_locus: str
    offline_baseline_plddt: float
    offline_seq_len: int
    reference_note: str


# Curated Zoe Milestone 1 H3K27M DMG / GBM target panel (UniProt canonical accessions)
GLIOMA_TARGET_PANEL: tuple[GliomaTargetSpec, ...] = (
    GliomaTargetSpec(
        gene="H3-3A",
        uniprot="P84243",
        role="Histone H3.3 — canonical H3K27M (K28M in UniProt numbering) epigenetic driver in pediatric DMG",
        canonical_variants=("K28M", "G35R", "G35V"),
        hg38_locus="chr1:226061851-226072019",
        offline_baseline_plddt=85.94,
        offline_seq_len=136,
        reference_note="UniProt includes initiator Met1, so mature H3K27M corresponds to K28M.",
    ),
    GliomaTargetSpec(
        gene="CLPP",
        uniprot="Q16740",
        role="Mitochondrial ClpP protease — direct allosteric agonist target of ONC201 (dordaviprone) in H3K27M DMG",
        canonical_variants=("D190A", "Y118A", "S153A"),
        hg38_locus="chr19:6361293-6369671",
        offline_baseline_plddt=82.31,
        offline_seq_len=277,
        reference_note="ONC201/imipridone binding activates ClpP proteolysis in preclinical DMG models.",
    ),
    GliomaTargetSpec(
        gene="EZH2",
        uniprot="Q15910",
        role="PRC2 catalytic H3K27 methyltransferase — functionally inhibited by H3K27M oncohistone",
        canonical_variants=("Y641N", "A677G", "A687V"),
        hg38_locus="chr7:148807384-148884312",
        offline_baseline_plddt=76.25,
        offline_seq_len=746,
        reference_note="Global H3K27me3 loss in DMG links directly to PRC2/EZH2 sequestration (Q15910-1 numbering).",
    ),
    GliomaTargetSpec(
        gene="ACVR1",
        uniprot="Q04771",
        role="ALK2 BMP type-I receptor kinase — recurrent somatic activating driver in pediatric DIPG/DMG",
        canonical_variants=("R206H", "G328V", "G328E"),
        hg38_locus="chr2:157736251-157876330",
        offline_baseline_plddt=81.50,
        offline_seq_len=509,
        reference_note="Co-occurs frequently with H3.1K27M (HIST1H3B) in pontine glioma cohorts.",
    ),
    GliomaTargetSpec(
        gene="DRD2",
        uniprot="P14416",
        role="Dopamine D2 GPCR — secondary antagonism axis investigated alongside ClpP in imipridone research",
        canonical_variants=("S311C", "P310S"),
        hg38_locus="chr11:113409595-113475398",
        offline_baseline_plddt=76.20,
        offline_seq_len=443,
        reference_note="Investigated alongside ClpP activation in glioma preclinical pharmacology.",
    ),
    GliomaTargetSpec(
        gene="EGFR",
        uniprot="P00533",
        role="EGF receptor tyrosine kinase — recurrent ectodomain missense & amplification target in adult GBM",
        canonical_variants=("A289V", "G598V", "R108K"),
        hg38_locus="chr7:55019017-55211628",
        offline_baseline_plddt=80.10,
        offline_seq_len=1210,
        reference_note="Extracellular domain missense variants alter receptor dimerization in GBM.",
    ),
    GliomaTargetSpec(
        gene="IDH1",
        uniprot="O75874",
        role="Cytosolic isocitrate dehydrogenase — canonical R132H neomorphic 2-HG driver in diffuse glioma",
        canonical_variants=("R132H", "R132C", "R132G"),
        hg38_locus="chr2:208236227-208266074",
        offline_baseline_plddt=95.60,
        offline_seq_len=414,
        reference_note="R132H active-site substitution redirects catalysis toward D-2-hydroxyglutarate.",
    ),
    GliomaTargetSpec(
        gene="TP53",
        uniprot="P04637",
        role="p53 tumor suppressor — high-frequency DNA-binding domain hotspot mutations in H3K27M DMG & GBM",
        canonical_variants=("R175H", "R248W", "R273H"),
        hg38_locus="chr17:7661779-7687550",
        offline_baseline_plddt=75.10,
        offline_seq_len=393,
        reference_note="DNA-binding domain hotspots frequently co-occur with H3.3K27M.",
    ),
)

_PANEL_BY_KEY: dict[str, GliomaTargetSpec] = {}
for _spec in GLIOMA_TARGET_PANEL:
    _PANEL_BY_KEY[_spec.gene.upper()] = _spec
    _PANEL_BY_KEY[_spec.uniprot.upper()] = _spec


@dataclass
class AlphaMissenseVariantScore:
    """Single amino-acid substitution score from Google DeepMind AlphaMissense."""

    protein_variant: str
    am_pathogenicity: float
    am_class: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AlphaMissenseSummary:
    """Aggregated gene-level AlphaMissense pathogenicity statistics."""

    source: str
    total_variants: int
    lpath_count: int
    amb_count: int
    lben_count: int
    lpath_fraction: float
    mean_pathogenicity: float
    canonical_variants: list[AlphaMissenseVariantScore] = field(default_factory=list)
    top_hotspots: list[AlphaMissenseVariantScore] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "total_variants": self.total_variants,
            "lpath_count": self.lpath_count,
            "amb_count": self.amb_count,
            "lben_count": self.lben_count,
            "lpath_fraction": round(self.lpath_fraction, 4),
            "mean_pathogenicity": round(self.mean_pathogenicity, 4),
            "canonical_variants": [v.to_dict() for v in self.canonical_variants],
            "top_hotspots": [v.to_dict() for v in self.top_hotspots],
        }


@dataclass
class AlphaFoldTargetReport:
    """Structured AlphaFold DB v6 + AlphaMissense evidence packet for one protein target."""

    contract: str
    gene: str
    uniprot: str
    entry_id: str
    description: str
    role: str
    source_mode: str  # "live_alphafold_v6" | "cache" | "offline_baseline"
    global_plddt: float
    sequence_length: int
    fraction_plddt_very_high: float
    fraction_plddt_confident: float
    pdb_url: str
    cif_url: str
    am_annotations_url: str
    alphamissense: AlphaMissenseSummary
    receipt_sha256: str
    constitutional: dict[str, Any] = field(default_factory=lambda: dict(CONSTITUTIONAL_FLAGS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "gene": self.gene,
            "uniprot": self.uniprot,
            "entry_id": self.entry_id,
            "description": self.description,
            "role": self.role,
            "source_mode": self.source_mode,
            "global_plddt": round(self.global_plddt, 2),
            "sequence_length": self.sequence_length,
            "fraction_plddt_very_high": round(self.fraction_plddt_very_high, 4),
            "fraction_plddt_confident": round(self.fraction_plddt_confident, 4),
            "pdb_url": self.pdb_url,
            "cif_url": self.cif_url,
            "am_annotations_url": self.am_annotations_url,
            "alphamissense": self.alphamissense.to_dict(),
            "receipt_sha256": self.receipt_sha256,
            "constitutional": dict(self.constitutional),
        }


def resolve_glioma_target(query: str) -> GliomaTargetSpec | None:
    """Look up a curated Milestone 1 target by gene symbol or UniProt accession."""
    key = (query or "").strip().upper()
    if key in _PANEL_BY_KEY:
        return _PANEL_BY_KEY[key]
    if key == "H3F3A":
        return _PANEL_BY_KEY["H3-3A"]
    return None


def parse_alphamissense_csv(
    csv_text: str,
    *,
    canonical_variants: Sequence[str] = (),
    top_k: int = 5,
    source: str = "live_alphamissense_csv",
) -> AlphaMissenseSummary:
    """Parse Google DeepMind AlphaMissense CSV text into gene-level and canonical variant stats."""
    wanted = {v.strip().upper(): v.strip().upper() for v in canonical_variants if v.strip()}
    reader = csv.DictReader(io.StringIO(csv_text))
    total = 0
    lpath = 0
    amb = 0
    lben = 0
    score_sum = 0.0
    found_canonical: dict[str, AlphaMissenseVariantScore] = {}
    top_buf: list[AlphaMissenseVariantScore] = []

    for row in reader:
        var = (row.get("protein_variant") or "").strip().upper()
        cls = (row.get("am_class") or "").strip()
        raw_score = row.get("am_pathogenicity")
        if not var or raw_score is None:
            continue
        try:
            score = float(raw_score)
        except ValueError:
            continue
        total += 1
        score_sum += score
        cls_low = cls.lower()
        if "path" in cls_low:
            lpath += 1
        elif "ben" in cls_low:
            lben += 1
        else:
            amb += 1

        if var in wanted:
            found_canonical[var] = AlphaMissenseVariantScore(var, round(score, 4), cls)

        if len(top_buf) < top_k:
            top_buf.append(AlphaMissenseVariantScore(var, round(score, 4), cls))
            top_buf.sort(key=lambda item: item.am_pathogenicity, reverse=True)
        elif score > top_buf[-1].am_pathogenicity:
            top_buf[-1] = AlphaMissenseVariantScore(var, round(score, 4), cls)
            top_buf.sort(key=lambda item: item.am_pathogenicity, reverse=True)

    ordered_canonical = [found_canonical[v] for v in canonical_variants if v.upper() in found_canonical]
    return AlphaMissenseSummary(
        source=source,
        total_variants=total,
        lpath_count=lpath,
        amb_count=amb,
        lben_count=lben,
        lpath_fraction=(lpath / total) if total else 0.0,
        mean_pathogenicity=(score_sum / total) if total else 0.0,
        canonical_variants=ordered_canonical,
        top_hotspots=top_buf,
    )


def _seal_receipt(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class AlphaFoldDeepMindClient:
    """Pure-stdlib client for Google DeepMind AlphaFold DB v6 & AlphaMissense CSV."""

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        offline_only: bool = False,
        timeout_sec: float = 20.0,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.offline_only = bool(offline_only)
        self.timeout_sec = float(timeout_sec)

    def _http_get_text(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            return resp.read().decode("utf-8")

    def _cache_path(self, uniprot: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"af_{uniprot.upper()}.json"

    def _offline_report(self, spec: GliomaTargetSpec) -> AlphaFoldTargetReport:
        am = AlphaMissenseSummary(
            source="offline_baseline_no_network",
            total_variants=0,
            lpath_count=0,
            amb_count=0,
            lben_count=0,
            lpath_fraction=0.0,
            mean_pathogenicity=0.0,
            canonical_variants=[],
            top_hotspots=[],
        )
        base_doc = {
            "gene": spec.gene,
            "uniprot": spec.uniprot,
            "entry_id": f"AF-{spec.uniprot}-F1",
            "global_plddt": spec.offline_baseline_plddt,
            "source_mode": "offline_baseline",
        }
        return AlphaFoldTargetReport(
            contract=DEEPMIND_SCIENCE_CONTRACT,
            gene=spec.gene,
            uniprot=spec.uniprot,
            entry_id=f"AF-{spec.uniprot}-F1",
            description=spec.role,
            role=spec.role,
            source_mode="offline_baseline",
            global_plddt=spec.offline_baseline_plddt,
            sequence_length=spec.offline_seq_len,
            fraction_plddt_very_high=0.0,
            fraction_plddt_confident=0.0,
            pdb_url=f"https://alphafold.ebi.ac.uk/files/AF-{spec.uniprot}-F1-model_v6.pdb",
            cif_url=f"https://alphafold.ebi.ac.uk/files/AF-{spec.uniprot}-F1-model_v6.cif",
            am_annotations_url=f"https://alphafold.ebi.ac.uk/files/AF-{spec.uniprot}-F1-aa-substitutions.csv",
            alphamissense=am,
            receipt_sha256=_seal_receipt(base_doc),
        )

    def fetch_target(
        self,
        gene_or_uniprot: str,
        *,
        include_alphamissense: bool = True,
        use_cache: bool = True,
    ) -> AlphaFoldTargetReport:
        """Fetch live AlphaFold v6 metadata + AlphaMissense substitution stats for a target."""
        spec = resolve_glioma_target(gene_or_uniprot)
        uniprot = spec.uniprot if spec else gene_or_uniprot.strip().upper()
        if not uniprot:
            raise ValueError("gene_or_uniprot must not be empty")

        cpath = self._cache_path(uniprot)
        if use_cache and cpath is not None and cpath.is_file():
            cached = json.loads(cpath.read_text(encoding="utf-8"))
            am_raw = cached["alphamissense"]
            am = AlphaMissenseSummary(
                source=am_raw["source"],
                total_variants=int(am_raw["total_variants"]),
                lpath_count=int(am_raw["lpath_count"]),
                amb_count=int(am_raw["amb_count"]),
                lben_count=int(am_raw["lben_count"]),
                lpath_fraction=float(am_raw["lpath_fraction"]),
                mean_pathogenicity=float(am_raw["mean_pathogenicity"]),
                canonical_variants=[
                    AlphaMissenseVariantScore(**v) for v in am_raw.get("canonical_variants", [])
                ],
                top_hotspots=[
                    AlphaMissenseVariantScore(**v) for v in am_raw.get("top_hotspots", [])
                ],
            )
            return AlphaFoldTargetReport(
                contract=cached["contract"],
                gene=cached["gene"],
                uniprot=cached["uniprot"],
                entry_id=cached["entry_id"],
                description=cached["description"],
                role=cached["role"],
                source_mode="cache",
                global_plddt=float(cached["global_plddt"]),
                sequence_length=int(cached["sequence_length"]),
                fraction_plddt_very_high=float(cached["fraction_plddt_very_high"]),
                fraction_plddt_confident=float(cached["fraction_plddt_confident"]),
                pdb_url=cached["pdb_url"],
                cif_url=cached["cif_url"],
                am_annotations_url=cached["am_annotations_url"],
                alphamissense=am,
                receipt_sha256=cached["receipt_sha256"],
                constitutional=dict(cached.get("constitutional", CONSTITUTIONAL_FLAGS)),
            )

        if self.offline_only:
            if spec is None:
                spec = GliomaTargetSpec(
                    gene=uniprot,
                    uniprot=uniprot,
                    role="Custom UniProt target (offline baseline)",
                    canonical_variants=(),
                    hg38_locus="unknown",
                    offline_baseline_plddt=0.0,
                    offline_seq_len=0,
                    reference_note="Offline baseline placeholder.",
                )
            return self._offline_report(spec)

        raw_json = self._http_get_text(f"{ALPHAFOLD_API_BASE}/{uniprot}")
        entries = json.loads(raw_json)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"No AlphaFold DB prediction found for {uniprot!r}")
        entry = entries[0]

        am_url = str(entry.get("amAnnotationsUrl") or "")
        canonical_vars = spec.canonical_variants if spec else ()
        if include_alphamissense and am_url:
            csv_text = self._http_get_text(am_url)
            am_summary = parse_alphamissense_csv(
                csv_text,
                canonical_variants=canonical_vars,
                source="live_alphamissense_v6",
            )
        else:
            am_summary = AlphaMissenseSummary(
                source="skipped",
                total_variants=0,
                lpath_count=0,
                amb_count=0,
                lben_count=0,
                lpath_fraction=0.0,
                mean_pathogenicity=0.0,
            )

        body: dict[str, Any] = {
            "contract": DEEPMIND_SCIENCE_CONTRACT,
            "gene": str(entry.get("gene") or (spec.gene if spec else uniprot)),
            "uniprot": str(entry.get("uniprotAccession") or uniprot),
            "entry_id": str(entry.get("entryId") or f"AF-{uniprot}-F1"),
            "description": str(entry.get("uniprotDescription") or (spec.role if spec else "")),
            "role": spec.role if spec else str(entry.get("uniprotDescription") or ""),
            "source_mode": "live_alphafold_v6",
            "global_plddt": float(entry.get("globalMetricValue") or 0.0),
            "sequence_length": int(entry.get("sequenceEnd") or 0),
            "fraction_plddt_very_high": float(entry.get("fractionPlddtVeryHigh") or 0.0),
            "fraction_plddt_confident": float(entry.get("fractionPlddtConfident") or 0.0),
            "pdb_url": str(entry.get("pdbUrl") or ""),
            "cif_url": str(entry.get("cifUrl") or ""),
            "am_annotations_url": am_url,
            "alphamissense": am_summary.to_dict(),
        }
        receipt = _seal_receipt(body)
        report = AlphaFoldTargetReport(
            contract=body["contract"],
            gene=body["gene"],
            uniprot=body["uniprot"],
            entry_id=body["entry_id"],
            description=body["description"],
            role=body["role"],
            source_mode=body["source_mode"],
            global_plddt=body["global_plddt"],
            sequence_length=body["sequence_length"],
            fraction_plddt_very_high=body["fraction_plddt_very_high"],
            fraction_plddt_confident=body["fraction_plddt_confident"],
            pdb_url=body["pdb_url"],
            cif_url=body["cif_url"],
            am_annotations_url=body["am_annotations_url"],
            alphamissense=am_summary,
            receipt_sha256=receipt,
        )
        if cpath is not None:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report

    def fetch_glioma_panel(
        self,
        *,
        genes: Sequence[str] | None = None,
        include_alphamissense: bool = True,
    ) -> list[AlphaFoldTargetReport]:
        """Fetch AlphaFold v6 + AlphaMissense reports for all (or selected) Milestone 1 glioma targets."""
        targets = list(genes) if genes is not None else [s.gene for s in GLIOMA_TARGET_PANEL]
        return [self.fetch_target(g, include_alphamissense=include_alphamissense) for g in targets]


def build_alphafold3_job(
    job_name: str,
    *,
    protein_sequences: Sequence[tuple[str, int]],
    ligand_ccd_codes: Sequence[str] = (),
    dna_sequences: Sequence[str] = (),
    rna_sequences: Sequence[str] = (),
    model_seeds: Sequence[int] = (2026,),
) -> dict[str, Any]:
    """Generate a schema-valid Google DeepMind AlphaFold 3 Server JSON job payload.

    Produces a local JSON document ready for manual upload to alphafoldserver.com
    (strictly ``external_actions = 0``; no automatic remote submission).
    """
    clean_name = "".join(ch if ch.isalnum() or ch in ("_", "-", " ") else "_" for ch in (job_name or "zoe_af3_job")).strip()
    if not clean_name:
        raise ValueError("job_name must not be empty")
    if not protein_sequences:
        raise ValueError("At least one (sequence, count) protein chain is required")

    sequences_block: list[dict[str, Any]] = []
    for seq, count in protein_sequences:
        clean_seq = "".join(ch for ch in seq.upper() if ch.isalpha())
        if len(clean_seq) < 10:
            raise ValueError("Protein sequence must contain at least 10 amino acid residues")
        if count < 1 or count > 20:
            raise ValueError(f"Protein copy count must be in 1..20, got {count}")
        sequences_block.append({"proteinChain": {"sequence": clean_seq, "count": int(count)}})

    for ccd in ligand_ccd_codes:
        code = ccd.strip().upper()
        if code:
            sequences_block.append({"ligand": {"ligand": f"CCD_{code}", "count": 1}})

    for dna in dna_sequences:
        clean_dna = "".join(ch for ch in dna.upper() if ch in "ACGT")
        if clean_dna:
            sequences_block.append({"dnaSequence": {"sequence": clean_dna, "count": 1}})

    for rna in rna_sequences:
        clean_rna = "".join(ch for ch in rna.upper() if ch in "ACGU")
        if clean_rna:
            sequences_block.append({"rnaSequence": {"sequence": clean_rna, "count": 1}})

    job_payload: dict[str, Any] = {
        "name": clean_name,
        "modelSeeds": [int(s) for s in model_seeds] or [2026],
        "sequences": sequences_block,
        "dialect": "alphafoldserver",
        "version": 1,
    }
    return {
        "contract": "zoe-alphafold3-job/v1",
        "upload_target": "https://alphafoldserver.com",
        "af3_server_json": [job_payload],
        "receipt_sha256": _seal_receipt(job_payload),
        "constitutional": dict(CONSTITUTIONAL_FLAGS),
    }


def build_alphagenome_request(
    gene_or_locus: str,
    *,
    variant_pos: int | None = None,
    ref_base: str = "A",
    alt_base: str = "T",
    window_bp: int = 1_048_576,
    modalities: Sequence[str] = (
        "RNA_SEQ",
        "CAGE",
        "ATAC",
        "DNASE",
        "CHIP_HISTONE",
        "SPLICE_SITES",
    ),
) -> dict[str, Any]:
    """Construct a structured Google DeepMind AlphaGenome 1-Mbp regulatory query plan.

    Detects local ``alphagenome`` package and ``ALPHAGENOME_API_KEY`` readiness without
    performing any unauthorized external call.
    """
    spec = resolve_glioma_target(gene_or_locus)
    locus = spec.hg38_locus if spec else gene_or_locus.strip()
    gene_label = spec.gene if spec else gene_or_locus.strip()

    try:
        import importlib.util

        pkg_installed = importlib.util.find_spec("alphagenome") is not None
    except Exception:
        pkg_installed = False

    api_key_present = bool(os.environ.get("ALPHAGENOME_API_KEY", "").strip())

    req_doc = {
        "contract": "zoe-alphagenome-plan/v1",
        "gene": gene_label,
        "hg38_locus": locus,
        "window_bp": int(window_bp),
        "variant": (
            {"pos": int(variant_pos), "ref": ref_base.upper(), "alt": alt_base.upper()}
            if variant_pos is not None
            else None
        ),
        "modalities": list(modalities),
        "sdk_installed": pkg_installed,
        "api_key_configured": api_key_present,
        "execution_status": "ready_for_api" if (pkg_installed and api_key_present) else "offline_plan_ready",
        "setup_hint": "Install `pip install alphagenome` and set ALPHAGENOME_API_KEY (free non-commercial research key).",
        "constitutional": dict(CONSTITUTIONAL_FLAGS),
    }
    req_doc["receipt_sha256"] = _seal_receipt(req_doc)
    return req_doc


def build_txgemma_tdc_prompt(
    smiles: str,
    *,
    task: str = "BBB_Martins",
    compound_name: str = "candidate",
) -> dict[str, Any]:
    """Build a Therapeutic Data Commons (TDC) prompt formatted for Google DeepMind TxGemma."""
    clean_smiles = (smiles or "").strip()
    if not clean_smiles:
        raise ValueError("SMILES string must not be empty")

    task_specs: dict[str, tuple[str, str]] = {
        "BBB_Martins": (
            "Blood-Brain Barrier Penetration (Martins et al.)",
            "Predict whether this small molecule penetrates the blood-brain barrier (B = crosses BBB, A = does not cross BBB).",
        ),
        "ClinTox": (
            "Clinical Trial Toxicity (ClinTox)",
            "Predict whether this molecule is associated with clinical toxicity (B = toxic, A = non-toxic).",
        ),
        "hERG": (
            "hERG Cardiotoxicity Blocker Screening",
            "Predict whether this molecule blocks the hERG potassium channel (B = blocker, A = non-blocker).",
        ),
        "AMES": (
            "Ames Mutagenicity",
            "Predict whether this molecule is mutagenic in the Ames assay (B = mutagenic, A = non-mutagenic).",
        ),
    }
    if task not in task_specs:
        raise ValueError(f"Unsupported TxGemma TDC task {task!r}. Choose from: {sorted(task_specs)}")
    title, instruction = task_specs[task]

    prompt = (
        f"Instructions: Answer the following preclinical therapeutic screening question based on the SMILES string.\n"
        f"Benchmark: {title} (TDC)\n"
        f"Context: {instruction}\n"
        f"Compound: {compound_name}\n"
        f"Drug SMILES: {clean_smiles}\n"
        f"Answer: ("
    )
    doc = {
        "contract": "zoe-txgemma-tdc-prompt/v1",
        "model_family": "google/txgemma-2b-predict",
        "task": task,
        "compound_name": compound_name,
        "smiles": clean_smiles,
        "prompt": prompt,
        "constitutional": dict(CONSTITUTIONAL_FLAGS),
    }
    doc["receipt_sha256"] = _seal_receipt(doc)
    return doc


def list_deepmind_open_models() -> list[dict[str, Any]]:
    """Catalog Google DeepMind open-weight and scientific tools compatible with Zoe."""
    return [
        {
            "name": "AlphaFold DB v6 + AlphaMissense",
            "category": "Structural Biology & Variant Pathogenicity",
            "access": "Live public REST API (0 API keys)",
            "zoe_integration": "AlphaFoldDeepMindClient -> Pillar 1 H3K27M/GBM panel + GEM VDI + MCP",
            "status": "LIVE_ACTIVE",
        },
        {
            "name": "AlphaFold 3 Server",
            "category": "Biomolecular Complex Structure (Protein + Ligand/DNA/RNA)",
            "access": "JSON job upload (alphafoldserver.com, non-commercial)",
            "zoe_integration": "build_alphafold3_job() -> SHA-256 sealed AF3 JSON export (external_actions=0)",
            "status": "JOB_GENERATOR_ACTIVE",
        },
        {
            "name": "Google Antigravity SDK (0.1.24)",
            "category": "Agentic Reasoning, Hooks, LiteRT Edge, MCP & Workflows",
            "access": "Installed locally (`google-antigravity 0.1.24`)",
            "zoe_integration": "ZoeConstitutionalPreToolHook/PostToolHook/StopHook + LiteRTAgentConfig + LocalOpenAIAgentConfig",
            "status": "LIVE_ACTIVE",
        },
        {
            "name": "AlphaGenome / AlphaGenome 2",
            "category": "1-Mbp Regulatory DNA Sequence-to-Function",
            "access": "Non-commercial Research API (`alphagenome` PyPI + key)",
            "zoe_integration": "build_alphagenome_request() -> H3-3A/ACVR1/OLIG2/PDGFRA regulatory locus planner",
            "status": "ADAPTER_READY",
        },
        {
            "name": "TxGemma (2B / 9B / 27B)",
            "category": "Preclinical Therapeutics (BBB, Toxicity, Binding)",
            "access": "Open weights on Hugging Face (`google/txgemma-2b-predict`, GGUF compatible)",
            "zoe_integration": "build_txgemma_tdc_prompt() -> plugs into C27 36-compound atlas & llama-server :8080",
            "status": "PROMPT_ADAPTER_READY",
        },
        {
            "name": "MedGemma (1.5) & Gemma 4 / EmbeddingGemma 2",
            "category": "Local Medical Vision-Language, Reasoning & RAG Embeddings",
            "access": "Open weights on Hugging Face (GGUF / LiteRT .task compatible)",
            "zoe_integration": "Swap-in for llama-server :8080, LiteRTAgentConfig, and private 135-book Dorothy RAG",
            "status": "RUNTIME_READY",
        },
    ]


def build_deepmind_gem_scene(reports: Sequence[AlphaFoldTargetReport]) -> Any:
    """Compile live AlphaFold v6 + AlphaMissense target reports into a Digital Research GEM Scene."""
    from guiai.gem.model import Scene  # type: ignore

    objs: list[dict[str, Any]] = [
        # GEM AES Menu Bar (Ruby ViewMAX 3 header) — bounds are [x0, y0, x1, y1]
        {"id": "gem_menu_bg", "type": "rectangle", "bounds": [8, 8, 952, 42], "fill": "#f35670", "stroke": "#111827", "width": 2},
        {"id": "gem_menu_left", "type": "text", "position": [20, 30], "text": "Desk  AlphaFold-v6  AlphaMissense  AF3  VDI", "size": 14, "fill": "#0f172a"},
        {"id": "gem_menu_right", "type": "text", "position": [635, 30], "text": "Zoe x Google DeepMind GEM Desk", "size": 14, "fill": "#0f172a"},
    ]

    # Render up to 8 target windows in a crisp 4x2 GEM tiled desktop grid
    panel = list(reports)[:8]
    cols = 4
    win_w = 228
    win_h = 200
    gap_x = 10
    gap_y = 12
    start_x = 8
    start_y = 52

    for idx, rep in enumerate(panel):
        col = idx % cols
        row = idx // cols
        x = start_x + col * (win_w + gap_x)
        y = start_y + row * (win_h + gap_y)

        # Window frame + title bar
        objs.append({"id": f"win_{idx}", "type": "rectangle", "bounds": [x, y, x + win_w, y + win_h], "fill": "#e9edf6", "stroke": "#111827", "width": 2})
        title_fill = "#38d9f5" if rep.global_plddt >= 80.0 else "#f8cc30"
        objs.append({"id": f"wtb_{idx}", "type": "rectangle", "bounds": [x, y, x + win_w, y + 26], "fill": title_fill, "stroke": "#111827", "width": 1.5})
        objs.append({"id": f"wtt_{idx}", "type": "text", "position": [x + 8, y + 18], "text": f"{rep.gene} ({rep.uniprot})", "size": 13, "fill": "#0f172a"})

        # pLDDT horizontal bar
        objs.append({"id": f"pl_lbl_{idx}", "type": "text", "position": [x + 10, y + 48], "text": f"AF-v6 pLDDT: {rep.global_plddt:.1f}  ({rep.sequence_length} aa)", "size": 11, "fill": "#0f172a"})
        bar_w = max(8, int(round((min(100.0, max(0.0, rep.global_plddt)) / 100.0) * (win_w - 22))))
        objs.append({"id": f"pl_bg_{idx}", "type": "rectangle", "bounds": [x + 10, y + 56, x + win_w - 12, y + 68], "fill": "#cbd5e1", "stroke": "#334155", "width": 1})
        objs.append({"id": f"pl_fg_{idx}", "type": "rectangle", "bounds": [x + 10, y + 56, x + 10 + bar_w, y + 68], "fill": "#2563eb", "stroke": "#1e3a8a", "width": 1})

        # AlphaMissense pathogenic fraction bar
        lp_pct = rep.alphamissense.lpath_fraction * 100.0
        objs.append({"id": f"am_lbl_{idx}", "type": "text", "position": [x + 10, y + 90], "text": f"AlphaMissense LPath: {lp_pct:.1f}%", "size": 11, "fill": "#0f172a"})
        am_w = max(6, int(round((min(100.0, max(0.0, lp_pct)) / 100.0) * (win_w - 22))))
        objs.append({"id": f"am_bg_{idx}", "type": "rectangle", "bounds": [x + 10, y + 98, x + win_w - 12, y + 110], "fill": "#cbd5e1", "stroke": "#334155", "width": 1})
        objs.append({"id": f"am_fg_{idx}", "type": "rectangle", "bounds": [x + 10, y + 98, x + 10 + am_w, y + 110], "fill": "#e11d48", "stroke": "#881337", "width": 1})

        # Canonical glioma variants (top 2)
        if rep.alphamissense.canonical_variants:
            for vi, v in enumerate(rep.alphamissense.canonical_variants[:2]):
                objs.append({
                    "id": f"cv_{idx}_{vi}",
                    "type": "text",
                    "position": [x + 10, y + 132 + vi * 18],
                    "text": f"{v.protein_variant}: {v.am_pathogenicity:.3f} ({v.am_class})",
                    "size": 11,
                    "fill": "#1e293b",
                })
        else:
            objs.append({
                "id": f"cv_{idx}_0",
                "type": "text",
                "position": [x + 10, y + 134],
                "text": f"Mode: {rep.source_mode}",
                "size": 10.5,
                "fill": "#334155",
            })

        objs.append({
            "id": f"rc_{idx}",
            "type": "text",
            "position": [x + 10, y + 186],
            "text": f"SHA:{rep.receipt_sha256[:12]}  n={rep.alphamissense.total_variants}",
            "size": 9.5,
            "fill": "#475569",
        })

    # Constitutional ViewMAX footer
    objs.append({"id": "gem_foot_bg", "type": "rectangle", "bounds": [8, 474, 952, 504], "fill": "#45e2f2", "stroke": "#111827", "width": 2})
    objs.append({
        "id": "gem_foot_txt",
        "type": "text",
        "position": [18, 494],
        "text": "VISUAL EVIDENCE ONLY · clinical_action_authorized=False · cure_claim=False · external_actions=0 · sentience_claimed=False",
        "size": 11.5,
        "fill": "#0f172a",
    })

    scene_doc: dict[str, Any] = {
        "schema_version": 1,
        "id": "zoe-deepmind-alphafold-gem-desk",
        "title": "Zoe x Google DeepMind AlphaFold v6 & AlphaMissense GEM VDI Desk",
        "canvas": {"width": 960, "height": 512},
        "objects": objs,
    }
    return Scene.from_dict(scene_doc)


__all__ = [
    "ALPHAFOLD_API_BASE",
    "CONSTITUTIONAL_FLAGS",
    "DEEPMIND_SCIENCE_CONTRACT",
    "GLIOMA_TARGET_PANEL",
    "AlphaFoldDeepMindClient",
    "AlphaFoldTargetReport",
    "AlphaMissenseSummary",
    "AlphaMissenseVariantScore",
    "GliomaTargetSpec",
    "build_alphafold3_job",
    "build_alphagenome_request",
    "build_deepmind_gem_scene",
    "build_txgemma_tdc_prompt",
    "list_deepmind_open_models",
    "parse_alphamissense_csv",
    "resolve_glioma_target",
]
