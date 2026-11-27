// Package ingest reads observations from the source adapters' common output
// format (JSON lines) into the unified observation stream that fuse consumes.
// The source-specific extractors - empire.db (Shodan/JAXEN), the Censys sweep,
// and nuclide.db - each emit this format; LoadJSONL is the single reader they
// all feed, which keeps the source-specific glue thin and this path tested once.
package ingest

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/nuclide-research/VisorCAS/normalize"
)

// LoadJSONL reads a JSON-lines file where each non-blank line is one observation
// (a normalize.Response). Blank lines are skipped; a malformed line is a hard
// error naming the file and line number.
func LoadJSONL(path string) ([]normalize.Response, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var out []normalize.Response
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 8*1024*1024) // tolerate large response bodies
	line := 0
	for sc.Scan() {
		line++
		text := strings.TrimSpace(sc.Text())
		if text == "" {
			continue
		}
		var r normalize.Response
		if err := json.Unmarshal([]byte(text), &r); err != nil {
			return nil, fmt.Errorf("ingest: %s line %d: %w", path, line, err)
		}
		out = append(out, r)
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	return out, nil
}
