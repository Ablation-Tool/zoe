// Package ledger ties the normalizer and the content-addressed store together
// into the VisorCAS false-positive ledger: a queryable SQLite index over
// immutable fingerprint blobs. VisorLog records true positives; this records
// what looked like a finding but was not.
package ledger

import (
	"database/sql"
	"fmt"
	"path/filepath"
	"time"

	"github.com/nuclide-research/VisorCAS/cas"
	"github.com/nuclide-research/VisorCAS/normalize"

	_ "modernc.org/sqlite"
)

// Disposition is the class of a false positive. It is deliberately NOT a binary
// "FP / not FP": only misidentification is safe to learn into an exclusion
// filter. auth-on and deception are real signals that must reach the findings
// ledger or the honeypot tracker, never the exclusion path.
type Disposition string

const (
	Misidentification Disposition = "misidentification"   // not an AI/LLM service at all
	TransientArtifact Disposition = "transient-artifact"  // scan-state or tool artifact; re-verify
	AuthOn            Disposition = "auth-on"             // real service, auth present; promote to VisorLog
	Deception         Disposition = "deception"           // honeypot / fake surface; track as intel
	ToolBug           Disposition = "tool-bug"            // scanner defect; fix at the source
	WrongSurfaceClass Disposition = "wrong-surface-class" // correct fingerprint, wrong surface (Docker/K8s substrate); reroute, never exclude
)

// Valid reports whether d is one of the six known dispositions.
func (d Disposition) Valid() bool {
	switch d {
	case Misidentification, TransientArtifact, AuthOn, Deception, ToolBug, WrongSurfaceClass:
		return true
	}
	return false
}

// Excludable reports whether a pattern with this disposition may be added to the
// BF-B exclusion filter. Only misidentification qualifies: transient artifacts
// must be re-verified, auth-on is the research thesis, deception is intelligence,
// tool-bugs are fixed at the scanner, and wrong-surface-class reroutes to the
// substrate channel. This is the single most important correctness rule in the
// ledger.
func (d Disposition) Excludable() bool {
	return d == Misidentification
}

// Finding is a verified false positive ready to record.
type Finding struct {
	Response    normalize.Response
	Disposition Disposition
	Category    string // finer free-text label, optional
	RootFix     string // upstream fix that would stop this FP, optional
	SurveyCtx   string // survey or category this was seen in
}

// Pattern is a stored fp_pattern row.
type Pattern struct {
	Hash        string
	Category    string
	Disposition Disposition
	RootFix     string
	FirstSeen   time.Time
	HitCount    int
}

// Ledger is the FP ledger: a content-addressed store of fingerprint blobs plus a
// SQLite index over them.
type Ledger struct {
	store *cas.Store
	db    *sql.DB
}

const schema = `
CREATE TABLE IF NOT EXISTS fp_pattern (
  fp_hash     TEXT PRIMARY KEY,
  category    TEXT,
  disposition TEXT NOT NULL,
  root_fix    TEXT,
  first_seen  TEXT NOT NULL,
  hit_count   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS occurrence (
  fp_hash     TEXT NOT NULL,
  source      TEXT,
  ip          TEXT,
  observed_at TEXT,
  survey_ctx  TEXT,
  recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_occurrence_hash ON occurrence(fp_hash);
CREATE TABLE IF NOT EXISTS source_rel (
  source      TEXT NOT NULL,
  category    TEXT,
  lag_days    REAL,
  reliability REAL,
  PRIMARY KEY (source, category)
);
CREATE TABLE IF NOT EXISTS reclassify_log (
  fp_hash   TEXT NOT NULL,
  from_disp TEXT NOT NULL,
  to_disp   TEXT NOT NULL,
  reason    TEXT,
  at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reclassify_hash ON reclassify_log(fp_hash);
`

// Open opens (creating if needed) a ledger rooted at dir: a CAS blob store under
// dir/cas and a SQLite index at dir/visorcas.db.
func Open(dir string) (*Ledger, error) {
	store, err := cas.Open(filepath.Join(dir, "cas"))
	if err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", filepath.Join(dir, "visorcas.db"))
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1) // SQLite: serialize writers, avoid SQLITE_BUSY
	if _, err := db.Exec(schema); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("ledger: creating schema: %w", err)
	}
	return &Ledger{store: store, db: db}, nil
}

// Close releases the underlying database handle.
func (l *Ledger) Close() error { return l.db.Close() }

// Record stores a verified false positive: it normalizes the response to its
// fingerprint, writes that to the CAS, upserts the pattern row (incrementing
// hit_count on repeat), and appends an occurrence. It returns the fingerprint
// hash - the pattern's content address. The first record of a pattern fixes its
// disposition, category, and root_fix; later records only bump hit_count.
func (l *Ledger) Record(f Finding) (string, error) {
	if !f.Disposition.Valid() {
		return "", fmt.Errorf("ledger: invalid disposition %q", f.Disposition)
	}
	fp := normalize.Fingerprint(f.Response)
	hash, err := l.store.Put(fp)
	if err != nil {
		return "", err
	}
	now := time.Now().UTC().Format(time.RFC3339)
	if _, err := l.db.Exec(
		`INSERT INTO fp_pattern (fp_hash, category, disposition, root_fix, first_seen, hit_count)
		 VALUES (?, ?, ?, ?, ?, 1)
		 ON CONFLICT(fp_hash) DO UPDATE SET hit_count = hit_count + 1`,
		hash, f.Category, string(f.Disposition), f.RootFix, now,
	); err != nil {
		return "", fmt.Errorf("ledger: upserting pattern: %w", err)
	}
	r := f.Response
	if _, err := l.db.Exec(
		`INSERT INTO occurrence (fp_hash, source, ip, observed_at, survey_ctx, recorded_at)
		 VALUES (?, ?, ?, ?, ?, ?)`,
		hash, r.Source, r.IP, r.ObservedAt, f.SurveyCtx, now,
	); err != nil {
		return "", fmt.Errorf("ledger: appending occurrence: %w", err)
	}
	return hash, nil
}

// Pattern returns the stored pattern for a fingerprint hash.
func (l *Ledger) Pattern(hash string) (Pattern, error) {
	var (
		p         Pattern
		disp      string
		firstSeen string
		category  sql.NullString
		rootFix   sql.NullString
	)
	err := l.db.QueryRow(
		`SELECT fp_hash, category, disposition, root_fix, first_seen, hit_count
		 FROM fp_pattern WHERE fp_hash = ?`, hash,
	).Scan(&p.Hash, &category, &disp, &rootFix, &firstSeen, &p.HitCount)
	if err != nil {
		return Pattern{}, err
	}
	p.Category = category.String
	p.RootFix = rootFix.String
	p.Disposition = Disposition(disp)
	p.FirstSeen, _ = time.Parse(time.RFC3339, firstSeen)
	return p, nil
}

// HasFingerprint reports whether the fingerprint blob is in the CAS.
func (l *Ledger) HasFingerprint(hash string) bool { return l.store.Has(hash) }

// OccurrenceCount returns how many times a pattern has been observed.
func (l *Ledger) OccurrenceCount(hash string) int {
	var n int
	_ = l.db.QueryRow(`SELECT COUNT(*) FROM occurrence WHERE fp_hash = ?`, hash).Scan(&n)
	return n
}

// PatternCount returns the number of distinct patterns in the ledger.
func (l *Ledger) PatternCount() int {
	var n int
	_ = l.db.QueryRow(`SELECT COUNT(*) FROM fp_pattern`).Scan(&n)
	return n
}

// Reclassify is one entry in a pattern's disposition history.
type Reclassify struct {
	From, To Disposition
	Reason   string
	At       time.Time
}

// Reclassify changes a pattern's disposition and appends a history entry without
// destroying the prior state. Reclassifying away from an excludable disposition
// (e.g. misidentification -> auth-on) reopens the pattern: the exclusion view
// flips and future fusion stops screening it. This is the recoverability path
// that makes bloom-gating safe - a bad learn is reversible and audited.
func (l *Ledger) Reclassify(hash string, to Disposition, reason string) error {
	if !to.Valid() {
		return fmt.Errorf("ledger: invalid disposition %q", to)
	}
	var from string
	if err := l.db.QueryRow(`SELECT disposition FROM fp_pattern WHERE fp_hash = ?`, hash).Scan(&from); err != nil {
		return fmt.Errorf("ledger: reclassify %s: %w", hash, err)
	}
	now := time.Now().UTC().Format(time.RFC3339)
	if _, err := l.db.Exec(`UPDATE fp_pattern SET disposition = ? WHERE fp_hash = ?`, string(to), hash); err != nil {
		return fmt.Errorf("ledger: reclassify update: %w", err)
	}
	if _, err := l.db.Exec(
		`INSERT INTO reclassify_log (fp_hash, from_disp, to_disp, reason, at) VALUES (?, ?, ?, ?, ?)`,
		hash, from, string(to), reason, now,
	); err != nil {
		return fmt.Errorf("ledger: reclassify log: %w", err)
	}
	return nil
}

// History returns a pattern's reclassification entries, oldest first.
func (l *Ledger) History(hash string) ([]Reclassify, error) {
	rows, err := l.db.Query(
		`SELECT from_disp, to_disp, reason, at FROM reclassify_log WHERE fp_hash = ? ORDER BY at`, hash)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Reclassify
	for rows.Next() {
		var fromd, tod, at string
		var reason sql.NullString
		if err := rows.Scan(&fromd, &tod, &reason, &at); err != nil {
			return nil, err
		}
		t, _ := time.Parse(time.RFC3339, at)
		out = append(out, Reclassify{From: Disposition(fromd), To: Disposition(tod), Reason: reason.String, At: t})
	}
	return out, rows.Err()
}
