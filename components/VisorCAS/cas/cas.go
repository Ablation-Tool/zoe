// Package cas is a content-addressed blob store: a blob's address is the blake3
// hash of its bytes. Identical content collapses to a single stored object
// (deduplication), and every read re-verifies the hash (integrity). It is the
// immutable substrate under the VisorCAS false-positive ledger: the dedup spine
// that makes 500 identical false positives cost one entry, not 500 rows.
package cas

import (
	"fmt"
	"os"
	"path/filepath"

	"lukechampine.com/blake3"
)

// Store is a sharded, content-addressed blob store rooted at a directory.
type Store struct{ root string }

// Open returns a Store rooted at dir, creating the directory if necessary.
func Open(root string) (*Store, error) {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return nil, err
	}
	return &Store{root: root}, nil
}

// hash is the hex blake3-256 digest of data - the content address.
func hash(data []byte) string {
	sum := blake3.Sum256(data)
	return fmt.Sprintf("%x", sum)
}

// Hash returns the content address of data without storing it: the same hex
// blake3-256 digest Put would store it under. Used by the fusion pre-screen to
// look a fingerprint up in the ledger before deciding whether to verify it.
func Hash(data []byte) string { return hash(data) }

// path is the sharded on-disk location for a digest: <root>/<first two>/<rest>.
// Sharding by prefix keeps any single directory from holding millions of files.
func (s *Store) path(digest string) string {
	return filepath.Join(s.root, digest[:2], digest[2:])
}

// Put stores data and returns its content address. Identical content already on
// disk is a no-op (dedup). Writes are atomic: temp file then rename.
func (s *Store) Put(data []byte) (string, error) {
	digest := hash(data)
	p := s.path(digest)
	if _, err := os.Stat(p); err == nil {
		return digest, nil // already stored
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return "", err
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, p); err != nil {
		return "", err
	}
	return digest, nil
}

// Get returns the blob at digest, verifying integrity on read. A blob whose
// bytes no longer hash to its address is rejected rather than returned.
func (s *Store) Get(digest string) ([]byte, error) {
	data, err := os.ReadFile(s.path(digest))
	if err != nil {
		return nil, err
	}
	if got := hash(data); got != digest {
		return nil, fmt.Errorf("cas: integrity check failed for %s: stored bytes hash to %s", digest, got)
	}
	return data, nil
}

// Has reports whether a blob with the given digest is stored.
func (s *Store) Has(digest string) bool {
	if len(digest) < 3 {
		return false
	}
	_, err := os.Stat(s.path(digest))
	return err == nil
}
