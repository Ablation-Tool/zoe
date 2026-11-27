// Command visorcas is the CLI over the VisorCAS false-positive ledger. It wires
// the tested packages - ingest, fuse, normalize, cas, ledger - into four verbs:
//
//	record   store a verified false positive
//	query    show a stored pattern
//	fuse     fuse multi-source observations, screen known FPs, rank survivors
//	stats    ledger summary
//
// All the logic lives in the packages; this file is orchestration and output.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/spf13/cobra"

	"github.com/nuclide-research/VisorCAS/adapters"
	"github.com/nuclide-research/VisorCAS/fuse"
	"github.com/nuclide-research/VisorCAS/gate"
	"github.com/nuclide-research/VisorCAS/ingest"
	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
	"github.com/nuclide-research/VisorCAS/screen"
)

var dir string

func main() {
	root := &cobra.Command{
		Use:           "visorcas",
		Short:         "Content-addressed false-positive ledger for AI-infra surveys",
		Version:       "0.1.0",
		SilenceUsage:  true,
		SilenceErrors: true,
	}
	root.PersistentFlags().StringVar(&dir, "dir", "./visorcas-data", "ledger data directory")
	root.AddCommand(recordCmd(), queryCmd(), reclassifyCmd(), fuseCmd(), gateCmd(), importCmd(), screenCmd(), statsCmd())
	if err := root.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func recordCmd() *cobra.Command {
	var input, disp, category, rootfix, survey string
	c := &cobra.Command{
		Use:   "record",
		Short: "Record a verified false positive (observation JSON via -i or stdin)",
		RunE: func(_ *cobra.Command, _ []string) error {
			raw, err := readInput(input)
			if err != nil {
				return err
			}
			var r normalize.Response
			if err := json.Unmarshal(raw, &r); err != nil {
				return fmt.Errorf("parsing observation: %w", err)
			}
			l, err := ledger.Open(dir)
			if err != nil {
				return err
			}
			defer l.Close()
			h, err := l.Record(ledger.Finding{
				Response:    r,
				Disposition: ledger.Disposition(disp),
				Category:    category,
				RootFix:     rootfix,
				SurveyCtx:   survey,
			})
			if err != nil {
				return err
			}
			fmt.Println(h)
			return nil
		},
	}
	c.Flags().StringVarP(&input, "in", "i", "", "observation JSON file (default stdin)")
	c.Flags().StringVar(&disp, "disposition", "", "misidentification|transient-artifact|auth-on|deception|tool-bug")
	c.Flags().StringVar(&category, "category", "", "finer label (optional)")
	c.Flags().StringVar(&rootfix, "rootfix", "", "upstream fix that would stop this FP (optional)")
	c.Flags().StringVar(&survey, "survey", "", "survey or category context")
	_ = c.MarkFlagRequired("disposition")
	return c
}

func queryCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "query <fp_hash>",
		Short: "Show a stored false-positive pattern",
		Args:  cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			l, err := ledger.Open(dir)
			if err != nil {
				return err
			}
			defer l.Close()
			p, err := l.Pattern(args[0])
			if err != nil {
				return fmt.Errorf("pattern %s: %w", args[0], err)
			}
			fmt.Printf("hash:        %s\n", p.Hash)
			fmt.Printf("disposition: %s (excludable=%v)\n", p.Disposition, p.Disposition.Excludable())
			fmt.Printf("category:    %s\n", p.Category)
			fmt.Printf("root_fix:    %s\n", p.RootFix)
			fmt.Printf("first_seen:  %s\n", p.FirstSeen.Format(time.RFC3339))
			fmt.Printf("hit_count:   %d\n", p.HitCount)
			fmt.Printf("occurrences: %d\n", l.OccurrenceCount(p.Hash))
			if hist, _ := l.History(p.Hash); len(hist) > 0 {
				fmt.Println("history:")
				for _, h := range hist {
					fmt.Printf("  %s  %s -> %s  %s\n", h.At.Format(time.RFC3339), h.From, h.To, h.Reason)
				}
			}
			return nil
		},
	}
}

func fuseCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "fuse <observations.jsonl>",
		Short: "Fuse multi-source observations, screen known FPs, rank survivors",
		Args:  cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			obs, err := ingest.LoadJSONL(args[0])
			if err != nil {
				return err
			}
			l, err := ledger.Open(dir)
			if err != nil {
				return err
			}
			defer l.Close()

			cands := fuse.Fuse(obs)
			survivors, skipped := fuse.Screen(cands, func(h string) bool {
				p, err := l.Pattern(h)
				return err == nil && p.Disposition.Excludable()
			})
			ranked := fuse.Rank(survivors)

			w := tabwriter.NewWriter(os.Stdout, 0, 2, 2, ' ', 0)
			fmt.Fprintln(w, "IP\tIDENT\tLIVE\tDIVERGENT\tSOURCES\tFP_HASH")
			for _, c := range ranked {
				fmt.Fprintf(w, "%s\t%d\t%d\t%v\t%s\t%s\n",
					c.IP, c.Agreement, c.LivenessAgreement, c.Divergent, strings.Join(c.Sources, ","), short(c.FPHash))
			}
			w.Flush()
			patterns := map[string]bool{}
			for _, c := range cands {
				patterns[c.FPHash] = true
			}
			fmt.Printf("\n%d hosts, %d distinct patterns: %d to verify, %d skipped (known excludable FPs)\n",
				len(cands), len(patterns), len(survivors), len(skipped))
			return nil
		},
	}
}

func statsCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "stats",
		Short: "Ledger summary",
		RunE: func(_ *cobra.Command, _ []string) error {
			l, err := ledger.Open(dir)
			if err != nil {
				return err
			}
			defer l.Close()
			fmt.Printf("patterns: %d\n", l.PatternCount())
			return nil
		},
	}
}

func reclassifyCmd() *cobra.Command {
	var reason string
	c := &cobra.Command{
		Use:   "reclassify <fp_hash> <disposition>",
		Short: "Reclassify a pattern (reopens it when moving off an excludable class)",
		Args:  cobra.ExactArgs(2),
		RunE: func(_ *cobra.Command, args []string) error {
			l, err := ledger.Open(dir)
			if err != nil {
				return err
			}
			defer l.Close()
			disp := ledger.Disposition(args[1])
			if err := l.Reclassify(args[0], disp, reason); err != nil {
				return err
			}
			fmt.Printf("reclassified %s -> %s (excludable=%v)\n", args[0], disp, disp.Excludable())
			return nil
		},
	}
	c.Flags().StringVar(&reason, "reason", "", "why this reclassification was made (recorded in history)")
	return c
}

func importCmd() *cobra.Command {
	var kind, source, shodanTags string
	c := &cobra.Command{
		Use:   "import <path>",
		Short: "Map a source file into JSONL observations on stdout (feeds fuse)",
		Args:  cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			var (
				obs []normalize.Response
				err error
			)
			switch kind {
			case "shodan-json":
				obs, err = adapters.ShodanResults(args[0], source)
			case "aimap-json":
				obs, err = adapters.AimapReport(args[0], source)
			case "scanner-json":
				obs, err = adapters.ScannerResults(args[0], source)
			default:
				return fmt.Errorf("unknown --kind %q (have: shodan-json, aimap-json, scanner-json)", kind)
			}
			if err != nil {
				return err
			}
			if shodanTags != "" {
				tags, terr := adapters.LoadShodanTags(shodanTags)
				if terr != nil {
					return terr
				}
				adapters.ApplyShodanTags(obs, tags)
			}
			enc := json.NewEncoder(os.Stdout)
			for _, o := range obs {
				if err := enc.Encode(o); err != nil {
					return err
				}
			}
			return nil
		},
	}
	c.Flags().StringVar(&kind, "kind", "shodan-json", "source format: shodan-json | aimap-json | scanner-json")
	c.Flags().StringVar(&source, "source", "shodan", "source label to tag observations with")
	c.Flags().StringVar(&shodanTags, "shodan-tags", "", "JSON [{ip,tags}] file to join host tags onto observations (enables the honeypot-host-tagged screen sig)")
	return c
}

func gateCmd() *cobra.Command {
	var out string
	var record bool
	var shodanTags string
	c := &cobra.Command{
		Use:   "gate <aimap-report.json>",
		Short: "Filter an aimap report: drop screen-refuted and known-FP findings, emit the survivors",
		Args:  cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			l, err := ledger.Open(dir)
			if err != nil {
				return err
			}
			defer l.Close()
			var tags map[string][]string
			if shodanTags != "" {
				tags, err = adapters.LoadShodanTags(shodanTags)
				if err != nil {
					return err
				}
			}
			reasons := map[string]int{}
			filtered, kept, dropped, err := adapters.FilterAimapReport(args[0], "aimap", tags, func(r normalize.Response) bool {
				k, reason := gate.Decide(r, l)
				if !k {
					reasons[reason]++
					// a newly screen-refuted FP: record it so the corpus learns it
					if record && strings.HasPrefix(reason, "screen:") {
						res := screen.Screen(r)
						_, _ = l.Record(ledger.Finding{
							Response: r, Disposition: res.Disposition,
							Category: res.SignatureID, RootFix: res.Reason, SurveyCtx: "gate",
						})
					}
				}
				return k
			})
			if err != nil {
				return err
			}
			if out != "" {
				if err := os.WriteFile(out, filtered, 0o644); err != nil {
					return err
				}
			} else {
				_, _ = os.Stdout.Write(filtered)
			}
			// summary to stderr so stdout stays a clean, pipeable report
			fmt.Fprintf(os.Stderr, "gate: %d kept, %d dropped\n", kept, dropped)
			ids := make([]string, 0, len(reasons))
			for id := range reasons {
				ids = append(ids, id)
			}
			sort.Strings(ids)
			for _, id := range ids {
				fmt.Fprintf(os.Stderr, "  %-28s %d\n", id, reasons[id])
			}
			return nil
		},
	}
	c.Flags().StringVar(&out, "out", "", "write the filtered report here (default stdout)")
	c.Flags().BoolVar(&record, "record", false, "record newly screen-refuted FPs to the ledger corpus")
	c.Flags().StringVar(&shodanTags, "shodan-tags", "", "JSON [{ip,tags}] file to join host tags onto observations (enables the honeypot-host-tagged screen sig on aimap reports)")
	return c
}

func screenCmd() *cobra.Command {
	var record bool
	c := &cobra.Command{
		Use:   "screen <observations.jsonl>",
		Short: "Run observations through the FP signature screen (winnow-ported rules)",
		Args:  cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			obs, err := ingest.LoadJSONL(args[0])
			if err != nil {
				return err
			}
			var l *ledger.Ledger
			if record {
				if l, err = ledger.Open(dir); err != nil {
					return err
				}
				defer l.Close()
			}
			var pass, refuted, downgrade, recorded int
			bySig := map[string]int{}
			for _, o := range obs {
				res := screen.Screen(o)
				switch res.Verdict {
				case screen.Pass:
					pass++
				case screen.Refuted:
					refuted++
					bySig[res.SignatureID]++
					if record {
						if _, err := l.Record(ledger.Finding{
							Response: o, Disposition: res.Disposition,
							Category: res.SignatureID, RootFix: res.Reason, SurveyCtx: "screen",
						}); err != nil {
							return err
						}
						recorded++
					}
				case screen.Downgrade:
					downgrade++
					bySig[res.SignatureID]++
				}
			}
			fmt.Printf("%d observations: %d pass, %d refuted, %d downgrade\n", len(obs), pass, refuted, downgrade)
			ids := make([]string, 0, len(bySig))
			for id := range bySig {
				ids = append(ids, id)
			}
			sort.Strings(ids)
			for _, id := range ids {
				fmt.Printf("  %-28s %d\n", id, bySig[id])
			}
			if record {
				fmt.Printf("recorded %d refuted FPs to the ledger\n", recorded)
			}
			return nil
		},
	}
	c.Flags().BoolVar(&record, "record", false, "record refuted observations to the ledger as FPs")
	return c
}

func readInput(path string) ([]byte, error) {
	if path == "" || path == "-" {
		return io.ReadAll(os.Stdin)
	}
	return os.ReadFile(path)
}

func short(h string) string {
	if len(h) > 12 {
		return h[:12]
	}
	return h
}
