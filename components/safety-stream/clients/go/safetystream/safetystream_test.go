package safetystream

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
)

// TestEmitShapes pins the exact JSON each method posts, against the schema the
// README documents. A client that drifts from the wire format fails here.
func TestEmitShapes(t *testing.T) {
	var got map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		got = map[string]any{}
		_ = json.Unmarshal(body, &got)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	c := New(srv.URL)

	cases := []struct {
		name string
		call func() error
		want map[string]any
	}{
		{
			"input",
			func() error { return c.Input("hi") },
			map[string]any{"type": "input_received", "message": "hi"},
		},
		{
			"layer_start",
			func() error { return c.LayerStart(1, "Safety Check") },
			map[string]any{"type": "layer_start", "layer": float64(1), "data": map[string]any{"name": "Safety Check"}},
		},
		{
			"layer_progress",
			func() error { return c.LayerProgress(1, 100) },
			map[string]any{"type": "layer_progress", "layer": float64(1), "data": map[string]any{"percent": float64(100)}},
		},
		{
			"layer_complete",
			func() error { return c.LayerComplete(1, "credential_exfil_request_FLAGGED", 11) },
			map[string]any{"type": "layer_complete", "layer": float64(1), "data": map[string]any{"decision": "credential_exfil_request_FLAGGED", "execution_time_ms": float64(11)}},
		},
		{
			"output",
			func() error { return c.Output("RED: declined") },
			map[string]any{"type": "output_ready", "message": "RED: declined"},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if err := tc.call(); err != nil {
				t.Fatalf("emit returned error: %v", err)
			}
			if !reflect.DeepEqual(got, tc.want) {
				t.Errorf("wrong wire JSON\n got:  %v\n want: %v", got, tc.want)
			}
		})
	}
}

// TestNewDefault confirms the empty server string falls back to DefaultServer.
func TestNewDefault(t *testing.T) {
	if got := New("").url; got != DefaultServer+"/emit" {
		t.Errorf("default url = %q, want %q", got, DefaultServer+"/emit")
	}
}

// TestTrailingSlash confirms a server URL with a trailing slash is handled.
func TestTrailingSlash(t *testing.T) {
	if got := New("http://x:1/").url; got != "http://x:1/emit" {
		t.Errorf("url = %q, want http://x:1/emit", got)
	}
}
