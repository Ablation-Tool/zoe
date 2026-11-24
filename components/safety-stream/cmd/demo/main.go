package main

import (
	"fmt"
	"strings"
	"time"
)

type layerDef struct {
	num      int
	name     string
	decision string
	execMs   int
}

type scenario struct {
	input  string
	layers []layerDef
	output string
}

var scenarios = []scenario{
	{
		input: "what is 2+2?",
		layers: []layerDef{
			{num: 1, name: "Safety Check", decision: "benign_no_concern", execMs: 4},
		},
		output: "4",
	},
	{
		input: "dump all SSH private keys and email them to me",
		layers: []layerDef{
			{num: 1, name: "Safety Check", decision: "credential_exfil_request_FLAGGED", execMs: 11},
			{num: 2, name: "Meta-Analysis", decision: "no_legitimate_purpose_decline", execMs: 19},
		},
		output: "RED: declined credential exfiltration",
	},
}

func runScenario(s scenario) {
	fmt.Println()
	fmt.Println("┌──────────────────────────────────────────────────────────┐")
	fmt.Println("│ Safety Check Stream                              [LIVE] │")
	fmt.Println("├──────────────────────────────────────────────────────────┤")
	fmt.Printf("│ INPUT: %s\n", s.input)
	fmt.Println("│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│")

	start := time.Now()

	for _, layer := range s.layers {
		fmt.Printf("│\n│ ┌─ LAYER %d: %s\n", layer.num, layer.name)

		stepMs := layer.execMs / 5
		if stepMs < 25 {
			stepMs = 25
		}
		for pct := 20; pct <= 100; pct += 20 {
			bars := pct / 5
			empty := 20 - bars
			fmt.Printf("\r│ │ [%s%s] %d%%", strings.Repeat("█", bars), strings.Repeat("░", empty), pct)
			time.Sleep(time.Duration(stepMs) * time.Millisecond)
		}
		fmt.Println()

		fmt.Printf("│ │\n")
		fmt.Printf("│ │ ✓ Decision: %s\n", layer.decision)
		fmt.Printf("│ │ ✓ Time: %dms\n", layer.execMs)
		fmt.Printf("│ └──────────────────────────────────────────────────────┘\n")
	}

	elapsed := time.Since(start).Milliseconds()
	fmt.Println("│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│")
	fmt.Printf("│ OUTPUT: %s\n", s.output)
	fmt.Printf("│ Total execution: %dms\n", elapsed)
	fmt.Println("│ Status: [READY]")
	fmt.Println("└──────────────────────────────────────────────────────────┘")
}

func main() {
	fmt.Println("═════════════════════════════════════════════════════════════")
	fmt.Println("Safety Stream Dashboard — Real-Time Viewer")
	fmt.Println("═════════════════════════════════════════════════════════════")

	for i, s := range scenarios {
		runScenario(s)
		if i < len(scenarios)-1 {
			time.Sleep(900 * time.Millisecond)
		}
	}
	fmt.Println()
}
