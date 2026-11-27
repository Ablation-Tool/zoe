# Nuclide Color Framework v2

Centered Lyapunov geometry, perceptually uniform **OKLab** calibration (`Home = #2DB2BF`, `Cascade = #C66032` / `#D9581E` Burnt Orange), 3D SVD metamerism nullspace, directional Page CUSUM compliance-cascade detection, and offline `distilgpt2` spectral grounding for language model behavior.

## Quick Links

- **Compiled Research Paper:** [`paper/nuclide_color_framework_v2.pdf`](paper/nuclide_color_framework_v2.pdf) ([LaTeX source](paper/nuclide_color_framework_v2.tex))
- **Standalone Offline Equalizer v2:** [`equalizer/index.html`](equalizer/index.html) (open directly in any browser, zero build step) & React export [`equalizer/nuclide-equalizer-v2.jsx`](equalizer/nuclide-equalizer-v2.jsx)
- **Core Math & CLI:** [`src/nuclide_color.py`](src/nuclide_color.py)
- **Offline `distilgpt2` Spectrometer:** [`src/model_spectrometer.py`](src/model_spectrometer.py)
- **Reproducible Experiment Results & Figures:** [`experiments/run_experiments.py`](experiments/run_experiments.py) & [`experiments/results.json`](experiments/results.json)

## Recovered Originals (Untouched)

The March 26, 2026 originals and July 3, 2026 reconstruction remain untouched in `/home/cowboy/Downloads/`:
- `/home/cowboy/Downloads/nuclide_color_framework_paper.pdf`
- `/home/cowboy/Downloads/nuclide-equalizer.jsx`
- `/home/cowboy/Downloads/nuclide-color-framework (1).zip`
- `/home/cowboy/Downloads/nuclide-color-framework.zip`

## Reproduce

```bash
python3 src/nuclide_color.py audit
python3 src/nuclide_color.py metamer
python3 experiments/run_experiments.py
cd paper && pdflatex nuclide_color_framework_v2.tex && pdflatex nuclide_color_framework_v2.tex
```
