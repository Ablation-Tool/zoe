"""EDDBMS Central Engineering Design Database & Bidirectional Domain Sister Modules (Milestone M2).

Implements the Figure 15.3 (Balma & Fitler / CAD-EDDBMS pp. 262-263) hub-and-spoke
Engineering Design Database Management System integrated with Zoe's 9-sister hexagonal
collaboration mesh (`zoe_hex_mesh.py` / `zoe_sisters.py`):
  - Feature #4: Unidirectional `FunctionEngineeringSpecification` intake feeding
    the central `EngineeringDesignDatabase`, `MATERIAL_DESIGN`, and
    `PRODUCT_DESIGN_AND_PLANNING` (plus surfacing constraints in `DESIGN_PARAMETERS`).
  - Feature #5: Central `EngineeringDesignDatabase` with `GeneralData`, `PropertyData`,
    and `GeometricData` (2D, 3D, mesh, analysis-process formats), canonical SHA-256
    revision chains from `"GENESIS"`, deep-copy snapshot isolation, and Article IV
    reversibility (`rollback_to_revision` preserving non-destructive provenance).
  - Feature #6: 6 bidirectional domain modules with all 28 canonical Figure 15.3
    sub-operations, optimistic `expected_revision` concurrency control, sequential
    right-column pipeline (`PRODUCT_DESIGN_AND_PLANNING -> PROJECT_MANAGEMENT ->
    POSTPRODUCTION_MANAGEMENT`), and deterministic 9-sister `run_sister_eddms_cycle`.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy
from dataclasses import dataclass, field
import threading
from typing import Any

from .zoe_hex_mesh import (
    ATTRIBUTION_TEXT,
    DEFAULT_SISTER_DOMAIN_MODULES,
    EDDBMS_DOMAIN_MODULES,
    HASH_CHAIN_SEMANTICS,
    ConstitutionalViolationError,
    EpistemicFirewallError,
    HexCell,
    HexCollaborationMesh,
    HexTickResult,
    TamperDetectedError,
    build_default_zoe_mesh,
    canonical_json_bytes,
    constitutional_metadata,
    sha256_canonical,
    validate_constitutional_packet,
    validate_epistemic_lane,
)
from .zoe_sisters import (
    SAFETY_INVARIANTS,
    ZOE_SISTERS,
    SisterModelSpec,
    resolve_sister,
)

EDDBMS_CONTRACT: str = "zoe-eddms/v1"

SPEC_INTAKE_TARGETS: tuple[str, ...] = (
    "ENGINEERING_DESIGN_DATABASE",
    "MATERIAL_DESIGN",
    "PRODUCT_DESIGN_AND_PLANNING",
)

EDDBMS_PIPELINE_STAGES: tuple[str, ...] = (
    "PRODUCT_DESIGN_AND_PLANNING",
    "PROJECT_MANAGEMENT",
    "POSTPRODUCTION_MANAGEMENT",
)
PIPELINE_STAGES: tuple[str, ...] = EDDBMS_PIPELINE_STAGES

VALID_PIPELINE_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT"),
        ("PROJECT_MANAGEMENT", "POSTPRODUCTION_MANAGEMENT"),
    }
)

EDDBMS_MODULE_SUBOPERATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "MATERIAL_DESIGN": (
        ("geometric_modeling", "1) Geometric modeling"),
        ("design_analysis", "2) Design analysis"),
        ("design_animation", "3) Design animation"),
        ("design_optimization", "4) Design optimization"),
        ("shaping_methods", "5) Shaping methods"),
        ("data_process", "6) Data process"),
    ),
    "HUMAN_MODEL": (
        ("shape_data", "1) Shape data"),
        ("physiological", "2) Physiological"),
        ("physical", "3) Physical"),
        ("psychological", "4) Psychological"),
    ),
    "DESIGN_PARAMETERS": (
        ("environment", "1) Environment"),
        ("restriction_condition", "2) Restriction condition"),
    ),
    "PRODUCT_DESIGN_AND_PLANNING": (
        ("drawing_of_product", "1) Drawing of product"),
        ("inventory_of_materials", "2) Inventory of materials"),
        ("function_design", "3) Function design"),
        ("wearing_requirement", "4) Wearing requirement"),
        ("cost_analysis", "5) Cost analysis"),
    ),
    "PROJECT_MANAGEMENT": (
        ("design_requirement", "1) Design requirement"),
        ("process_design_and_control", "2) Process design & control"),
        ("pre_process", "3) Pre-process"),
        ("solver", "4) Solver"),
        ("post_process", "5) Post-process"),
        ("built_design_result", "6) Built design result"),
    ),
    "POSTPRODUCTION_MANAGEMENT": (
        ("analysis", "1) Analysis"),
        ("evaluation", "2) Evaluation"),
        ("visualization", "3) Visualization"),
        ("optimization", "4) Optimization"),
        ("application_information", "5) Application information"),
    ),
}

EDDBMS_SUBOPERATION_KEYS: dict[str, tuple[str, ...]] = {
    mod: tuple(key for key, _label in ops)
    for mod, ops in EDDBMS_MODULE_SUBOPERATIONS.items()
}

_ALLOWED_PATCH_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "general",
        "properties",
        "geometric",
        "sub_operations",
        "module_data",
        "notes",
        "epistemic_lane",
    }
)
_DATA_PATCH_SECTION_KEYS: frozenset[str] = frozenset(
    {"general", "properties", "geometric", "sub_operations", "module_data"}
)
_ALLOWED_GENERAL_KEYS: frozenset[str] = frozenset(
    {"design_id", "product_id", "owner_metadata", "special_instructions", "commerce_info"}
)
_ALLOWED_PROPERTY_KEYS: frozenset[str] = frozenset(
    {"structure_desc", "mechanical_desc", "physical_desc"}
)
_ALLOWED_GEOMETRIC_KEYS: frozenset[str] = frozenset(
    {"geom_2d", "geom_3d", "mesh_data", "analysis_process_formats"}
)

_MECHANICAL_KEY_HINTS: tuple[str, ...] = (
    "tensile",
    "yield",
    "modulus",
    "rigidity",
    "shear",
    "hardness",
    "fatigue",
    "mpa",
    "gpa",
)
_PHYSICAL_KEY_HINTS: tuple[str, ...] = (
    "thermal",
    "density",
    "mass",
    "sorption",
    "temp",
    "watt",
    "power",
    "conductivity",
)
_GEOM3D_KEY_HINTS: tuple[str, ...] = ("bound", "3d", "envelope")
_MESH_KEY_HINTS: tuple[str, ...] = ("mesh", "node", "element")

_TRUTHY_EXECUTION_STRINGS: frozenset[str] = frozenset({"true", "1", "yes", "on"})


class EddmsValidationError(ConstitutionalViolationError):
    """Raised when EDDBMS schema, module, or constitutional validation fails."""


class RevisionConflictError(ValueError):
    """Raised on stale expected_revision or duplicate spec_id/design_id ingest."""


EddmsConflictError = RevisionConflictError


class PipelineOrderError(ValueError):
    """Raised when right-column pipeline stage transition violates sequential order."""


EddmsPipelineError = PipelineOrderError


class UnknownDesignError(KeyError, ValueError):
    """Raised when a design_id or revision cannot be found in EngineeringDesignDatabase."""


EddmsRecordNotFoundError = UnknownDesignError


def _require_non_empty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EddmsValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _require_non_bool_int(value: Any, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EddmsValidationError(
            f"{label} must be a non-bool integer, got {value!r}"
        )
    if value < minimum:
        raise EddmsValidationError(
            f"{label} must be >= {minimum}, got {value!r}"
        )
    return value


def _is_truthy_execution_flag(val: Any) -> bool:
    if val is True:
        return True
    if isinstance(val, bool):
        return False
    if isinstance(val, (int, float)) and val == 1:
        return True
    if isinstance(val, str) and val.strip().lower() in _TRUTHY_EXECUTION_STRINGS:
        return True
    return False


def _enforce_no_truthy_execute(node: Any, *, path: str = "packet") -> None:
    if isinstance(node, list):
        for idx, item in enumerate(node):
            _enforce_no_truthy_execute(item, path=f"{path}[{idx}]")
        return
    if not isinstance(node, dict):
        return
    for flag_key in ("execute", "auto_execute"):
        if flag_key in node and _is_truthy_execution_flag(node[flag_key]):
            raise EpistemicFirewallError(
                f"{path}.{flag_key} attempted autonomous execution override ({node[flag_key]!r})"
            )
    for k, child in node.items():
        _enforce_no_truthy_execute(child, path=f"{path}.{k}")


def _validate_eddms_packet(
    packet: Mapping[str, Any],
    *,
    label: str = "packet",
    epistemic_lane: str | None = None,
    require_metadata: bool = False,
) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        raise EddmsValidationError(
            f"{label} must be a Mapping, got {type(packet).__name__}"
        )
    normalized = validate_constitutional_packet(
        packet,
        epistemic_lane=epistemic_lane,
        require_metadata=require_metadata,
    )
    _enforce_no_truthy_execute(normalized, path=label)
    return normalized


def _normalize_module_name(module_name: str) -> str:
    if not isinstance(module_name, str) or not module_name.strip():
        raise EddmsValidationError("module_name must be a non-empty string")
    norm = module_name.strip().upper()
    if norm not in EDDBMS_DOMAIN_MODULES:
        valid = ", ".join(EDDBMS_DOMAIN_MODULES)
        raise EddmsValidationError(
            f"Unknown EDDBMS domain module {module_name!r}; expected one of: {valid}"
        )
    return norm


def _deep_merge_dict(target: dict[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-merged copy without mutating inputs."""
    out = copy.deepcopy(target)
    for k, v in updates.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)
        else:
            out[k] = copy.deepcopy(dict(v) if isinstance(v, Mapping) else v)
    return out


def list_module_suboperations(module_name: str) -> tuple[tuple[str, str], ...]:
    """Return canonical Figure 15.3 (key, label) sub-operations for a domain module."""
    norm = _normalize_module_name(module_name)
    return EDDBMS_MODULE_SUBOPERATIONS[norm]


@dataclass(frozen=True)
class FunctionEngineeringSpecification:
    """Unidirectional Figure 15.3 Function Engineering Specification intake schema."""

    spec_id: str
    title: str
    objective: str
    owner: str
    constraints: dict[str, Any]
    target_properties: dict[str, Any]
    geometric_requirements: dict[str, Any]
    special_instructions: str = ""

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate and normalize all specification fields (safe against post-init dict mutation)."""
        clean_spec_id = _require_non_empty_str(
            self.spec_id, "FunctionEngineeringSpecification.spec_id"
        )
        clean_title = _require_non_empty_str(
            self.title, "FunctionEngineeringSpecification.title"
        )
        clean_objective = _require_non_empty_str(
            self.objective, "FunctionEngineeringSpecification.objective"
        )
        clean_owner = _require_non_empty_str(
            self.owner, "FunctionEngineeringSpecification.owner"
        )
        if not isinstance(self.special_instructions, str):
            raise EddmsValidationError(
                "FunctionEngineeringSpecification.special_instructions must be a string"
            )
        clean_constraints = _validate_eddms_packet(
            self.constraints,
            label="FunctionEngineeringSpecification.constraints",
            epistemic_lane="measurement",
        )
        clean_props = _validate_eddms_packet(
            self.target_properties,
            label="FunctionEngineeringSpecification.target_properties",
            epistemic_lane="measurement",
        )
        clean_geom = _validate_eddms_packet(
            self.geometric_requirements,
            label="FunctionEngineeringSpecification.geometric_requirements",
            epistemic_lane="measurement",
        )
        object.__setattr__(self, "spec_id", clean_spec_id)
        object.__setattr__(self, "title", clean_title)
        object.__setattr__(self, "objective", clean_objective)
        object.__setattr__(self, "owner", clean_owner)
        object.__setattr__(self, "constraints", clean_constraints)
        object.__setattr__(self, "target_properties", clean_props)
        object.__setattr__(self, "geometric_requirements", clean_geom)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "title": self.title,
            "objective": self.objective,
            "owner": self.owner,
            "constraints": copy.deepcopy(self.constraints),
            "target_properties": copy.deepcopy(self.target_properties),
            "geometric_requirements": copy.deepcopy(self.geometric_requirements),
            "special_instructions": self.special_instructions,
        }

    def compute_sha256(self) -> str:
        return sha256_canonical(
            {
                "contract": EDDBMS_CONTRACT,
                "schema": "FunctionEngineeringSpecification",
                **self.to_dict(),
            }
        )


@dataclass
class GeneralData:
    """Figure 15.3 (p. 263) General data category."""

    design_id: str
    product_id: str
    owner_metadata: dict[str, Any]
    special_instructions: str
    commerce_info: dict[str, Any]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.design_id = _require_non_empty_str(self.design_id, "GeneralData.design_id")
        self.product_id = _require_non_empty_str(self.product_id, "GeneralData.product_id")
        if not isinstance(self.special_instructions, str):
            raise EddmsValidationError("GeneralData.special_instructions must be a string")
        self.owner_metadata = _validate_eddms_packet(
            self.owner_metadata, label="GeneralData.owner_metadata"
        )
        self.commerce_info = _validate_eddms_packet(
            self.commerce_info, label="GeneralData.commerce_info"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_id": self.design_id,
            "product_id": self.product_id,
            "owner_metadata": copy.deepcopy(self.owner_metadata),
            "special_instructions": self.special_instructions,
            "commerce_info": copy.deepcopy(self.commerce_info),
        }


@dataclass
class PropertyData:
    """Figure 15.3 (p. 263) Property data category (macro/micro, mechanical, physical)."""

    structure_desc: dict[str, Any] = field(default_factory=dict)
    mechanical_desc: dict[str, Any] = field(default_factory=dict)
    physical_desc: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.structure_desc = _validate_eddms_packet(
            self.structure_desc, label="PropertyData.structure_desc"
        )
        self.mechanical_desc = _validate_eddms_packet(
            self.mechanical_desc, label="PropertyData.mechanical_desc"
        )
        self.physical_desc = _validate_eddms_packet(
            self.physical_desc, label="PropertyData.physical_desc"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "structure_desc": copy.deepcopy(self.structure_desc),
            "mechanical_desc": copy.deepcopy(self.mechanical_desc),
            "physical_desc": copy.deepcopy(self.physical_desc),
        }


@dataclass
class GeometricData:
    """Figure 15.3 (p. 263) Geometric data category (2D, 3D, mesh, analysis-process formats)."""

    geom_2d: dict[str, Any] = field(default_factory=dict)
    geom_3d: dict[str, Any] = field(default_factory=dict)
    mesh_data: dict[str, Any] = field(default_factory=dict)
    analysis_process_formats: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.geom_2d = _validate_eddms_packet(self.geom_2d, label="GeometricData.geom_2d")
        self.geom_3d = _validate_eddms_packet(self.geom_3d, label="GeometricData.geom_3d")
        self.mesh_data = _validate_eddms_packet(
            self.mesh_data, label="GeometricData.mesh_data"
        )
        self.analysis_process_formats = _validate_eddms_packet(
            self.analysis_process_formats,
            label="GeometricData.analysis_process_formats",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "geom_2d": copy.deepcopy(self.geom_2d),
            "geom_3d": copy.deepcopy(self.geom_3d),
            "mesh_data": copy.deepcopy(self.mesh_data),
            "analysis_process_formats": copy.deepcopy(self.analysis_process_formats),
        }


@dataclass
class EngineeringDesignRecord:
    """Revisioned central EDDBMS record with tamper-evident SHA-256 hash chain."""

    general: GeneralData
    properties: PropertyData
    geometric: GeometricData
    revision: int
    spec_id: str
    provenance_log: list[dict[str, Any]]
    record_sha256: str = ""
    prev_record_sha256: str = "GENESIS"
    pipeline_stage: str = "PRODUCT_DESIGN_AND_PLANNING"
    safety_invariants: dict[str, Any] = field(
        default_factory=lambda: constitutional_metadata("measurement", read_only=False)
    )

    def __post_init__(self) -> None:
        if not isinstance(self.general, GeneralData):
            raise EddmsValidationError("EngineeringDesignRecord.general must be GeneralData")
        if not isinstance(self.properties, PropertyData):
            raise EddmsValidationError(
                "EngineeringDesignRecord.properties must be PropertyData"
            )
        if not isinstance(self.geometric, GeometricData):
            raise EddmsValidationError(
                "EngineeringDesignRecord.geometric must be GeometricData"
            )
        _require_non_bool_int(self.revision, "EngineeringDesignRecord.revision", minimum=1)
        self.spec_id = _require_non_empty_str(
            self.spec_id, "EngineeringDesignRecord.spec_id"
        )
        if self.pipeline_stage not in EDDBMS_PIPELINE_STAGES:
            raise EddmsValidationError(
                f"Invalid pipeline_stage {self.pipeline_stage!r}"
            )
        if not isinstance(self.prev_record_sha256, str) or not self.prev_record_sha256:
            raise EddmsValidationError(
                "EngineeringDesignRecord.prev_record_sha256 must be non-empty str"
            )
        if not isinstance(self.provenance_log, list):
            raise EddmsValidationError(
                "EngineeringDesignRecord.provenance_log must be a list"
            )
        normalized_log: list[dict[str, Any]] = []
        for idx, entry in enumerate(self.provenance_log):
            normalized_log.append(
                _validate_eddms_packet(entry, label=f"provenance_log[{idx}]")
            )
        self.provenance_log = normalized_log
        self.safety_invariants = _validate_eddms_packet(
            self.safety_invariants,
            label="EngineeringDesignRecord.safety_invariants",
            require_metadata=True,
        )
        if not isinstance(self.record_sha256, str):
            raise EddmsValidationError("EngineeringDesignRecord.record_sha256 must be str")
        if self.record_sha256 == "":
            self.record_sha256 = self.compute_sha256()

    def _validate_contents(self) -> None:
        self.general.validate()
        self.properties.validate()
        self.geometric.validate()
        _require_non_bool_int(self.revision, "EngineeringDesignRecord.revision", minimum=1)
        _require_non_empty_str(self.spec_id, "EngineeringDesignRecord.spec_id")
        if self.pipeline_stage not in EDDBMS_PIPELINE_STAGES:
            raise EddmsValidationError(f"Invalid pipeline_stage {self.pipeline_stage!r}")
        for idx, entry in enumerate(self.provenance_log):
            _validate_eddms_packet(entry, label=f"provenance_log[{idx}]")
        _validate_eddms_packet(
            self.safety_invariants,
            label="EngineeringDesignRecord.safety_invariants",
            require_metadata=True,
        )

    def compute_sha256(self) -> str:
        preimage: dict[str, Any] = {
            "contract": EDDBMS_CONTRACT,
            "spec_id": self.spec_id,
            "design_id": self.general.design_id,
            "revision": self.revision,
            "prev_record_sha256": self.prev_record_sha256,
            "pipeline_stage": self.pipeline_stage,
            "general": self.general.to_dict(),
            "properties": self.properties.to_dict(),
            "geometric": self.geometric.to_dict(),
            "provenance_log": copy.deepcopy(self.provenance_log),
            "safety_invariants": copy.deepcopy(self.safety_invariants),
        }
        return sha256_canonical(preimage)

    def verify_sha256(self, *, raise_on_error: bool = True) -> bool:
        try:
            self._validate_contents()
            expected = self.compute_sha256()
            ok = self.record_sha256 == expected
            if not ok and raise_on_error:
                raise TamperDetectedError(
                    f"EngineeringDesignRecord {self.general.design_id!r} rev={self.revision} "
                    f"SHA-256 mismatch (expected {expected}, got {self.record_sha256!r}; "
                    f"{HASH_CHAIN_SEMANTICS})"
                )
            return ok
        except (ConstitutionalViolationError, EddmsValidationError) as exc:
            if raise_on_error:
                raise TamperDetectedError(
                    f"EngineeringDesignRecord {self.general.design_id!r} rev={self.revision} "
                    f"integrity violation: {exc}"
                ) from exc
            return False

    def constitutional_metadata(
        self,
        epistemic_lane: str | None = None,
        *,
        read_only: bool | None = None,
    ) -> dict[str, Any]:
        if epistemic_lane is None and read_only is None:
            return copy.deepcopy(self.safety_invariants)
        return constitutional_metadata(
            epistemic_lane if epistemic_lane is not None else "measurement",
            read_only=read_only if read_only is not None else False,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": EDDBMS_CONTRACT,
            "design_id": self.general.design_id,
            "spec_id": self.spec_id,
            "revision": self.revision,
            "prev_record_sha256": self.prev_record_sha256,
            "record_sha256": self.record_sha256,
            "pipeline_stage": self.pipeline_stage,
            "general": self.general.to_dict(),
            "properties": self.properties.to_dict(),
            "geometric": self.geometric.to_dict(),
            "provenance_log": copy.deepcopy(self.provenance_log),
            "safety_invariants": copy.deepcopy(self.safety_invariants),
        }


def _clone_record(record: EngineeringDesignRecord) -> EngineeringDesignRecord:
    return EngineeringDesignRecord(
        general=GeneralData(
            design_id=record.general.design_id,
            product_id=record.general.product_id,
            owner_metadata=copy.deepcopy(record.general.owner_metadata),
            special_instructions=record.general.special_instructions,
            commerce_info=copy.deepcopy(record.general.commerce_info),
        ),
        properties=PropertyData(
            structure_desc=copy.deepcopy(record.properties.structure_desc),
            mechanical_desc=copy.deepcopy(record.properties.mechanical_desc),
            physical_desc=copy.deepcopy(record.properties.physical_desc),
        ),
        geometric=GeometricData(
            geom_2d=copy.deepcopy(record.geometric.geom_2d),
            geom_3d=copy.deepcopy(record.geometric.geom_3d),
            mesh_data=copy.deepcopy(record.geometric.mesh_data),
            analysis_process_formats=copy.deepcopy(
                record.geometric.analysis_process_formats
            ),
        ),
        revision=record.revision,
        spec_id=record.spec_id,
        provenance_log=copy.deepcopy(record.provenance_log),
        record_sha256=record.record_sha256,
        prev_record_sha256=record.prev_record_sha256,
        pipeline_stage=record.pipeline_stage,
        safety_invariants=copy.deepcopy(record.safety_invariants),
    )


def _build_initial_module_workspaces(
    spec: FunctionEngineeringSpecification,
) -> dict[str, dict[str, Any]]:
    workspaces: dict[str, dict[str, Any]] = {}
    for mod_name in EDDBMS_DOMAIN_MODULES:
        sub_ops: dict[str, dict[str, Any]] = {
            key: {"label": label, "status": "initialized", "data": {}}
            for key, label in EDDBMS_MODULE_SUBOPERATIONS[mod_name]
        }
        ws: dict[str, Any] = {
            "module_name": mod_name,
            "spec_id": spec.spec_id,
            "intake_fed": mod_name in ("MATERIAL_DESIGN", "PRODUCT_DESIGN_AND_PLANNING"),
            "unidirectional_intake": None,
            "sub_operations": sub_ops,
            "module_data": {},
        }
        if mod_name == "MATERIAL_DESIGN":
            ws["unidirectional_intake"] = {
                "direction": "FunctionEngineeringSpecification -> MATERIAL_DESIGN",
                "spec_id": spec.spec_id,
                "objective": spec.objective,
                "target_properties": copy.deepcopy(spec.target_properties),
                "constraints": copy.deepcopy(spec.constraints),
            }
        elif mod_name == "PRODUCT_DESIGN_AND_PLANNING":
            ws["unidirectional_intake"] = {
                "direction": "FunctionEngineeringSpecification -> PRODUCT_DESIGN_AND_PLANNING",
                "spec_id": spec.spec_id,
                "title": spec.title,
                "objective": spec.objective,
                "constraints": copy.deepcopy(spec.constraints),
                "geometric_requirements": copy.deepcopy(spec.geometric_requirements),
                "special_instructions": spec.special_instructions,
            }
        elif mod_name == "DESIGN_PARAMETERS":
            ws["constraints"] = copy.deepcopy(spec.constraints)
            sub_ops["restriction_condition"]["data"] = copy.deepcopy(spec.constraints)
            sub_ops["restriction_condition"]["status"] = "seeded_from_spec"
        workspaces[mod_name] = ws
    return workspaces


class EngineeringDesignDatabase:
    """Central Figure 15.3 EDDBMS hub with revisioned history, Article IV rollback, and 6 domain spokes."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, EngineeringDesignRecord] = {}
        self._revisions: dict[str, list[EngineeringDesignRecord]] = {}
        self._specs: dict[str, FunctionEngineeringSpecification] = {}
        self._spec_index: dict[str, str] = {}
        self._module_workspaces: dict[str, dict[str, dict[str, Any]]] = {}
        self._module_history: dict[str, list[dict[str, dict[str, Any]]]] = {}

    def _require_design_record(self, design_id: str) -> EngineeringDesignRecord:
        if not isinstance(design_id, str) or not design_id.strip():
            raise UnknownDesignError("design_id must be a non-empty string")
        rec = self._records.get(design_id)
        if rec is None:
            raise UnknownDesignError(f"Unknown EDDBMS design_id: {design_id!r}")
        return rec

    def ingest_specification(
        self,
        spec: FunctionEngineeringSpecification,
        *,
        design_id: str | None = None,
        product_id: str | None = None,
        owner_metadata: Mapping[str, Any] | None = None,
        commerce_info: Mapping[str, Any] | None = None,
    ) -> EngineeringDesignRecord:
        """Unidirectional Figure 15.3 intake feeding Central DB, MATERIAL_DESIGN, and PRODUCT_DESIGN_AND_PLANNING."""
        if not isinstance(spec, FunctionEngineeringSpecification):
            raise EddmsValidationError(
                "spec must be a FunctionEngineeringSpecification instance"
            )
        spec.validate()
        spec_snapshot = FunctionEngineeringSpecification(**spec.to_dict())

        resolved_design_id = (
            design_id.strip()
            if design_id is not None
            else f"EDDBMS-{spec_snapshot.spec_id}"
        )
        resolved_design_id = _require_non_empty_str(resolved_design_id, "design_id")

        resolved_product_id = (
            product_id.strip()
            if product_id is not None
            else f"PROD-{spec_snapshot.spec_id}"
        )
        resolved_product_id = _require_non_empty_str(resolved_product_id, "product_id")

        base_owner_meta: dict[str, Any] = {
            "owner": spec_snapshot.owner,
            "title": spec_snapshot.title,
            "objective": spec_snapshot.objective,
            "spec_id": spec_snapshot.spec_id,
        }
        if owner_metadata is not None:
            clean_owner_extra = _validate_eddms_packet(
                owner_metadata, label="owner_metadata"
            )
            base_owner_meta = _deep_merge_dict(base_owner_meta, clean_owner_extra)

        base_commerce: dict[str, Any] = {
            "constraints": copy.deepcopy(spec_snapshot.constraints),
            "offline_local_only": True,
            "cloud_cost_usd": 0.0,
        }
        if commerce_info is not None:
            clean_commerce_extra = _validate_eddms_packet(
                commerce_info, label="commerce_info"
            )
            base_commerce = _deep_merge_dict(base_commerce, clean_commerce_extra)

        general = GeneralData(
            design_id=resolved_design_id,
            product_id=resolved_product_id,
            owner_metadata=base_owner_meta,
            special_instructions=spec_snapshot.special_instructions,
            commerce_info=base_commerce,
        )

        mech_seeded = {
            k: copy.deepcopy(v)
            for k, v in spec_snapshot.target_properties.items()
            if any(hint in k.lower() for hint in _MECHANICAL_KEY_HINTS)
        }
        phys_seeded = {
            k: copy.deepcopy(v)
            for k, v in spec_snapshot.target_properties.items()
            if any(hint in k.lower() for hint in _PHYSICAL_KEY_HINTS)
        }
        properties = PropertyData(
            structure_desc={"target_properties": copy.deepcopy(spec_snapshot.target_properties)},
            mechanical_desc=mech_seeded,
            physical_desc=phys_seeded,
        )

        geom3d_seeded = {
            k: copy.deepcopy(v)
            for k, v in spec_snapshot.geometric_requirements.items()
            if any(hint in k.lower() for hint in _GEOM3D_KEY_HINTS)
        }
        mesh_seeded = {
            k: copy.deepcopy(v)
            for k, v in spec_snapshot.geometric_requirements.items()
            if any(hint in k.lower() for hint in _MESH_KEY_HINTS)
        }
        geometric = GeometricData(
            geom_2d=(
                copy.deepcopy(spec_snapshot.geometric_requirements["geom_2d"])
                if isinstance(spec_snapshot.geometric_requirements.get("geom_2d"), Mapping)
                else {}
            ),
            geom_3d=geom3d_seeded,
            mesh_data=mesh_seeded,
            analysis_process_formats={
                "specification_ref": {
                    "spec_id": spec_snapshot.spec_id,
                    "spec_sha256": spec_snapshot.compute_sha256(),
                    "geometric_requirements": copy.deepcopy(
                        spec_snapshot.geometric_requirements
                    ),
                    "advisory_only": True,
                }
            },
        )

        meta = constitutional_metadata("measurement", read_only=False)
        provenance_entry: dict[str, Any] = {
            "seq": 1,
            "revision": 1,
            "action": "ingest_specification",
            "direction": "FunctionEngineeringSpecification -> EngineeringDesignDatabase",
            "spec_id": spec_snapshot.spec_id,
            "design_id": resolved_design_id,
            "product_id": resolved_product_id,
            "unidirectional_targets": list(SPEC_INTAKE_TARGETS),
            "sister_name": "Zoe",
            "sister_slot": 1,
            "epistemic_lane": "measurement",
            **meta,
        }

        record = EngineeringDesignRecord(
            general=general,
            properties=properties,
            geometric=geometric,
            revision=1,
            spec_id=spec_snapshot.spec_id,
            provenance_log=[provenance_entry],
            prev_record_sha256="GENESIS",
            pipeline_stage="PRODUCT_DESIGN_AND_PLANNING",
            safety_invariants=copy.deepcopy(meta),
        )
        workspaces = _build_initial_module_workspaces(spec_snapshot)

        # Atomic commit after all validation and hash computation succeeds.
        with self._lock:
            if spec_snapshot.spec_id in self._spec_index:
                existing_did = self._spec_index[spec_snapshot.spec_id]
                raise RevisionConflictError(
                    f"Specification {spec_snapshot.spec_id!r} already ingested as {existing_did!r}; "
                    "silent overwrite forbidden by Article IV"
                )
            if resolved_design_id in self._records:
                raise RevisionConflictError(
                    f"Design record {resolved_design_id!r} already exists; "
                    "silent overwrite forbidden by Article IV"
                )
            self._specs[resolved_design_id] = spec_snapshot
            self._spec_index[spec_snapshot.spec_id] = resolved_design_id
            self._records[resolved_design_id] = record
            self._revisions[resolved_design_id] = [_clone_record(record)]
            self._module_workspaces[resolved_design_id] = workspaces
            self._module_history[resolved_design_id] = [copy.deepcopy(workspaces)]
            return _clone_record(record)

    def get_record(self, design_id: str) -> EngineeringDesignRecord:
        """Return an isolated deep copy of the latest EngineeringDesignRecord."""
        with self._lock:
            return _clone_record(self._require_design_record(design_id))

    def get_revision(self, design_id: str, revision: int) -> EngineeringDesignRecord:
        """Return an isolated deep copy of a specific 1-indexed revision snapshot."""
        with self._lock:
            self._require_design_record(design_id)
            rev_num = _require_non_bool_int(revision, "revision", minimum=1)
            history = self._revisions[design_id]
            if rev_num > len(history):
                raise UnknownDesignError(
                    f"Revision {rev_num} out of range for {design_id!r} (max {len(history)})"
                )
            return _clone_record(history[rev_num - 1])

    def list_revisions(self, design_id: str) -> tuple[EngineeringDesignRecord, ...]:
        """Return all historical revision snapshots for design_id in monotonic order."""
        with self._lock:
            self._require_design_record(design_id)
            return tuple(_clone_record(r) for r in self._revisions[design_id])

    def read_for_module(self, design_id: str, module_name: str) -> dict[str, Any]:
        """Project central DB schemas + module workspace for a domain module (deep-copied)."""
        with self._lock:
            rec = self._require_design_record(design_id)
            norm_mod = _normalize_module_name(module_name)
            spec = self._specs[design_id]
            ws = copy.deepcopy(self._module_workspaces[design_id][norm_mod])
            meta = constitutional_metadata("measurement", read_only=True)
            return {
                **meta,
                "contract": EDDBMS_CONTRACT,
                "design_id": rec.general.design_id,
                "spec_id": rec.spec_id,
                "module_name": norm_mod,
                "revision": rec.revision,
                "record_sha256": rec.record_sha256,
                "pipeline_stage": rec.pipeline_stage,
                "intake_fed": bool(ws.get("intake_fed", False)),
                "sub_operations": {
                    key: label for key, label in EDDBMS_MODULE_SUBOPERATIONS[norm_mod]
                },
                "module_workspace": copy.deepcopy(ws),
                "module_state": ws,
                "general": rec.general.to_dict(),
                "properties": rec.properties.to_dict(),
                "geometric": rec.geometric.to_dict(),
                "constraints": copy.deepcopy(spec.constraints),
                "constitutional": copy.deepcopy(meta),
            }

    def write_from_module(
        self,
        design_id: str,
        module_name: str,
        sister_name: str,
        patch: Mapping[str, Any],
        expected_revision: int,
        *,
        epistemic_lane: str = "advisory_proposal",
        sub_operation: str | None = None,
    ) -> EngineeringDesignRecord:
        """Bidirectional validated write from a domain spoke into the central EDDBMS."""
        with self._lock:
            return self._write_from_module_locked(
                design_id,
                module_name,
                sister_name,
                patch,
                expected_revision,
                epistemic_lane=epistemic_lane,
                sub_operation=sub_operation,
            )

    def _write_from_module_locked(
        self,
        design_id: str,
        module_name: str,
        sister_name: str,
        patch: Mapping[str, Any],
        expected_revision: int,
        *,
        epistemic_lane: str = "advisory_proposal",
        sub_operation: str | None = None,
    ) -> EngineeringDesignRecord:
        current = self._require_design_record(design_id)
        norm_mod = _normalize_module_name(module_name)
        if not isinstance(sister_name, str) or not sister_name.strip():
            raise EddmsValidationError("sister_name must be a non-empty string")
        sister = resolve_sister(sister_name)

        exp_rev = _require_non_bool_int(expected_revision, "expected_revision", minimum=1)
        if exp_rev != current.revision:
            raise RevisionConflictError(
                f"Revision conflict on {design_id!r}: expected_revision={exp_rev}, "
                f"current revision={current.revision}"
            )

        if not isinstance(patch, Mapping) or len(patch) == 0:
            raise EddmsValidationError("patch must be a non-empty Mapping")

        default_lane = validate_epistemic_lane(epistemic_lane)
        effective_lane = default_lane
        if "epistemic_lane" in patch:
            effective_lane = validate_epistemic_lane(patch["epistemic_lane"])

        clean_patch = _validate_eddms_packet(
            patch,
            label="patch",
            epistemic_lane=effective_lane,
        )

        unknown_top = sorted(set(clean_patch.keys()) - _ALLOWED_PATCH_TOP_LEVEL_KEYS)
        if unknown_top:
            raise EddmsValidationError(
                f"Unknown top-level patch schema key(s): {', '.join(unknown_top)}"
            )
        if not any(k in clean_patch for k in _DATA_PATCH_SECTION_KEYS):
            raise EddmsValidationError(
                "patch must update at least one of: general, properties, geometric, sub_operations, module_data"
            )

        valid_subops = EDDBMS_SUBOPERATION_KEYS[norm_mod]
        if sub_operation is not None:
            if not isinstance(sub_operation, str) or sub_operation not in valid_subops:
                raise EddmsValidationError(
                    f"Unknown sub_operation {sub_operation!r} for module {norm_mod}"
                )

        notes_val = clean_patch.get("notes", "")
        if not isinstance(notes_val, str):
            raise EddmsValidationError("patch.notes must be a string")

        working = _clone_record(current)
        working_workspaces = copy.deepcopy(self._module_workspaces[design_id])
        ws = working_workspaces[norm_mod]
        patched_sections: list[str] = []

        if "general" in clean_patch:
            gen_patch = clean_patch["general"]
            if not isinstance(gen_patch, Mapping) or not gen_patch:
                raise EddmsValidationError("patch.general must be a non-empty Mapping")
            unknown_gen = sorted(set(gen_patch.keys()) - _ALLOWED_GENERAL_KEYS)
            if unknown_gen:
                raise EddmsValidationError(
                    f"Unknown patch.general key(s): {', '.join(unknown_gen)}"
                )
            if "design_id" in gen_patch:
                did_val = gen_patch["design_id"]
                if not isinstance(did_val, str) or not did_val.strip():
                    raise EddmsValidationError("general.design_id cannot be blank")
                if did_val.strip() != current.general.design_id:
                    raise EddmsValidationError(
                        f"general.design_id cannot be reassigned ({did_val!r} != {current.general.design_id!r})"
                    )
            if "product_id" in gen_patch:
                pid_val = _require_non_empty_str(
                    gen_patch["product_id"], "general.product_id"
                )
                working.general.product_id = pid_val
            if "special_instructions" in gen_patch:
                si_val = gen_patch["special_instructions"]
                if not isinstance(si_val, str):
                    raise EddmsValidationError("general.special_instructions must be str")
                working.general.special_instructions = si_val
            if "owner_metadata" in gen_patch:
                om_val = gen_patch["owner_metadata"]
                if not isinstance(om_val, Mapping):
                    raise EddmsValidationError("general.owner_metadata must be a Mapping")
                working.general.owner_metadata = _deep_merge_dict(
                    working.general.owner_metadata, om_val
                )
            if "commerce_info" in gen_patch:
                ci_val = gen_patch["commerce_info"]
                if not isinstance(ci_val, Mapping):
                    raise EddmsValidationError("general.commerce_info must be a Mapping")
                working.general.commerce_info = _deep_merge_dict(
                    working.general.commerce_info, ci_val
                )
            working.general.validate()
            patched_sections.append("general")

        if "properties" in clean_patch:
            prop_patch = clean_patch["properties"]
            if not isinstance(prop_patch, Mapping) or not prop_patch:
                raise EddmsValidationError("patch.properties must be a non-empty Mapping")
            unknown_prop = sorted(set(prop_patch.keys()) - _ALLOWED_PROPERTY_KEYS)
            if unknown_prop:
                raise EddmsValidationError(
                    f"Unknown patch.properties key(s): {', '.join(unknown_prop)}"
                )
            for field_name, sub_val in prop_patch.items():
                if not isinstance(sub_val, Mapping):
                    raise EddmsValidationError(
                        f"patch.properties.{field_name} must be a Mapping"
                    )
                existing_map: dict[str, Any] = getattr(working.properties, field_name)
                setattr(
                    working.properties,
                    field_name,
                    _deep_merge_dict(existing_map, sub_val),
                )
            working.properties.validate()
            patched_sections.append("properties")

        if "geometric" in clean_patch:
            geom_patch = clean_patch["geometric"]
            if not isinstance(geom_patch, Mapping) or not geom_patch:
                raise EddmsValidationError("patch.geometric must be a non-empty Mapping")
            unknown_geom = sorted(set(geom_patch.keys()) - _ALLOWED_GEOMETRIC_KEYS)
            if unknown_geom:
                raise EddmsValidationError(
                    f"Unknown patch.geometric key(s): {', '.join(unknown_geom)}"
                )
            for field_name, sub_val in geom_patch.items():
                if not isinstance(sub_val, Mapping):
                    raise EddmsValidationError(
                        f"patch.geometric.{field_name} must be a Mapping"
                    )
                existing_geom: dict[str, Any] = getattr(working.geometric, field_name)
                setattr(
                    working.geometric,
                    field_name,
                    _deep_merge_dict(existing_geom, sub_val),
                )
            working.geometric.validate()
            patched_sections.append("geometric")

        if "sub_operations" in clean_patch:
            subops_patch = clean_patch["sub_operations"]
            if not isinstance(subops_patch, Mapping) or not subops_patch:
                raise EddmsValidationError(
                    "patch.sub_operations must be a non-empty Mapping"
                )
            unknown_ops = sorted(set(subops_patch.keys()) - set(valid_subops))
            if unknown_ops:
                raise EddmsValidationError(
                    f"Unknown sub_operations key(s) for {norm_mod}: {', '.join(unknown_ops)}"
                )
            for op_key, op_val in subops_patch.items():
                op_slot = ws["sub_operations"][op_key]
                op_slot["status"] = "updated"
                op_slot["last_sister"] = sister.name
                op_slot["last_revision"] = current.revision + 1
                if isinstance(op_val, Mapping):
                    op_slot["data"] = _deep_merge_dict(op_slot["data"], op_val)
                else:
                    op_slot["data"] = _deep_merge_dict(
                        op_slot["data"], {"value": copy.deepcopy(op_val)}
                    )
            patched_sections.append("sub_operations")

        if "module_data" in clean_patch:
            mod_data_patch = clean_patch["module_data"]
            if not isinstance(mod_data_patch, Mapping) or not mod_data_patch:
                raise EddmsValidationError("patch.module_data must be a non-empty Mapping")
            ws["module_data"] = _deep_merge_dict(ws["module_data"], mod_data_patch)
            patched_sections.append("module_data")

        if sub_operation is not None:
            ws["sub_operations"][sub_operation]["last_sister"] = sister.name
            ws["sub_operations"][sub_operation]["last_revision"] = current.revision + 1
            if ws["sub_operations"][sub_operation]["status"] == "initialized":
                ws["sub_operations"][sub_operation]["status"] = "updated"

        new_revision = current.revision + 1
        meta = constitutional_metadata(effective_lane, read_only=False)
        prov_entry: dict[str, Any] = {
            "seq": len(working.provenance_log) + 1,
            "revision": new_revision,
            "action": "write_from_module",
            "direction": f"{norm_mod} <-> EngineeringDesignDatabase",
            "module_name": norm_mod,
            "sub_operation": sub_operation,
            "sister_name": sister.name,
            "sister_slot": sister.slot,
            "sister_signet": sister.signet,
            "expected_revision": exp_rev,
            "patched_sections": sorted(patched_sections),
            "patch_sha256": sha256_canonical(clean_patch),
            "prev_record_sha256": current.record_sha256,
            "epistemic_lane": effective_lane,
            **meta,
        }
        if notes_val:
            prov_entry["notes"] = notes_val

        working.revision = new_revision
        working.prev_record_sha256 = current.record_sha256
        working.provenance_log.append(prov_entry)
        working.safety_invariants = copy.deepcopy(meta)
        working.record_sha256 = working.compute_sha256()

        # Atomic commit
        self._records[design_id] = working
        self._revisions[design_id].append(_clone_record(working))
        self._module_workspaces[design_id] = working_workspaces
        self._module_history[design_id].append(copy.deepcopy(working_workspaces))
        return _clone_record(working)

    def advance_pipeline_stage(
        self,
        design_id: str,
        from_stage: str,
        to_stage: str,
        sister_name: str,
        *,
        expected_revision: int | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Advance sequential Figure 15.3 right-column pipeline stage."""
        with self._lock:
            return self._advance_pipeline_stage_locked(
                design_id,
                from_stage,
                to_stage,
                sister_name,
                expected_revision=expected_revision,
                notes=notes,
            )

    def _advance_pipeline_stage_locked(
        self,
        design_id: str,
        from_stage: str,
        to_stage: str,
        sister_name: str,
        *,
        expected_revision: int | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        current = self._require_design_record(design_id)
        if not isinstance(from_stage, str) or not isinstance(to_stage, str):
            raise PipelineOrderError("from_stage and to_stage must be strings")
        norm_from = from_stage.strip().upper()
        norm_to = to_stage.strip().upper()

        if norm_from not in EDDBMS_PIPELINE_STAGES or norm_to not in EDDBMS_PIPELINE_STAGES:
            valid = " -> ".join(EDDBMS_PIPELINE_STAGES)
            raise PipelineOrderError(
                f"Invalid pipeline stage transition {from_stage!r} -> {to_stage!r}; "
                f"valid sequence: {valid}"
            )
        if (norm_from, norm_to) not in VALID_PIPELINE_TRANSITIONS:
            raise PipelineOrderError(
                f"Pipeline transition {norm_from!r} -> {norm_to!r} violates sequential "
                "order (PRODUCT_DESIGN_AND_PLANNING -> PROJECT_MANAGEMENT -> POSTPRODUCTION_MANAGEMENT)"
            )
        if current.pipeline_stage != norm_from:
            raise PipelineOrderError(
                f"Cannot advance {design_id!r} from {norm_from!r}: current stage is {current.pipeline_stage!r}"
            )

        if not isinstance(sister_name, str) or not sister_name.strip():
            raise EddmsValidationError("sister_name must be a non-empty string")
        sister = resolve_sister(sister_name)

        if expected_revision is not None:
            exp_rev = _require_non_bool_int(
                expected_revision, "expected_revision", minimum=1
            )
            if exp_rev != current.revision:
                raise RevisionConflictError(
                    f"Revision conflict on pipeline advance for {design_id!r}: "
                    f"expected={exp_rev}, current={current.revision}"
                )

        if not isinstance(notes, str):
            raise EddmsValidationError("notes must be a string")

        working = _clone_record(current)
        working_workspaces = copy.deepcopy(self._module_workspaces[design_id])
        new_revision = current.revision + 1
        meta = constitutional_metadata("advisory_proposal", read_only=False)
        prov_entry: dict[str, Any] = {
            "seq": len(working.provenance_log) + 1,
            "revision": new_revision,
            "action": "advance_pipeline_stage",
            "direction": f"{norm_from} -> {norm_to}",
            "from_stage": norm_from,
            "to_stage": norm_to,
            "sister_name": sister.name,
            "sister_slot": sister.slot,
            "sister_signet": sister.signet,
            "prev_record_sha256": current.record_sha256,
            "epistemic_lane": "advisory_proposal",
            **meta,
        }
        if notes:
            prov_entry["notes"] = notes

        working.pipeline_stage = norm_to
        working.revision = new_revision
        working.prev_record_sha256 = current.record_sha256
        working.provenance_log.append(prov_entry)
        working.safety_invariants = copy.deepcopy(meta)
        working.record_sha256 = working.compute_sha256()

        working_workspaces[norm_to]["pipeline_entered_at_revision"] = new_revision
        working_workspaces[norm_to]["pipeline_entered_by_sister"] = sister.name

        self._records[design_id] = working
        self._revisions[design_id].append(_clone_record(working))
        self._module_workspaces[design_id] = working_workspaces
        self._module_history[design_id].append(copy.deepcopy(working_workspaces))

        return {
            **meta,
            "contract": EDDBMS_CONTRACT,
            "design_id": design_id,
            "from_stage": norm_from,
            "to_stage": norm_to,
            "current_stage": norm_to,
            "sister_name": sister.name,
            "sister_slot": sister.slot,
            "revision": new_revision,
            "record_sha256": working.record_sha256,
            "constitutional": copy.deepcopy(meta),
        }

    def rollback_to_revision(
        self,
        design_id: str,
        target_revision: int,
        *,
        sister_name: str,
        expected_revision: int | None = None,
        reason: str = "",
    ) -> EngineeringDesignRecord:
        """Article IV reversibility: restore an earlier revision as a new monotonic revision without erasing history."""
        with self._lock:
            return self._rollback_to_revision_locked(
                design_id,
                target_revision,
                sister_name=sister_name,
                expected_revision=expected_revision,
                reason=reason,
            )

    def _rollback_to_revision_locked(
        self,
        design_id: str,
        target_revision: int,
        *,
        sister_name: str,
        expected_revision: int | None = None,
        reason: str = "",
    ) -> EngineeringDesignRecord:
        current = self._require_design_record(design_id)
        target_rev = _require_non_bool_int(
            target_revision, "target_revision", minimum=1
        )
        history = self._revisions[design_id]
        if target_rev > len(history):
            raise UnknownDesignError(
                f"Target revision {target_rev} out of range for {design_id!r} (max {len(history)})"
            )
        if not isinstance(sister_name, str) or not sister_name.strip():
            raise EddmsValidationError("sister_name must be a non-empty string")
        sister = resolve_sister(sister_name)

        if expected_revision is not None:
            exp_rev = _require_non_bool_int(
                expected_revision, "expected_revision", minimum=1
            )
            if exp_rev != current.revision:
                raise RevisionConflictError(
                    f"Revision conflict on rollback for {design_id!r}: "
                    f"expected={exp_rev}, current={current.revision}"
                )
        if not isinstance(reason, str):
            raise EddmsValidationError("reason must be a string")

        snapshot_rec = _clone_record(history[target_rev - 1])
        restored_workspaces = copy.deepcopy(self._module_history[design_id][target_rev - 1])

        new_revision = current.revision + 1
        meta = constitutional_metadata("advisory_proposal", read_only=False)
        merged_log = copy.deepcopy(current.provenance_log)
        merged_log.append(
            {
                "seq": len(merged_log) + 1,
                "revision": new_revision,
                "action": "rollback_to_revision",
                "restored_from_revision": target_rev,
                "restored_from_sha256": snapshot_rec.record_sha256,
                "sister_name": sister.name,
                "sister_slot": sister.slot,
                "sister_signet": sister.signet,
                "reason": reason,
                "prev_record_sha256": current.record_sha256,
                "epistemic_lane": "advisory_proposal",
                **meta,
            }
        )

        restored = EngineeringDesignRecord(
            general=snapshot_rec.general,
            properties=snapshot_rec.properties,
            geometric=snapshot_rec.geometric,
            revision=new_revision,
            spec_id=current.spec_id,
            provenance_log=merged_log,
            prev_record_sha256=current.record_sha256,
            pipeline_stage=snapshot_rec.pipeline_stage,
            safety_invariants=copy.deepcopy(meta),
        )

        self._records[design_id] = restored
        self._revisions[design_id].append(_clone_record(restored))
        self._module_workspaces[design_id] = restored_workspaces
        self._module_history[design_id].append(copy.deepcopy(restored_workspaces))
        return _clone_record(restored)

    rollback = rollback_to_revision

    def verify_integrity(
        self,
        design_id: str | None = None,
        *,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        """Verify SHA-256 hash chain and constitutional invariants across revisions."""
        with self._lock:
            return self._verify_integrity_locked(design_id, raise_on_error=raise_on_error)

    def _verify_integrity_locked(
        self,
        design_id: str | None = None,
        *,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        target_ids: list[str]
        if design_id is not None:
            self._require_design_record(design_id)
            target_ids = [design_id]
        else:
            target_ids = sorted(self._records.keys())

        revisions_verified = 0
        try:
            for did in target_ids:
                history = self._revisions[did]
                if not history:
                    raise TamperDetectedError(f"Empty revision history for {did!r}")
                expected_prev = "GENESIS"
                for idx, rev_rec in enumerate(history, start=1):
                    if rev_rec.revision != idx:
                        raise TamperDetectedError(
                            f"Non-monotonic revision at index {idx} for {did!r}: got {rev_rec.revision}"
                        )
                    if rev_rec.prev_record_sha256 != expected_prev:
                        raise TamperDetectedError(
                            f"Hash chain broken at {did!r} rev={idx}: "
                            f"expected prev={expected_prev!r}, got {rev_rec.prev_record_sha256!r}"
                        )
                    rev_rec.verify_sha256(raise_on_error=True)
                    expected_prev = rev_rec.record_sha256
                    revisions_verified += 1

                live_rec = self._records[did]
                live_rec.verify_sha256(raise_on_error=True)
                if live_rec.record_sha256 != expected_prev or live_rec.revision != len(history):
                    raise TamperDetectedError(
                        f"Live record for {did!r} diverged from revision chain head"
                    )
        except (TamperDetectedError, ConstitutionalViolationError) as exc:
            if raise_on_error:
                raise
            return {
                "ok": False,
                "error": str(exc),
                "designs_verified": len(target_ids),
                "revisions_verified": revisions_verified,
                "tamper_evidence_only": True,
                "authentication_proof": False,
                "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
                "constitutional": constitutional_metadata("measurement", read_only=True),
            }

        return {
            "ok": True,
            "designs_verified": len(target_ids),
            "revisions_verified": revisions_verified,
            "tamper_evidence_only": True,
            "authentication_proof": False,
            "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
            "constitutional": constitutional_metadata("measurement", read_only=True),
        }

    verify_record_integrity = verify_integrity


@dataclass(frozen=True)
class EddmsCollaborationRun:
    """Deterministic result of coupling the 9-sister hexagonal mesh with EDDBMS."""

    spec: FunctionEngineeringSpecification
    database: EngineeringDesignDatabase
    record: EngineeringDesignRecord
    design_id: str
    spec_id: str
    ticks_executed: int
    tick_results: tuple[HexTickResult, ...]
    tick_trace_hashes: tuple[str, ...]
    sister_module_bindings: dict[str, str]
    covered_modules: tuple[str, ...]
    sister_contributions: tuple[dict[str, Any], ...]
    run_sha256: str
    safety_invariants: dict[str, Any]

    @property
    def db(self) -> EngineeringDesignDatabase:
        return self.database

    @property
    def design_record(self) -> EngineeringDesignRecord:
        return self.record

    def constitutional_metadata(
        self,
        epistemic_lane: str = "advisory_proposal",
        *,
        read_only: bool = True,
    ) -> dict[str, Any]:
        return constitutional_metadata(epistemic_lane, read_only=read_only)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": EDDBMS_CONTRACT,
            "design_id": self.design_id,
            "spec_id": self.spec_id,
            "ticks_executed": self.ticks_executed,
            "tick_trace_hashes": list(self.tick_trace_hashes),
            "sister_module_bindings": dict(self.sister_module_bindings),
            "covered_modules": list(self.covered_modules),
            "sister_contributions": copy.deepcopy(list(self.sister_contributions)),
            "record": self.record.to_dict(),
            "run_sha256": self.run_sha256,
            "safety_invariants": copy.deepcopy(self.safety_invariants),
        }

    def __repr__(self) -> str:
        sisters_str = ", ".join(self.sister_module_bindings.keys())
        modules_str = ", ".join(self.covered_modules)
        return (
            f"EddmsCollaborationRun(design_id={self.design_id!r}, spec_id={self.spec_id!r}, "
            f"ticks_executed={self.ticks_executed}, revision={self.record.revision}, "
            f"sisters=[{sisters_str}], modules=[{modules_str}], "
            f"run_sha256={self.run_sha256[:12]!r})"
        )


def _build_sister_cycle_patch(
    cell: HexCell,
    spec: FunctionEngineeringSpecification,
    tick_num: int,
    tick_trace_sha256: str,
    view: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Build a deterministic, domain-aligned EDDBMS patch for one sister at one tick."""
    sname = cell.sister.name
    mod = _normalize_module_name(cell.domain_module)
    subops = EDDBMS_SUBOPERATION_KEYS[mod]
    cell_digest = sha256_canonical(
        {
            "sister": sname,
            "slot": cell.sister.slot,
            "module": mod,
            "tick": tick_num,
            "tick_trace_sha256": tick_trace_sha256,
            "cell_revision": cell.revision,
        }
    )

    if mod == "MATERIAL_DESIGN":
        sub_op = subops[(tick_num - 1) % len(subops)]
        return sub_op, {
            "properties": {
                "structure_desc": {
                    f"material_screen_{sname.lower()}": {
                        "tick": tick_num,
                        "sister": sname,
                        "digest": cell_digest[:16],
                        "target_keys": sorted(spec.target_properties.keys()),
                    }
                },
                "physical_desc": {
                    "material_screen_tick": tick_num,
                    "material_digest": cell_digest[:16],
                },
            },
            "sub_operations": {
                sub_op: {
                    "tick": tick_num,
                    "sister": sname,
                    "digest": cell_digest[:16],
                }
            },
        }

    if mod == "HUMAN_MODEL":
        sub_op = subops[(tick_num - 1) % len(subops)]
        return sub_op, {
            "general": {
                "owner_metadata": {
                    "safe_offline_profile": {
                        "sister": sname,
                        "tick": tick_num,
                        "ergonomic_checks": "verified_offline",
                    }
                }
            },
            "properties": {
                "mechanical_desc": {
                    "human_ergonomics": {
                        "sister": sname,
                        "tick": tick_num,
                        "digest": cell_digest[:16],
                    }
                }
            },
            "sub_operations": {
                sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
            },
        }

    if mod == "DESIGN_PARAMETERS":
        sub_op = subops[(tick_num - 1) % len(subops)]
        return sub_op, {
            "properties": {
                "physical_desc": {
                    "parameter_bounds": {
                        "sister": sname,
                        "tick": tick_num,
                        "constraint_keys": sorted(spec.constraints.keys()),
                    }
                }
            },
            "geometric": {
                "analysis_process_formats": {
                    "design_parameters_proof": {
                        "sister": sname,
                        "tick": tick_num,
                        "digest": cell_digest[:16],
                    }
                }
            },
            "sub_operations": {
                sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
            },
        }

    if mod == "PRODUCT_DESIGN_AND_PLANNING":
        if sname == "Tetra":
            sub_op = "inventory_of_materials"
            return sub_op, {
                "geometric": {
                    "geom_3d": {
                        "spatial_lattice": {
                            "sister": sname,
                            "tick": tick_num,
                            "digest": cell_digest[:16],
                        }
                    },
                    "mesh_data": {
                        "spatial_lattice_mesh": {
                            "sister": sname,
                            "tick": tick_num,
                            "digest": cell_digest[:16],
                        }
                    },
                },
                "sub_operations": {
                    sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
                },
            }
        sub_op = "drawing_of_product"
        return sub_op, {
            "geometric": {
                "geom_2d": {
                    "vdi_vector_layout": {
                        "sister": sname,
                        "tick": tick_num,
                        "digest": cell_digest[:16],
                    }
                }
            },
            "sub_operations": {
                sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
            },
        }

    if mod == "PROJECT_MANAGEMENT":
        if sname == "Tosi":
            sub_op = "pre_process"
            return sub_op, {
                "geometric": {
                    "analysis_process_formats": {
                        "hardware_hal_gate": {
                            "sister": sname,
                            "tick": tick_num,
                            "digest": cell_digest[:16],
                        }
                    }
                },
                "sub_operations": {
                    sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
                },
            }
        sub_op = "design_requirement"
        return sub_op, {
            "general": {
                "commerce_info": {
                    "coordinator_plan": {
                        "sister": sname,
                        "tick": tick_num,
                        "seen_revision": view["revision"],
                    }
                }
            },
            "module_data": {
                "coordinator_digest": cell_digest[:16],
                "tick": tick_num,
            },
            "sub_operations": {
                sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
            },
        }

    # POSTPRODUCTION_MANAGEMENT (Mono, Lumen, or custom binding)
    if sname == "Mono":
        sub_op = "evaluation"
        return sub_op, {
            "geometric": {
                "analysis_process_formats": {
                    "formal_sha256_audit": {
                        "sister": sname,
                        "tick": tick_num,
                        "tick_trace_sha256": tick_trace_sha256,
                    }
                }
            },
            "sub_operations": {
                sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
            },
        }
    sub_op = "visualization"
    return sub_op, {
        "geometric": {
            "analysis_process_formats": {
                "spectral_visualization": {
                    "sister": sname,
                    "tick": tick_num,
                    "digest": cell_digest[:16],
                },
                "hex_mesh_ticks": {
                    f"tick_{tick_num}": tick_trace_sha256,
                },
            }
        },
        "sub_operations": {
            sub_op: {"tick": tick_num, "sister": sname, "digest": cell_digest[:16]}
        },
    }


def run_sister_eddms_cycle(
    mesh: HexCollaborationMesh,
    spec: FunctionEngineeringSpecification,
    ticks: int = 2,
    *,
    db: EngineeringDesignDatabase | None = None,
) -> EddmsCollaborationRun:
    """Couple all 9 sisters on the hexagonal mesh and sync bidirectionally with EDDBMS."""
    if not isinstance(mesh, HexCollaborationMesh):
        raise EddmsValidationError(
            f"mesh must be a HexCollaborationMesh, got {type(mesh).__name__}"
        )
    if not isinstance(spec, FunctionEngineeringSpecification):
        raise EddmsValidationError(
            f"spec must be a FunctionEngineeringSpecification, got {type(spec).__name__}"
        )
    spec.validate()
    num_ticks = _require_non_bool_int(ticks, "ticks", minimum=1)

    mesh.verify_integrity(raise_on_error=True)

    cells_ordered = sorted(mesh.cells(), key=lambda c: (c.sister.slot, c.cell_id))
    present_sisters = {c.sister.name for c in cells_ordered}
    expected_sisters = {s.name for s in ZOE_SISTERS}
    if present_sisters != expected_sisters:
        missing = sorted(expected_sisters - present_sisters)
        raise EddmsValidationError(
            f"HexCollaborationMesh must bind all 9 canonical sisters; missing: {', '.join(missing)}"
        )

    normalized_modules: dict[str, str] = {}
    present_modules: set[str] = set()
    for cell in cells_ordered:
        norm_mod = _normalize_module_name(cell.domain_module)
        normalized_modules[cell.cell_id] = norm_mod
        present_modules.add(norm_mod)
    missing_mods = sorted(set(EDDBMS_DOMAIN_MODULES) - present_modules)
    if missing_mods:
        raise EddmsValidationError(
            f"HexCollaborationMesh must cover all 6 EDDBMS domain modules; missing: {', '.join(missing_mods)}"
        )

    database = db if db is not None else EngineeringDesignDatabase()
    if not isinstance(database, EngineeringDesignDatabase):
        raise EddmsValidationError(
            f"db must be an EngineeringDesignDatabase, got {type(database).__name__}"
        )

    initial_record = database.ingest_specification(spec)
    design_id = initial_record.general.design_id

    def _coupling_step(
        cell_copy: HexCell,
        neighbor_states: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        norm_mod = _normalize_module_name(cell_copy.domain_module)
        next_state = copy.deepcopy(cell_copy.state)
        next_state["slot"] = cell_copy.sister.slot
        next_state["signet"] = cell_copy.sister.signet
        next_state["domain_module"] = norm_mod
        next_state["eddms_design_id"] = design_id
        next_state["last_tick"] = mesh.tick + 1
        next_state["coupled_neighbors"] = list(neighbor_states.keys())
        next_state["neighbor_domains"] = {
            nid: str(nb_state.get("domain_module", ""))
            for nid, nb_state in neighbor_states.items()
        }
        return next_state

    tick_results: list[HexTickResult] = []
    contributions: list[dict[str, Any]] = []
    current_record = initial_record

    for tick_num in range(1, num_ticks + 1):
        for cell in cells_ordered:
            mod = normalized_modules[cell.cell_id]
            view = database.read_for_module(design_id, mod)
            for nb_id in mesh.neighbors(cell.cell_id):
                mesh.send_neighbor_message(
                    cell.cell_id,
                    nb_id,
                    f"eddms.sync.{mod.lower()}",
                    {
                        "design_id": design_id,
                        "spec_id": spec.spec_id,
                        "tick": tick_num,
                        "sender_sister": cell.sister.name,
                        "domain_module": mod,
                        "db_revision": view["revision"],
                    },
                    epistemic_lane="measurement",
                )

        tick_res = mesh.step_coupled_tick(coupling_fn=_coupling_step)
        tick_results.append(tick_res)

        for cell in cells_ordered:
            mod = normalized_modules[cell.cell_id]
            view = database.read_for_module(design_id, mod)
            sub_op, patch = _build_sister_cycle_patch(
                cell,
                spec,
                tick_num,
                tick_res.trace_sha256,
                view,
            )
            current_record = database.write_from_module(
                design_id,
                mod,
                cell.sister.name,
                patch,
                expected_revision=current_record.revision,
                epistemic_lane="advisory_proposal",
                sub_operation=sub_op,
            )
            contributions.append(
                {
                    "tick": tick_num,
                    "sister_name": cell.sister.name,
                    "sister_slot": cell.sister.slot,
                    "cell_id": cell.cell_id,
                    "domain_module": mod,
                    "sub_operation": sub_op,
                    "db_revision": current_record.revision,
                    "record_sha256": current_record.record_sha256,
                }
            )

    mesh.verify_integrity(raise_on_error=True)
    database.verify_integrity(design_id, raise_on_error=True)

    bindings = {cell.sister.name: normalized_modules[cell.cell_id] for cell in cells_ordered}
    covered_modules = tuple(
        mod for mod in EDDBMS_DOMAIN_MODULES if mod in present_modules
    )
    trace_hashes = tuple(tr.trace_sha256 for tr in tick_results)
    safety = constitutional_metadata("advisory_proposal", read_only=True)
    run_sha = sha256_canonical(
        {
            "contract": EDDBMS_CONTRACT,
            "design_id": design_id,
            "spec_id": spec.spec_id,
            "ticks_executed": num_ticks,
            "tick_trace_hashes": list(trace_hashes),
            "sister_module_bindings": bindings,
            "covered_modules": list(covered_modules),
            "final_record_sha256": current_record.record_sha256,
            "safety_invariants": safety,
        }
    )

    return EddmsCollaborationRun(
        spec=FunctionEngineeringSpecification(**spec.to_dict()),
        database=database,
        record=current_record,
        design_id=design_id,
        spec_id=spec.spec_id,
        ticks_executed=num_ticks,
        tick_results=tuple(tick_results),
        tick_trace_hashes=trace_hashes,
        sister_module_bindings=bindings,
        covered_modules=covered_modules,
        sister_contributions=tuple(contributions),
        run_sha256=run_sha,
        safety_invariants=safety,
    )


__all__ = [
    "ATTRIBUTION_TEXT",
    "DEFAULT_SISTER_DOMAIN_MODULES",
    "EDDBMS_CONTRACT",
    "EDDBMS_DOMAIN_MODULES",
    "EDDBMS_MODULE_SUBOPERATIONS",
    "EDDBMS_PIPELINE_STAGES",
    "EDDBMS_SUBOPERATION_KEYS",
    "HASH_CHAIN_SEMANTICS",
    "PIPELINE_STAGES",
    "SAFETY_INVARIANTS",
    "SPEC_INTAKE_TARGETS",
    "VALID_PIPELINE_TRANSITIONS",
    "ZOE_SISTERS",
    "ConstitutionalViolationError",
    "EddmsCollaborationRun",
    "EddmsConflictError",
    "EddmsPipelineError",
    "EddmsRecordNotFoundError",
    "EddmsValidationError",
    "EngineeringDesignDatabase",
    "EngineeringDesignRecord",
    "EpistemicFirewallError",
    "FunctionEngineeringSpecification",
    "GeneralData",
    "GeometricData",
    "PipelineOrderError",
    "PropertyData",
    "RevisionConflictError",
    "SisterModelSpec",
    "TamperDetectedError",
    "UnknownDesignError",
    "build_default_zoe_mesh",
    "canonical_json_bytes",
    "constitutional_metadata",
    "list_module_suboperations",
    "resolve_sister",
    "run_sister_eddms_cycle",
    "sha256_canonical",
    "validate_constitutional_packet",
    "validate_epistemic_lane",
]
