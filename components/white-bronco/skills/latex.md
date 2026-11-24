---
name: latex
description: LaTeX document authoring expert. Synthesized from 13 official LaTeX documentation PDFs — lshort, usrguide, clsguide, fntguide, latex2e-reference, amsmath, hyperref, geometry, biblatex, beameruserguide, pgfmanual, latexsheet, symbols-comprehensive. Use when writing, reviewing, debugging, or correcting any .tex file.
tools:
  - Read
  - Edit
  - Write
  - Bash
---

# LaTeX Authoring Skill

Synthesized from the official LaTeX documentation corpus (PDFs in `docs/`): *The Not So Short Introduction to LaTeX2e* (lshort v6.4), *LaTeX2e for Authors* (usrguide), *LaTeX2e for Class and Package Writers* (clsguide), *LaTeX2e Font Selection* (fntguide), the *LaTeX2e Reference Manual* (June 2026), *User's Guide for the amsmath Package*, the *hyperref manual* (v7.01r), the *geometry manual*, *biblatex* (v3.x), the *beamer User Guide* (v3.78), the *PGF/TikZ Manual* (v3.x), and the *Comprehensive LaTeX Symbol List*. All primary sources are in `docs/` — consult them directly when a rule needs verification.

---

## 1. Document Structure

### Minimal working document
```latex
\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}   % not needed with LuaLaTeX/XeLaTeX
\usepackage{lmodern}
\usepackage{microtype}
\begin{document}
Hello, world.
\end{document}
```

### Class selection (lshort §1.3)
| Class | Use case |
|-------|----------|
| `article` | Papers, reports, short documents |
| `report` | Longer reports with chapters |
| `book` | Books — two-sided by default |
| `beamer` | Presentations |

Key class options: `10pt`/`11pt`/`12pt`, `a4paper`/`letterpaper`, `twoside`, `twocolumn`, `draft`.

---

## 2. Package Load Order

This order avoids nearly all conflicts (per hyperref manual §11):

```latex
% 1. Encoding and fonts — always first
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}      % pdfLaTeX only
\usepackage{lmodern}

% 2. Language
\usepackage[english]{babel}      % or polyglossia for XeLaTeX/LuaLaTeX

% 3. Page layout
\usepackage[margin=1in]{geometry}

% 4. Typography
\usepackage[protrusion=true,expansion=false]{microtype}
\usepackage{parskip}             % paragraph spacing instead of indent

% 5. Math
\usepackage{amsmath,amssymb,amsthm}

% 6. Utility
\usepackage{etoolbox}
\usepackage{needspace}
\usepackage{array}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{graphicx}

% 7. Code / verbatim
\usepackage{listings}
\usepackage{verbatim}

% 8. Boxes
\usepackage[most]{tcolorbox}

% 9. Headers
\usepackage{fancyhdr}
\usepackage{titlesec}

% 10. Bibliography
\usepackage[backend=biber,style=numeric]{biblatex}

% 11. hyperref LAST (almost always)
\usepackage[colorlinks=true]{hyperref}
\usepackage{cleveref}            % after hyperref
```

**Never load**: `graphicx` + `epsfig` together; `caption` inside `tcolorbox`; `subfigure` (use `subcaption`).

---

## 3. Typography Rules (lshort §2.4, §6.3)

### Dashes
```
-      hyphen:  well-known
--     en-dash: pages 12--15, ranges
---    em-dash: thought---like this
$-$    minus sign in math
```

### Quotation marks
```latex
``double quotes''       % NOT "double quotes"
`single quotes'         % NOT 'single quotes'
\usepackage{csquotes}
\enquote{text}          % preferred — adapts to language
```

### Special characters
```latex
\%  \$  \&  \#  \_  \{  \}  \^{}  \~{}  \textbackslash
```

### Ellipsis
```latex
\ldots    % correct: ...
...       % wrong in pdfLaTeX — produces three dots with wrong spacing
```

### Non-breaking space
```latex
Figure~\ref{fig:foo}   % ~ = non-breaking space — use before \ref, \cite
Dr.~Smith
```

### URLs (hyperref)
```latex
\url{https://example.com}        % typewriter, auto line-break at / - _ .
\href{https://example.com}{text} % linked text
\nolinkurl{https://example.com}  % typewriter no link
\path{/var/run/key.sock}         % paths with special chars, no link
```
**Never** wrap a URL in `\texttt{}` — it cannot line-break, causing overfull hboxes. Use `\url{}` or `\nolinkurl{}`.

### Spacing after periods
LaTeX adds extra space after `.` — suppress with `\@` before `.` when it follows an uppercase letter:
```latex
NASA\@ is an agency.   % correct
NASA is an agency.     % wrong — TeX sees uppercase before period
```
Or use `\frenchspacing` to disable inter-sentence spacing entirely.

### Penalties (lshort §6.3)
```latex
\widowpenalty=10000    % prevent widow lines
\clubpenalty=10000     % prevent orphan lines
```

---

## 4. Floats and Figures (lshort §2.6)

```latex
\usepackage{graphicx}

\begin{figure}[htbp]          % placement: here, top, bottom, page
  \centering
  \includegraphics[width=0.8\linewidth]{image.pdf}
  \caption{Caption text.}
  \label{fig:label}
\end{figure}
```

- `[H]` (from `float` package) forces exact placement — use sparingly; breaks float algorithm
- Prefer `[htbp]` order; `\clearpage` flushes pending floats
- `\linewidth` over `\textwidth` inside environments (minipage, tcolorbox, etc.)
- **Never** use `\begin{center}` inside a figure — use `\centering`

---

## 5. Tables (booktabs manual, lshort §2.5)

### booktabs rules — the three rule types
```latex
\toprule    % top of table — thicker
\midrule    % between header and body
\bottomrule % bottom — thicker
% \cline{i-j}  partial horizontal rule (use sparingly)
% Never use \hline with booktabs
```

### Standard tabular
```latex
\begin{table}[htbp]
  \centering
  \caption{Caption above for tables.}
  \label{tab:label}
  \begin{tabular}{@{}lp{6cm}r@{}}   % @{} removes outer padding
    \toprule
    \textbf{A} & \textbf{B} & \textbf{C} \\
    \midrule
    data & data & data \\
    \bottomrule
  \end{tabular}
\end{table}
```

### longtable (multi-page tables)
```latex
\begin{longtable}{@{}lp{8cm}@{}}
  % First-page header only:
  \toprule \textbf{Col1} & \textbf{Col2} \\ \midrule
  \endfirsthead
  % Subsequent-page header:
  \toprule \textbf{Col1} & \textbf{Col2} \\ \midrule
  \endhead
  % Last-page footer (closing rule):
  \bottomrule
  \endlastfoot
  % Optional every-page footer:
  \midrule \multicolumn{2}{r}{\small Continued\ldots} \\
  \endfoot
  % Data rows:
  Row 1 & data \\
  Row 2 & data \\
\end{longtable}
```
**Critical**: `\bottomrule` belongs in `\endlastfoot`, not as a trailing data row. A `\bottomrule` after data rows produces a rule that appears on every page break location.

### Column types
```
l  r  c         fixed alignment
p{width}        paragraph — wraps; top-aligned
m{width}        paragraph — vertically centered (array pkg)
b{width}        paragraph — bottom-aligned
X               stretch to fill (tabularx pkg)
@{text}         suppress inter-column space, insert text
>{cmd}c<{cmd}   pre/post column commands (array pkg)
```

---

## 6. Cross-References (lshort §2.8)

```latex
\label{sec:intro}          % place immediately after \section{}
\ref{sec:intro}            % produces number
\pageref{sec:intro}        % produces page number
```

### With cleveref (loaded after hyperref)
```latex
\usepackage{cleveref}
\cref{sec:intro}           % "Section 1" — auto-formats type
\Cref{sec:intro}           % Capitalised: "Section 1"
\cref{fig:foo,fig:bar}     % "Figures 1 and 2"
```

### With hyperref — \texorpdfstring
Use `\texorpdfstring` whenever a formatting command appears in a section title, to prevent bookmark corruption:
```latex
\section{\texorpdfstring{\texttt{key\_manager}}{key\_manager} Socket}
\section{Vuln-5: Hardcoded \texorpdfstring{\texttt{manager:password}}{manager:password}}
```
Without this, hyperref writes raw LaTeX commands into PDF bookmarks, producing garbage.

---

## 7. Lists (enumitem manual, lshort §2.2)

```latex
\usepackage{enumitem}

\begin{itemize}[nosep, leftmargin=*]
  \item First
  \item Second
\end{itemize}

\begin{enumerate}[label=\arabic*., nosep]
  \item One
  \item Two
\end{enumerate}

\begin{description}[labelwidth=3cm, leftmargin=3.5cm]
  \item[Term] Definition text here.
\end{description}
```
`nosep` removes extra spacing. `leftmargin=*` aligns with surrounding text.

---

## 8. Math (amsmath user guide)

### Inline vs. display
```latex
Inline: $a^2 + b^2 = c^2$ or \(a^2 + b^2 = c^2\)  % \(...\) preferred

Display (unnumbered):
\[ a^2 + b^2 = c^2 \]
or
\begin{equation*}
  a^2 + b^2 = c^2
\end{equation*}

Display (numbered):
\begin{equation}
  a^2 + b^2 = c^2  \label{eq:pythagoras}
\end{equation}
```

### Multi-line equations
```latex
\begin{align}
  f(x) &= x^2 + 2x + 1 \\
       &= (x+1)^2          \label{eq:factored}
\end{align}

\begin{align*}           % unnumbered
  f &= g \\
  g &= h
\end{align*}

\begin{split}            % inside equation, single number
  f(x) &= a + b \\
       &= c
\end{split}
```

### Operators
```latex
\sin \cos \tan \log \ln \exp \lim \max \min
\sup \inf \gcd \det \dim

% Custom:
\DeclareMathOperator{\softmax}{softmax}
```

### Text in math
```latex
E = mc^2 \quad \text{where } c \text{ is the speed of light}
% \text{} uses the surrounding font — correct
% \mathrm{} for upright Roman letters in math: $\mathrm{d}x$
```

### Spacing in math
```latex
\,    thin space
\:    medium space
\;    thick space
\!    negative thin space
\quad one em
\qquad two em
```

---

## 9. Code Listings (listings manual)

### Setup
```latex
\usepackage{listings}
\usepackage{xcolor}

\lstset{
  basicstyle=\small\ttfamily,
  backgroundcolor=\color{gray!10},
  frame=single,
  numbers=left,
  numberstyle=\tiny\color{gray},
  breaklines=true,
  showstringspaces=false,
  tabsize=4,
}
```

### Usage
```latex
\begin{lstlisting}[language=Python, caption={My script}]
def hello():
    print("hello world")
\end{lstlisting}

% Inline:
\lstinline|some_code()|
```

### Custom languages
```latex
\lstdefinelanguage{YARA}{
  morekeywords={rule, meta, strings, condition, ascii, nocase},
  morecomment=[l]{//},
  morestring=[b]",
}
```

### \texttt{} in listings
Never wrap listing content in `\texttt{}` — listings already uses typewriter. `\texttt{}` is for inline code in prose only.

---

## 10. Page Layout (geometry manual, fancyhdr)

### geometry
```latex
\usepackage[
  a4paper,
  margin=2.5cm,
  headheight=14pt,    % must be set when using fancyhdr
  includeheadfoot,
]{geometry}
```

### fancyhdr
```latex
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}                                  % clear all
\fancyhead[L]{\small\leftmark}              % chapter/section
\fancyhead[R]{\small\thepage}               % page number
\fancyfoot[C]{}                             % empty center footer
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}          % 0pt if footer is empty
```
**Rule**: if `\fancyfoot[C]{}` (empty), set `\footrulewidth` to `0pt`. A rule with no content below it is a layout error.

### titlesec
```latex
\usepackage{titlesec}
\titleformat{\section}
  {\large\bfseries}    % format
  {\thesection}        % label
  {1em}                % sep
  {}                   % before-code
  [\titlerule]         % after-code (horizontal rule under heading)

\titlespacing*{\section}{0pt}{3ex plus 1ex minus .5ex}{1.5ex}
```

---

## 11. Colors and Boxes (tcolorbox, xcolor)

### xcolor
```latex
\usepackage{xcolor}
\definecolor{navy}{HTML}{1a2744}
\definecolor{accent}{RGB}{37,99,168}
\textcolor{navy}{text}
\colorbox{accent!20}{text}
```

### tcolorbox custom environments
```latex
\usepackage[most]{tcolorbox}
\tcbuselibrary{skins,breakable}

\newtcolorbox{mybox}[1][]{
  enhanced, breakable,
  colback=blue!5, colframe=blue!50,
  leftrule=4pt, rightrule=0pt,
  toprule=0pt, bottomrule=0pt,
  arc=0pt,
  title={\small\bfseries My Box},
  fonttitle=\small\bfseries,
  coltitle=white,
  #1
}
```

**Critical**: `\newtcolorbox{mybox}` defines a `mybox` environment. Use it as `\begin{mybox}...\end{mybox}`. Do NOT pass `mybox` as a key to a raw `\begin{tcolorbox}[mybox]` — that tries to look up `mybox` as a tcolorbox option key and fails with a pgfkeys error.

### lstlisting inside tcolorbox
Listings inside breakable tcolorboxes may produce underfull hbox warnings from box geometry — these are cosmetic, not errors.

---

## 12. Headers and Sections

### Section title rules
- Do not use `\\` inside section titles
- Wrap any formatting command in `\texorpdfstring{formatted}{plain}` for PDF bookmarks
- Avoid `\footnote{}` in section titles — use `\footnotemark`/`\footnotetext` instead
- `\section*{}` produces unnumbered section with no ToC entry; use `\addcontentsline` to add manually

### titlesec formatting
```latex
\titleformat{\subsection}
  {\normalsize\bfseries\color{navy}}
  {}
  {0em}
  {}
```

---

## 13. Bibliography (biblatex manual §1–3)

### Setup
```latex
\usepackage[backend=biber, style=authoryear]{biblatex}
\addbibresource{refs.bib}
```

### Citation commands
```latex
\cite{key}          % (Author, Year)
\parencite{key}     % (Author, Year)
\textcite{key}      % Author (Year)
\footcite{key}      % footnote citation
\nocite{*}          % include all entries
```

### Printing bibliography
```latex
\printbibliography
\printbibliography[heading=bibintoc]   % add to ToC
```

### BibTeX entry types
```
@article, @book, @inproceedings, @techreport, @online, @misc
```
Required fields vary by type — check §2.1 of the biblatex manual.

---

## 14. Beamer Presentations (beamer user guide)

### Minimal frame
```latex
\documentclass{beamer}
\usetheme{Madrid}
\begin{document}
\begin{frame}{Title}
  Content here.
  \begin{itemize}
    \item<1-> Appears from slide 1
    \item<2-> Appears from slide 2
  \end{itemize}
\end{frame}
\end{document}
```

### Package compatibility
Load `lmodern` before any other font package. Do not load `geometry` with beamer — it breaks slide dimensions. Use `\setbeamersize` instead.

### lstlisting in beamer
Must use `\defverbatim` or `fragile` frame option:
```latex
\begin{frame}[fragile]{Code}
\begin{lstlisting}
code here
\end{lstlisting}
\end{frame}
```

---

## 15. TikZ / PGF (pgf manual §1–17)

### Minimal diagram
```latex
\usepackage{tikz}
\usetikzlibrary{arrows.meta, positioning}

\begin{tikzpicture}
  \draw[->] (0,0) -- (2,0) node[right] {$x$};
  \draw[->] (0,0) -- (0,2) node[above] {$y$};
  \node[circle, fill=blue!20, draw] at (1,1) {A};
\end{tikzpicture}
```

### Standalone figures
```latex
\documentclass[tikz,border=5pt]{standalone}
\usepackage{tikz}
\begin{document}
\begin{tikzpicture}
  % diagram
\end{tikzpicture}
\end{document}
```

### Common libraries
```
arrows.meta   positioning   shapes   fit   calc   matrix
decorations.pathmorphing    backgrounds    patterns
```

---

## 16. Fonts (fntguide, lshort §6.1)

### Standard font commands
```latex
\textrm{Roman}     \rmfamily
\textsf{Sans}      \sffamily
\texttt{Mono}      \ttfamily
\textbf{Bold}      \bfseries
\textit{Italic}    \itshape
\emph{Emphasis}              % context-sensitive italic/roman
\textsc{Small Caps}  \scshape
```

### Font encoding (fntguide §5)
Always load `[T1]{fontenc}` for pdfLaTeX — OT1 (default) cannot hyphenate words with accented characters and produces bitmap fonts at low resolutions. T1 uses vector fonts and proper hyphenation.

### Font size commands (relative)
```latex
\tiny \scriptsize \footnotesize \small \normalsize
\large \Large \LARGE \huge \Huge
```

---

## 17. Common Mistakes and How to Avoid Them

### Spacing
```latex
% WRONG:
\vspace{10pt}\\   % \\ followed by \vspace is redundant
\\[10pt]          % OK for small tweaks, but overused

% RIGHT:
\medskip / \bigskip   % semantic vertical space
\vspace{\baselineskip} % one line height
```

### Nesting environments
```latex
% WRONG — \centering inside center adds double spacing:
\begin{center}
  \centering
  ...
\end{center}

% RIGHT:
\begin{center}
  ...
\end{center}

% Or inside a float:
\begin{figure}
  \centering
  ...
\end{figure}
```

### Fragile commands in moving arguments
Moving arguments: section titles, captions, ToC entries. Fragile commands break there:
```latex
% WRONG:
\section{About \textcolor{red}{this}}

% RIGHT — \texorpdfstring for hyperref compatibility:
\section{\texorpdfstring{\textcolor{red}{this}}{this}}
% Or use \protect:
\section{About \protect\textcolor{red}{this}}
```

### Unused packages
Only load packages you actually use. Unnecessary packages:
- Slow compilation
- Risk option conflicts (especially with hyperref)
- Produce confusing warnings

### The \noindent anti-pattern
`\noindent` at the start of every paragraph means `parskip` or `\parindent=0pt` is a better choice. Use `\noindent` only for intentional non-indented paragraphs after a display, figure, or list.

### Overfull hboxes
```latex
% Common causes:
\texttt{very-long-url-that-cannot-break}  % use \url{} or \nolinkurl{}
\texttt{very_long_identifier}              % use \path{} for paths
% Long unbreakable words in narrow columns

% Diagnostic: add \usepackage{showframe} temporarily
% Fix: \sloppy (last resort), \allowbreak, \linebreak[1]
```

---

## 18. Compilation Workflow

```bash
pdflatex document.tex     # first pass
biber document            # if using biblatex
pdflatex document.tex     # second pass (ToC, refs)
pdflatex document.tex     # third pass (if changes)

# Or with latexmk (handles all passes automatically):
latexmk -pdf document.tex
latexmk -pdf -pvc document.tex   # continuous preview
```

### Output files
| Extension | Contents |
|-----------|----------|
| `.pdf` | Final output |
| `.aux` | Cross-reference data |
| `.log` | Full TeX log (read for errors) |
| `.toc` | Table of contents data |
| `.out` | hyperref bookmark data |
| `.bbl` | Compiled bibliography |
| `.bcf` | biber control file |

Delete `.aux` and `.out` if cross-references produce wrong results after major structural changes.

---

## 19. Error Diagnosis

Read the `.log` file, not just the terminal. Errors show as:
```
! Package pgfkeys Error: I do not know the key '/tcb/mybox'
l.42  \begin{tcolorbox}[mybox]
```
Line number (`l.42`) points to the source of the error.

### Common errors
| Error | Cause | Fix |
|-------|-------|-----|
| `! Package pgfkeys Error: I do not know the key '/tcb/X'` | Using a custom tcolorbox env name as a key | Use `\begin{X}` not `\begin{tcolorbox}[X]` |
| `! Undefined control sequence` | Typo or missing package | Check spelling, load required package |
| `! Missing $ inserted` | Math command outside math mode | Wrap in `$...$` |
| `Overfull \hbox` | Line too wide | Use `\url{}`, `\allowbreak`, or `\sloppy` |
| `LaTeX Warning: Label(s) may have changed` | Refs changed | Compile again |
| `Package hyperref Warning: Token not allowed in a PDF string` | Formatting in section title | Use `\texorpdfstring{}{}` |

---

## 20. The Minimal Correct Preamble

For a professional article/report:
```latex
\documentclass[11pt,a4paper]{article}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage[margin=1in, headheight=15pt]{geometry}
\usepackage[protrusion=true,expansion=false]{microtype}
\usepackage{parskip}
\usepackage{etoolbox}
\usepackage{needspace}
\usepackage{array}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{graphicx}
\usepackage{listings}
\usepackage[most]{tcolorbox}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage[
  colorlinks=true,
  linkcolor=blue!60!black,
  urlcolor=blue!60!black,
]{hyperref}
\usepackage{cleveref}

\widowpenalty=10000
\clubpenalty=10000
```

Load order is load-bearing. `hyperref` last (before `cleveref`). Font packages before geometry. `etoolbox` before `needspace`.
