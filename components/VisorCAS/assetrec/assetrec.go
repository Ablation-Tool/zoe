// Package assetrec emits VisorCAS observations as records conforming to the
// canonical nuclide-asset-schema (v1.1.0). The schema is asset-centric and has
// no false-positive/disposition field, so VisorCAS carries its disposition in
// the schema's `raw` pass-through (the audit-recommended bridge); a `deception`
// disposition additionally maps onto classification.category = honeypot, which
// the schema does model.
package assetrec

import (
	"time"

	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
)

const schemaVersion = "1.1.0"

type asset struct {
	IP   string `json:"ip"`
	Port int    `json:"port"`
}

type source struct {
	Tool        string `json:"tool"`
	ToolVersion string `json:"tool_version,omitempty"`
	RunID       string `json:"run_id,omitempty"`
}

type classification struct {
	Category string `json:"category,omitempty"`
}

// AssetRecord is the subset of nuclide-asset-schema VisorCAS emits. Field order
// and json tags match the schema; omitempty keeps optional blocks out so the
// record stays minimal and additionalProperties:false is never violated.
type AssetRecord struct {
	SchemaVersion  string          `json:"schema_version"`
	Asset          asset           `json:"asset"`
	Source         source          `json:"source"`
	Timestamp      string          `json:"timestamp"`
	Classification *classification `json:"classification,omitempty"`
	Raw            map[string]any  `json:"raw,omitempty"`
}

// Record builds a schema-conformant asset record for an observation, carrying
// its disposition and fingerprint hash in raw.
func Record(r normalize.Response, disp ledger.Disposition, fpHash, runID string) AssetRecord {
	rec := AssetRecord{
		SchemaVersion: schemaVersion,
		Asset:         asset{IP: r.IP, Port: r.Port},
		Source:        source{Tool: "visorcas", ToolVersion: "0.1.0", RunID: runID},
		Timestamp:     timestamp(r.ObservedAt),
		Raw: map[string]any{
			"disposition": string(disp),
			"fp_hash":     fpHash,
			"service":     r.Signature,
			"auth_status": normalize.NormalizeAuth(r.AuthStatus),
		},
	}
	if disp == ledger.Deception {
		rec.Classification = &classification{Category: "honeypot"}
	}
	return rec
}

// timestamp returns observed if it is set, otherwise now in RFC3339 (the schema
// requires a date-time, so the field is never empty).
func timestamp(observed string) string {
	if observed != "" {
		return observed
	}
	return time.Now().UTC().Format(time.RFC3339)
}
