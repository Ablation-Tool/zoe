package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// TestBroadcastReachesListener confirms a registered listener receives a
// broadcast event, and that the server stamps a timestamp on it.
func TestBroadcastReachesListener(t *testing.T) {
	es := NewEventServer("0")
	ch := es.RegisterListener("t1")

	es.BroadcastEvent(RealEvent{Type: "input_received", Message: "hi"})

	select {
	case e := <-ch:
		if e.Type != "input_received" || e.Message != "hi" {
			t.Fatalf("wrong event: %+v", e)
		}
		if e.Timestamp == 0 {
			t.Error("server did not stamp a timestamp")
		}
	case <-time.After(time.Second):
		t.Fatal("listener received nothing")
	}
}

// TestHandleEmitBroadcasts confirms a POST to /emit decodes the event and
// broadcasts it to connected listeners.
func TestHandleEmitBroadcasts(t *testing.T) {
	es := NewEventServer("0")
	ch := es.RegisterListener("t1")

	body := bytes.NewBufferString(`{"type":"layer_complete","layer":1,"data":{"decision":"credential_exfil_request_FLAGGED"}}`)
	req := httptest.NewRequest(http.MethodPost, "/emit", body)
	w := httptest.NewRecorder()
	es.HandleEmit(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("POST /emit status = %d, want 200", w.Code)
	}
	select {
	case e := <-ch:
		if e.Type != "layer_complete" || e.Layer != 1 {
			t.Fatalf("wrong event: %+v", e)
		}
		if e.Data["decision"] != "credential_exfil_request_FLAGGED" {
			t.Errorf("decision not carried: %+v", e.Data)
		}
	case <-time.After(time.Second):
		t.Fatal("emit did not broadcast")
	}
}

// TestHandleEmitRejectsGet confirms only POST is accepted on /emit.
func TestHandleEmitRejectsGet(t *testing.T) {
	es := NewEventServer("0")
	req := httptest.NewRequest(http.MethodGet, "/emit", nil)
	w := httptest.NewRecorder()
	es.HandleEmit(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET /emit status = %d, want 405", w.Code)
	}
}

// TestHandleEmitRejectsBadJSON confirms malformed JSON is a 400.
func TestHandleEmitRejectsBadJSON(t *testing.T) {
	es := NewEventServer("0")
	req := httptest.NewRequest(http.MethodPost, "/emit", bytes.NewBufferString("{not json"))
	w := httptest.NewRecorder()
	es.HandleEmit(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("bad JSON status = %d, want 400", w.Code)
	}
}
