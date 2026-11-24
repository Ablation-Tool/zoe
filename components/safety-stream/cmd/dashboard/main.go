package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

type DashboardEvent struct {
	Type      string                 `json:"type"`
	Timestamp int64                  `json:"timestamp"`
	Layer     int                    `json:"layer"`
	Message   string                 `json:"message"`
	Data      map[string]interface{} `json:"data"`
}

func main() {
	serverAddr := flag.String("server", "http://localhost:9999", "Event server address")
	flag.Parse()

	fmt.Println("═════════════════════════════════════════════════════════════")
	fmt.Println("Safety Stream Dashboard — Real-Time Viewer")
	fmt.Println("═════════════════════════════════════════════════════════════")
	fmt.Println()
	fmt.Printf("Connecting to %s/stream\n\n", *serverAddr)

	resp, err := http.Get(*serverAddr + "/stream?id=dashboard-" + fmt.Sprintf("%d", time.Now().UnixNano()))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Connection failed: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	var currentInput string
	var startTime time.Time

	for scanner.Scan() {
		line := scanner.Text()

		// Parse SSE format
		if !strings.HasPrefix(line, "data: ") {
			continue
		}

		data := strings.TrimPrefix(line, "data: ")
		var e DashboardEvent
		if err := json.Unmarshal([]byte(data), &e); err != nil {
			continue
		}

		switch e.Type {
		case "input_received":
			currentInput = e.Message
			startTime = time.Now()
			fmt.Println()
			fmt.Println("┌──────────────────────────────────────────────────────────┐")
			fmt.Println("│ Safety Check Stream                              [LIVE] │")
			fmt.Println("├──────────────────────────────────────────────────────────┤")
			fmt.Printf("│ INPUT: %s\n", truncate(currentInput, 55))
			fmt.Println("│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│")

		case "layer_start":
			fmt.Printf("│\n│ ┌─ LAYER %d: %v\n", e.Layer, e.Data["name"])

		case "layer_progress":
			if percent, ok := e.Data["percent"].(float64); ok {
				p := int(percent)
				bars := (p / 5)
				empty := 20 - bars
				fmt.Printf("│ │ [%s%s] %d%%\n", strings.Repeat("█", bars), strings.Repeat("░", empty), p)
			}

		case "layer_complete":
			fmt.Printf("│ │\n")
			fmt.Printf("│ │ ✓ Decision: %v\n", e.Data["decision"])
			if execTime, ok := e.Data["execution_time_ms"]; ok {
				fmt.Printf("│ │ ✓ Time: %vms\n", execTime)
			}
			if biases, ok := e.Data["biases_detected"]; ok && biases != 0 {
				fmt.Printf("│ │ ✓ Biases detected: %v\n", biases)
			}
			if corrections, ok := e.Data["corrections_made"]; ok && corrections != 0 {
				fmt.Printf("│ │ ✓ Corrections: %v\n", corrections)
			}
			if questions, ok := e.Data["questions_asked"]; ok {
				fmt.Printf("│ │ ✓ Questions: %v\n", questions)
			}
			fmt.Printf("│ └──────────────────────────────────────────────────────┘\n")

		case "output_ready":
			elapsed := time.Since(startTime).Milliseconds()
			fmt.Println("│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│")
			fmt.Printf("│ OUTPUT: %s\n", truncate(e.Message, 55))
			fmt.Printf("│ Total execution: %dms\n", elapsed)
			fmt.Println("│ Status: [READY]")
			fmt.Println("└──────────────────────────────────────────────────────────┘")
		}
	}
}

func truncate(s string, length int) string {
	if len(s) > length {
		return s[:length-3] + "..."
	}
	return s
}
