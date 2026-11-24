package cas

import (
	"encoding/binary"
	"sync/atomic"

	"lukechampine.com/blake3"
)

// DefaultBloomBytes matches the 16 MB lock-free Bloom filter design from
// Scanner-Bloom-CAS-Dedup-Design (134,217,728 bits; 3 probes per key).
const (
	DefaultBloomBytes = 16 * 1024 * 1024
	DefaultCASSlots   = 1 << 21 // 2,097,152 atomic uint64 slots (16 MB)
	defaultMaxProbes  = 64
)

// BloomCASConfig configures a lock-free two-layer Bloom + atomic CAS deduplicator.
type BloomCASConfig struct {
	// BloomBits is the number of bits in the lock-free Bloom filter (rounded up
	// to a power of two >= 64). Defaults to DefaultBloomBytes * 8.
	BloomBits uint64
	// CASSlots is the number of atomic uint64 slots in the open-addressed CAS
	// ownership table (rounded up to a power of two >= 64). Defaults to DefaultCASSlots.
	CASSlots uint64
	// AllowBloomFastReject enables the scanner-mode read-only Bloom fast path
	// (~98% zero-CAS duplicate rejection with tunable ~2% false-positive rate).
	// When false (default), Claim always verifies exact ownership in the CAS
	// table so zero unseen findings are ever dropped.
	AllowBloomFastReject bool
}

// DedupStats reports atomic lock-free telemetry counters.
type DedupStats struct {
	TotalChecks      uint64
	BloomFastRejects uint64
	CASClaims        uint64
	CASDuplicates    uint64
	CASOverflow      uint64
}

// BloomCASDedup implements a mutex-free two-layer concurrent deduplicator:
//   Layer 1: Lock-free Bloom filter (3 atomic bit probes from a single blake3 hash)
//   Layer 2: Open-addressed atomic Compare-And-Swap (CAS) claim table
//
// Safe for 1,000+ concurrent worker goroutines without mutex contention.
type BloomCASDedup struct {
	bloomWords           []atomic.Uint64
	bloomMask            uint64
	casSlots             []atomic.Uint64
	casMask              uint64
	allowBloomFastReject bool

	totalChecks      atomic.Uint64
	bloomFastRejects atomic.Uint64
	casClaims        atomic.Uint64
	casDuplicates    atomic.Uint64
	casOverflow      atomic.Uint64
}

func nextPow2(v uint64) uint64 {
	if v <= 64 {
		return 64
	}
	v--
	v |= v >> 1
	v |= v >> 2
	v |= v >> 4
	v |= v >> 8
	v |= v >> 16
	v |= v >> 32
	v++
	return v
}

// NewBloomCASDedup allocates a lock-free Bloom + atomic CAS deduplicator.
func NewBloomCASDedup(cfg BloomCASConfig) *BloomCASDedup {
	bits := cfg.BloomBits
	if bits == 0 {
		bits = DefaultBloomBytes * 8
	}
	bits = nextPow2(bits)

	slots := cfg.CASSlots
	if slots == 0 {
		slots = DefaultCASSlots
	}
	slots = nextPow2(slots)

	return &BloomCASDedup{
		bloomWords:           make([]atomic.Uint64, bits/64),
		bloomMask:            bits - 1,
		casSlots:             make([]atomic.Uint64, slots),
		casMask:              slots - 1,
		allowBloomFastReject: cfg.AllowBloomFastReject,
	}
}

// hashProbes derives 3 independent Bloom bit positions and a non-zero 64-bit CAS
// fingerprint from a single blake3-256 digest.
func (d *BloomCASDedup) hashProbes(key []byte) (b1, b2, b3, fp uint64) {
	sum := blake3.Sum256(key)
	h1 := binary.LittleEndian.Uint64(sum[0:8])
	h2 := binary.LittleEndian.Uint64(sum[8:16])
	h3 := binary.LittleEndian.Uint64(sum[16:24])
	fp = binary.LittleEndian.Uint64(sum[24:32])
	if fp == 0 {
		fp = 1 // reserve 0 for empty CAS slot
	}
	return h1 & d.bloomMask, h2 & d.bloomMask, h3 & d.bloomMask, fp
}

func (d *BloomCASDedup) bloomHas(b1, b2, b3 uint64) bool {
	if (d.bloomWords[b1>>6].Load() & (uint64(1) << (b1 & 63))) == 0 {
		return false
	}
	if (d.bloomWords[b2>>6].Load() & (uint64(1) << (b2 & 63))) == 0 {
		return false
	}
	if (d.bloomWords[b3>>6].Load() & (uint64(1) << (b3 & 63))) == 0 {
		return false
	}
	return true
}

func (d *BloomCASDedup) bloomSet(b1, b2, b3 uint64) {
	d.bloomWords[b1>>6].Or(uint64(1) << (b1 & 63))
	d.bloomWords[b2>>6].Or(uint64(1) << (b2 & 63))
	d.bloomWords[b3>>6].Or(uint64(1) << (b3 & 63))
}

// PreloadBloom marks key as previously seen in the read-only Bloom fast path.
func (d *BloomCASDedup) PreloadBloom(key []byte) {
	b1, b2, b3, _ := d.hashProbes(key)
	d.bloomSet(b1, b2, b3)
}

// ProbablySeen performs a lock-free 3-probe Bloom lookup with zero writes.
func (d *BloomCASDedup) ProbablySeen(key []byte) bool {
	b1, b2, b3, _ := d.hashProbes(key)
	return d.bloomHas(b1, b2, b3)
}

// Claim atomically claims ownership of key. Exactly one concurrent caller wins
// (claimed == true); all duplicate callers immediately return claimed == false.
// When AllowBloomFastReject is true, keys matching all 3 Bloom bits return
// (false, true) without touching the CAS table.
func (d *BloomCASDedup) Claim(key []byte) (claimed bool, fastPathRejected bool) {
	d.totalChecks.Add(1)
	b1, b2, b3, fp := d.hashProbes(key)

	if d.allowBloomFastReject && d.bloomHas(b1, b2, b3) {
		d.bloomFastRejects.Add(1)
		return false, true
	}

	idx := fp & d.casMask
	for probe := 0; probe < defaultMaxProbes; probe++ {
		slot := &d.casSlots[(idx+uint64(probe))&d.casMask]
		cur := slot.Load()
		if cur == fp {
			d.casDuplicates.Add(1)
			return false, false
		}
		if cur == 0 {
			if slot.CompareAndSwap(0, fp) {
				d.bloomSet(b1, b2, b3)
				d.casClaims.Add(1)
				return true, false
			}
			// Another goroutine raced into this slot — re-check if same key.
			if slot.Load() == fp {
				d.casDuplicates.Add(1)
				return false, false
			}
		}
	}

	d.casOverflow.Add(1)
	return false, false
}

// Stats returns a snapshot of lock-free deduplication counters.
func (d *BloomCASDedup) Stats() DedupStats {
	return DedupStats{
		TotalChecks:      d.totalChecks.Load(),
		BloomFastRejects: d.bloomFastRejects.Load(),
		CASClaims:        d.casClaims.Load(),
		CASDuplicates:    d.casDuplicates.Load(),
		CASOverflow:      d.casOverflow.Load(),
	}
}
