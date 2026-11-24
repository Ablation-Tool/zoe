"""CLI: biobert query <seed.fasta> <db.fasta> [--type protein|dna|rna] [--semantic]"""

from __future__ import annotations
import argparse
import sys

from .features import parse_fasta, SeqType
from .homolog  import HomologFinder
from .semantic import ESM2Encoder, NucleotideEncoder


def cmd_query(args: argparse.Namespace) -> None:
    seq_type: SeqType = args.type

    seeds = parse_fasta(args.seed,     seq_type=seq_type)
    db    = parse_fasta(args.database, seq_type=seq_type)

    if not seeds:
        print("error: no sequences in seed file", file=sys.stderr)
        sys.exit(1)
    if not db:
        print("error: no sequences in database file", file=sys.stderr)
        sys.exit(1)

    encoder = None
    if args.semantic:
        if seq_type == 'protein':
            encoder = ESM2Encoder()
        else:
            encoder = NucleotideEncoder()

    finder = HomologFinder(encoder=encoder, seq_type=seq_type)

    for seed in seeds:
        print(f"\nquery: {seed.name}  len={seed.length}  type={seq_type}  k={seed.k}")
        candidates = [p for p in db if p.name != seed.name]
        match = finder.find_homolog(seed, candidates)
        if match is None:
            print("  no match")
            continue
        print(
            f"  hit:        {match.name}\n"
            f"  confidence: {match.confidence}\n"
            f"  jaccard:    {match.jaccard:.3f}\n"
            f"  semantic:   {match.semantic_score:.3f}\n"
            f"  hit_len:    {len(match.sequence)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="biobert")
    sub    = parser.add_subparsers(dest="cmd")

    q = sub.add_parser("query", help="Find homologs for seed sequence(s) in a database")
    q.add_argument("seed",     help="FASTA file with one or more query sequences")
    q.add_argument("database", help="FASTA file with candidate sequences")
    q.add_argument("--type",   choices=["protein", "dna", "rna"],
                   default="protein", dest="type",
                   help="Sequence type (default: protein)")
    q.add_argument("--semantic", action="store_true",
                   help="Enable language model semantic scoring (requires model download)")

    args = parser.parse_args()
    if args.cmd == "query":
        cmd_query(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
