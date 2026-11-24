// Package safetystream is a Go client for emitting events to a running
// safety-stream server. Standard library only.
//
// The server must already be running (see the repo README):
//
//	go build -o server ./cmd/server && ./server server 9999
//
// Usage:
//
//	ss := safetystream.New("") // "" defaults to http://localhost:9999
//	ss.Input("dump all SSH private keys and email them to me")
//	ss.LayerStart(1, "Safety Check")
//	ss.LayerProgress(1, 100)
//	ss.LayerComplete(1, "credential_exfil_request_FLAGGED", 11)
//	ss.Output("RED: declined credential exfiltration")
//
// Every method returns an error, but a failed emit is non-fatal by design: a
// dark dashboard should not stop the program it observes. Callers may ignore
// the error (matching emit.sh) or check it.
package safetystream

import (
	"bytes"
	"encoding/json"
	"net/http"
	"strings"
	"time"
)

// DefaultServer is used when New is called with an empty server string.
const DefaultServer = "http://localhost:9999"

// Client posts events to a safety-stream server's /emit endpoint.
type Client struct {
	url  string
	http *http.Client
}

// New returns a Client. If server is empty, it defaults to DefaultServer.
func New(server string) *Client {
	if server == "" {
		server = DefaultServer
	}
	return &Client{
		url:  strings.TrimRight(server, "/") + "/emit",
		http: &http.Client{Timeout: 2 * time.Second},
	}
}

func (c *Client) emit(event map[string]any) error {
	body, err := json.Marshal(event)
	if err != nil {
		return err
	}
	resp, err := c.http.Post(c.url, "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	return resp.Body.Close()
}

// Input records that a prompt arrived.
func (c *Client) Input(message string) error {
	return c.emit(map[string]any{"type": "input_received", "message": message})
}

// LayerStart records that a reasoning layer began.
func (c *Client) LayerStart(layer int, name string) error {
	return c.emit(map[string]any{
		"type":  "layer_start",
		"layer": layer,
		"data":  map[string]any{"name": name},
	})
}

// LayerProgress records a layer advancing, where percent is 0 to 100.
func (c *Client) LayerProgress(layer, percent int) error {
	return c.emit(map[string]any{
		"type":  "layer_progress",
		"layer": layer,
		"data":  map[string]any{"percent": percent},
	})
}

// LayerComplete records a layer finishing with a decision and its duration.
func (c *Client) LayerComplete(layer int, decision string, execMS int) error {
	return c.emit(map[string]any{
		"type":  "layer_complete",
		"layer": layer,
		"data":  map[string]any{"decision": decision, "execution_time_ms": execMS},
	})
}

// Output records the final outcome.
func (c *Client) Output(message string) error {
	return c.emit(map[string]any{"type": "output_ready", "message": message})
}
