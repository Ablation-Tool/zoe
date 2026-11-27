package cas

import (
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
)

func TestBloomCASDedupExactSingleWinner1000Workers(t *testing.T) {
	d := NewBloomCASDedup(BloomCASConfig{
		BloomBits:            1 << 18, // 32 KiB test filter
		CASSlots:             1 << 14, // 16,384 slots
		AllowBloomFastReject: false,   // exact CAS mode
	})

	const numKeys = 200
	const workers = 1000

	var wins [numKeys]atomic.Int32
	var wg sync.WaitGroup
	wg.Add(workers)
	for w := 0; w < workers; w++ {
		go func(workerID int) {
			defer wg.Done()
			for k := 0; k < numKeys; k++ {
				key := []byte(fmt.Sprintf("10.0.%d.%d:8080", (k+workerID)%10, k))
				// Normalize to shared 200-key pool so all 1000 workers collide heavily
				sharedKey := []byte(fmt.Sprintf("10.0.0.%d:443", k))
				_ = key
				if claimed, fastRej := d.Claim(sharedKey); claimed {
					if fastRej {
						t.Errorf("unexpected fastPathRejected on claimed key")
					}
					wins[k].Add(1)
				}
			}
		}(w)
	}
	wg.Wait()

	for k := 0; k < numKeys; k++ {
		if got := wins[k].Load(); got != 1 {
			t.Fatalf("key %d claimed %d times; want exactly 1", k, got)
		}
		if !d.ProbablySeen([]byte(fmt.Sprintf("10.0.0.%d:443", k))) {
			t.Fatalf("key %d missing from Bloom filter after claim", k)
		}
	}

	st := d.Stats()
	if st.CASClaims != numKeys {
		t.Fatalf("CASClaims=%d want %d", st.CASClaims, numKeys)
	}
	if st.CASDuplicates != uint64(workers*numKeys-numKeys) {
		t.Fatalf("CASDuplicates=%d want %d", st.CASDuplicates, workers*numKeys-numKeys)
	}
}

func TestBloomCASDedupFastPathRejectsPreloaded(t *testing.T) {
	d := NewBloomCASDedup(BloomCASConfig{
		BloomBits:            1 << 20, // 128 KiB filter (<0.01% FP for 500 items)
		CASSlots:             1 << 12,
		AllowBloomFastReject: true,
	})

	for i := 0; i < 500; i++ {
		d.PreloadBloom([]byte(fmt.Sprintf("192.168.1.%d:22", i)))
	}

	for i := 0; i < 500; i++ {
		claimed, fastRej := d.Claim([]byte(fmt.Sprintf("192.168.1.%d:22", i)))
		if claimed || !fastRej {
			t.Fatalf("preloaded key %d: claimed=%v fastRej=%v; want false, true", i, claimed, fastRej)
		}
	}

	// Brand-new key should pass Bloom and win CAS claim
	claimed, fastRej := d.Claim([]byte("203.0.113.99:9000"))
	if !claimed || fastRej {
		t.Fatalf("new key: claimed=%v fastRej=%v; want true, false", claimed, fastRej)
	}

	st := d.Stats()
	if st.BloomFastRejects != 500 || st.CASClaims != 1 {
		t.Fatalf("unexpected stats: %+v", st)
	}
}
