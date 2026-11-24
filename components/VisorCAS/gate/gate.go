// Package gate is VisorCAS's keep/drop decision for the pipeline. An observation
// is dropped when the rule screen refutes it, or when the content-addressed
// corpus already knows its fingerprint as an excludable false positive. A
// downgrade is kept (it is real, just over-rated), and a non-excludable corpus
// disposition (auth-on, deception, transient, wrong-surface-class) is kept - so
// the thesis and the honeypot intelligence are never filtered away. This is what
// turns observe mode into gating.
package gate

import (
	"github.com/nuclide-research/VisorCAS/cas"
	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
	"github.com/nuclide-research/VisorCAS/screen"
)

// Decide reports whether to keep an observation in the pipeline, and if not, why.
func Decide(r normalize.Response, l *ledger.Ledger) (keep bool, reason string) {
	if res := screen.Screen(r); res.Verdict == screen.Refuted {
		return false, "screen:" + res.SignatureID
	}
	h := cas.Hash(normalize.Fingerprint(r))
	if p, err := l.Pattern(h); err == nil && p.Disposition.Excludable() {
		return false, "corpus:" + string(p.Disposition)
	}
	return true, ""
}
