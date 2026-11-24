// Package fuse merges observations from multiple scan sources (Shodan, Censys,
// prior NuClide data) into ranked candidates. Cross-source agreement is a
// pre-probe confidence signal; cross-source disagreement is a divergence
// (staleness / auth-state) signal. This is Stage 0c: it decides what the
// expensive deep-enumeration ever runs against.
package fuse

import (
	"sort"

	"github.com/nuclide-research/VisorCAS/cas"
	"github.com/nuclide-research/VisorCAS/normalize"
)

// Candidate is one host after fusion across sources.
type Candidate struct {
	IP        string
	FPHash    string   // the dominant (most-agreed) service fingerprint for this host
	Agreement int      // tier-2 IDENTITY agreement: distinct sources mapping IP -> FPHash
	// tier-1 LIVENESS agreement: distinct sources that observed IP at all,
	// regardless of how each named the service. An app-layer fingerprinter and a
	// banner-grabber rarely produce the same FPHash, so identity agreement
	// between them is near-unreachable by construction; liveness agreement
	// preserves the cross-source corroboration that both confirmed the host live.
	LivenessAgreement int
	Sources           []string // all distinct sources that observed IP, sorted
	Divergent         bool     // sources disagree on the fingerprint (staleness / auth-state divergence)
}

// Fuse groups observations by host and computes per-host agreement and
// divergence. Agreement counts DISTINCT sources, never raw observation count,
// so the same source observing a host twice does not inflate confidence.
func Fuse(obs []normalize.Response) []Candidate {
	// ip -> fingerprint hash -> set of sources
	byIP := map[string]map[string]map[string]bool{}
	for _, o := range obs {
		h := cas.Hash(normalize.Fingerprint(o))
		if byIP[o.IP] == nil {
			byIP[o.IP] = map[string]map[string]bool{}
		}
		if byIP[o.IP][h] == nil {
			byIP[o.IP][h] = map[string]bool{}
		}
		byIP[o.IP][h][o.Source] = true
	}

	var cands []Candidate
	for ip, hashes := range byIP {
		// Deterministic dominant pick: most distinct sources, ties broken by the
		// lexicographically smaller hash.
		hkeys := make([]string, 0, len(hashes))
		for h := range hashes {
			hkeys = append(hkeys, h)
		}
		sort.Strings(hkeys)

		var (
			domHash string
			domN    int
			allSrc  = map[string]bool{}
		)
		for _, h := range hkeys {
			if n := len(hashes[h]); n > domN {
				domN, domHash = n, h
			}
			for s := range hashes[h] {
				allSrc[s] = true
			}
		}

		srcs := make([]string, 0, len(allSrc))
		for s := range allSrc {
			srcs = append(srcs, s)
		}
		sort.Strings(srcs)

		cands = append(cands, Candidate{
			IP:                ip,
			FPHash:            domHash,
			Agreement:         domN,
			LivenessAgreement: len(srcs),
			Sources:           srcs,
			Divergent:         len(hashes) > 1,
		})
	}
	sort.Slice(cands, func(i, j int) bool { return cands[i].IP < cands[j].IP })
	return cands
}

// Rank orders candidates for the verification queue: highest identity
// agreement first (3/3 before 2/3 before 1/3), then highest liveness agreement
// (more sources confirming the host is live), then non-divergent before
// divergent, then by IP for determinism.
func Rank(cands []Candidate) []Candidate {
	out := make([]Candidate, len(cands))
	copy(out, cands)
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Agreement != out[j].Agreement {
			return out[i].Agreement > out[j].Agreement
		}
		// At equal identity agreement, more sources confirming the host is live
		// is stronger corroboration than fewer, so liveness breaks the tie before
		// the divergence flag does.
		if out[i].LivenessAgreement != out[j].LivenessAgreement {
			return out[i].LivenessAgreement > out[j].LivenessAgreement
		}
		if out[i].Divergent != out[j].Divergent {
			return !out[i].Divergent
		}
		return out[i].IP < out[j].IP
	})
	return out
}

// Screen splits candidates against the known-FP corpus: any candidate whose
// fingerprint is a known excludable false positive is skipped, the rest survive
// to verification. The lookup is a function so fuse stays decoupled from ledger.
func Screen(cands []Candidate, isKnownExcludable func(fpHash string) bool) (survivors, skipped []Candidate) {
	for _, c := range cands {
		if isKnownExcludable(c.FPHash) {
			skipped = append(skipped, c)
		} else {
			survivors = append(survivors, c)
		}
	}
	return survivors, skipped
}
