# chainsaw

A thin CLI over a personal collective-brain of full-text books: routes a task to
the right book(s), serves full text, logs what fires, surfaces prune candidates,
and ingests new books. It never summarizes in place of a book.

Engine only. Bring your own corpus - no book text ships here.

## Layout the tool expects
    books/          full text per book:  NN_isbn_slug.txt
    brain/cards/    one card per book:   NN_isbn.md
    brain/INDEX.md  router + chain map
    _books.json     manifest
    USAGE.md        fire-log (prune-by-usage)

## Verbs
    chainsaw route "<task>"   lobe(s) + book numbers + full-text paths + 1 priming pick
    chainsaw read <NN[-MM]>   cat the full text of a book
    chainsaw list [lobe]      the manifest
    chainsaw fire <NN..> --task T --lift L   append a USAGE.md fire-log row
    chainsaw prune            books with zero fires
    chainsaw add <pdf> --lobe L --title T    slot a new book (additive)

Single file, Python stdlib only.
