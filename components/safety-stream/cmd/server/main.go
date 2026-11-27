package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"sync"
	"time"
)

type RealEvent struct {
	Type      string                 `json:"type"`
	Timestamp int64                  `json:"timestamp"`
	Layer     int                    `json:"layer,omitempty"`
	Message   string                 `json:"message,omitempty"`
	Data      map[string]interface{} `json:"data,omitempty"`
}

type EventServer struct {
	listeners map[string]chan RealEvent
	mu        sync.RWMutex
	port      string
}

func NewEventServer(port string) *EventServer {
	return &EventServer{
		listeners: make(map[string]chan RealEvent),
		port:      port,
	}
}

func (es *EventServer) RegisterListener(id string) chan RealEvent {
	es.mu.Lock()
	defer es.mu.Unlock()
	ch := make(chan RealEvent, 100)
	es.listeners[id] = ch
	return ch
}

func (es *EventServer) BroadcastEvent(e RealEvent) {
	e.Timestamp = time.Now().UnixMilli()
	es.mu.RLock()
	defer es.mu.RUnlock()
	for _, ch := range es.listeners {
		select {
		case ch <- e:
		default:
			// Non-blocking send
		}
	}
}

func (es *EventServer) HandleEmit(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var e RealEvent
	if err := json.NewDecoder(r.Body).Decode(&e); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	es.BroadcastEvent(e)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "emitted"})
}

func (es *EventServer) HandleStream(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if id == "" {
		id = fmt.Sprintf("client-%d", time.Now().UnixNano())
	}

	ch := es.RegisterListener(id)
	defer func() {
		es.mu.Lock()
		delete(es.listeners, id)
		es.mu.Unlock()
		close(ch)
	}()

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	for {
		select {
		case e, ok := <-ch:
			if !ok {
				return
			}
			data, _ := json.Marshal(e)
			fmt.Fprintf(w, "data: %s\n\n", string(data))
			flusher.Flush()

		case <-r.Context().Done():
			return

		case <-time.After(30 * time.Second):
			// Keep-alive
			fmt.Fprintf(w, ": keepalive\n\n")
			flusher.Flush()
		}
	}
}

func (es *EventServer) Start() {
	http.HandleFunc("/emit", es.HandleEmit)
	http.HandleFunc("/stream", es.HandleStream)
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})
	http.HandleFunc("/", es.HandleDashboard)

	fmt.Printf("Event server listening on http://localhost:%s  (open in a browser for the live dashboard)\n", es.port)
	if err := http.ListenAndServe(":"+es.port, nil); err != nil {
		fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
		os.Exit(1)
	}
}

// HandleDashboard serves a same-origin browser view of the live SSE stream.
func (es *EventServer) HandleDashboard(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, dashboardHTML)
}

const dashboardHTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Safety Stream</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; background:#0b0f14; color:#cfe3ec; }
  header { padding:12px 18px; border-bottom:1px solid #1c2733; display:flex; align-items:center; gap:12px; }
  header h1 { font-size:15px; margin:0; color:#e8f3f8; letter-spacing:.12em; }
  #status { font-size:12px; padding:2px 8px; border-radius:10px; }
  .up { background:#0d3320; color:#5ee08a; } .down { background:#3a1620; color:#ff7a93; }
  #feed { padding:10px 18px; }
  .ev { padding:6px 10px; margin:4px 0; border-left:3px solid #2a3a49; background:#0e151d; border-radius:0 6px 6px 0; }
  .t { color:#5b7488; font-size:11px; }
  .input { border-left-color:#4aa3df; } .output { border-left-color:#9b7ad6; }
  .start { border-left-color:#e0a84a; } .progress { border-left-color:#3a4a59; }
  .complete { border-left-color:#5ee08a; }
  .lyr { color:#8fb6cc; font-weight:600; } .dec { color:#5ee08a; } .msg { color:#cfe3ec; }
  .bar { height:4px; background:#1c2733; border-radius:2px; margin-top:4px; overflow:hidden; }
  .bar > i { display:block; height:100%; background:#4aa3df; width:0; transition:width .2s; }
  .empty { color:#5b7488; padding:20px 0; }
</style>
</head>
<body>
<header>
  <h1>SAFETY STREAM</h1>
  <span id="status" class="down">connecting...</span>
  <span class="t" id="count">0 events</span>
</header>
<div id="feed"><div class="empty">waiting for the model to emit reasoning...</div></div>
<script>
  var feed=document.getElementById('feed'), statusEl=document.getElementById('status'), countEl=document.getElementById('count');
  var n=0, cleared=false;
  function ts(ms){ var d=ms?new Date(ms):new Date(); return d.toLocaleTimeString(); }
  function esc(s){ var p=document.createElement('span'); p.textContent=(s==null?'':String(s)); return p.innerHTML; }
  function add(cls, html){
    if(!cleared){ feed.innerHTML=''; cleared=true; }
    var div=document.createElement('div'); div.className='ev '+cls; div.innerHTML=html;
    feed.insertBefore(div, feed.firstChild);
    n++; countEl.textContent=n+' events';
  }
  var es=new EventSource('/stream');
  es.onopen=function(){ statusEl.textContent='live'; statusEl.className='up'; };
  es.onerror=function(){ statusEl.textContent='disconnected'; statusEl.className='down'; };
  es.onmessage=function(m){
    var e; try{ e=JSON.parse(m.data); }catch(_){ return; }
    var time='<span class="t">'+ts(e.timestamp)+'</span> ', d=e.data||{};
    if(e.type==='input_received') add('input', time+'<span class="msg">INPUT: '+esc(e.message)+'</span>');
    else if(e.type==='layer_start') add('start', time+'<span class="lyr">L'+esc(e.layer)+' start</span> '+esc(d.name));
    else if(e.type==='layer_progress') add('progress', time+'<span class="lyr">L'+esc(e.layer)+'</span> '+esc(d.percent)+'%<div class="bar"><i style="width:'+esc(d.percent)+'%"></i></div>');
    else if(e.type==='layer_complete') add('complete', time+'<span class="lyr">L'+esc(e.layer)+' complete</span> <span class="dec">'+esc(d.decision)+'</span>'+(d.execution_time_ms?(' <span class="t">'+esc(d.execution_time_ms)+'ms</span>'):''));
    else if(e.type==='output_ready') add('output', time+'<span class="msg">OUTPUT: '+esc(e.message)+'</span>');
    else add('', time+esc(e.type)+' '+esc(e.message||''));
  };
</script>
</body>
</html>`

func main() {
	if len(os.Args) > 1 && os.Args[1] == "server" {
		port := "9999"
		if len(os.Args) > 2 {
			port = os.Args[2]
		}
		server := NewEventServer(port)
		server.Start()
		return
	}

	// CLI mode: listen to stdin and emit events
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		var e RealEvent
		if err := json.Unmarshal([]byte(line), &e); err != nil {
			fmt.Fprintf(os.Stderr, "Invalid JSON: %v\n", err)
			continue
		}

		// Connect and emit
		conn, err := net.Dial("tcp", "localhost:9999")
		if err != nil {
			fmt.Fprintf(os.Stderr, "Cannot connect to server: %v\n", err)
			continue
		}

		data, _ := json.Marshal(e)
		req := fmt.Sprintf("POST /emit HTTP/1.1\r\nHost: localhost\r\nContent-Length: %d\r\n\r\n%s",
			len(data), string(data))

		conn.Write([]byte(req))
		conn.Close()
	}
}
