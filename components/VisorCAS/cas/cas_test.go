package cas

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPutGetRoundTrip(t *testing.T) {
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	data := []byte(`{"signature":"vllm","status":200}`)
	h, err := s.Put(data)
	if err != nil {
		t.Fatal(err)
	}
	got, err := s.Get(h)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(data) {
		t.Fatalf("round-trip mismatch: got %q want %q", got, data)
	}
}

// Identical content must produce one hash and exactly one stored blob.
func TestPutIsDeterministicAndDeduplicates(t *testing.T) {
	root := t.TempDir()
	s, _ := Open(root)
	data := []byte("same content stored twice")

	h1, _ := s.Put(data)
	h2, _ := s.Put(data)
	if h1 != h2 {
		t.Fatalf("same content produced different hashes: %s vs %s", h1, h2)
	}

	blobs := 0
	_ = filepath.WalkDir(root, func(_ string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() {
			blobs++
		}
		return nil
	})
	if blobs != 1 {
		t.Fatalf("expected 1 deduplicated blob on disk, found %d", blobs)
	}
}

func TestHasReflectsStorage(t *testing.T) {
	s, _ := Open(t.TempDir())
	if s.Has("00deadbeef") {
		t.Fatal("Has returned true for an absent hash")
	}
	h, _ := s.Put([]byte("present"))
	if !s.Has(h) {
		t.Fatal("Has returned false right after Put")
	}
}

func TestGetUnknownHashErrors(t *testing.T) {
	s, _ := Open(t.TempDir())
	if _, err := s.Get("deadbeefdeadbeef"); err == nil {
		t.Fatal("expected an error getting an unknown hash")
	}
}

// A blob whose bytes no longer hash to its address must be rejected on read.
func TestGetDetectsCorruption(t *testing.T) {
	root := t.TempDir()
	s, _ := Open(root)
	h, _ := s.Put([]byte("trustworthy bytes"))

	tampered := filepath.Join(root, h[:2], h[2:])
	if err := os.WriteFile(tampered, []byte("tampered bytes!!"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Get(h); err == nil {
		t.Fatal("expected an integrity error reading a corrupted blob")
	}
}

func TestShardedLayout(t *testing.T) {
	root := t.TempDir()
	s, _ := Open(root)
	h, _ := s.Put([]byte("shard me"))

	want := filepath.Join(root, h[:2], h[2:])
	if _, err := os.Stat(want); err != nil {
		t.Fatalf("expected blob at sharded path %s: %v", want, err)
	}
}

// Hash must agree with the address Put stores under, so a caller (e.g. the
// fusion pre-screen) can compute a content address without writing and later
// find the same blob.
func TestHashMatchesPut(t *testing.T) {
	s, _ := Open(t.TempDir())
	data := []byte("address me identically")
	stored, _ := s.Put(data)
	if Hash(data) != stored {
		t.Fatalf("Hash=%s but Put stored under %s", Hash(data), stored)
	}
}
