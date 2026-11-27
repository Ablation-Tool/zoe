package main

import (
	"embed"
	"os"

	"github.com/nuclide-research/VisorScuba/cmd"
	"github.com/nuclide-research/VisorScuba/engine"
)

//go:embed all:rego
var regoFS embed.FS

func main() {
	engine.RegoFS = regoFS
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
