# Source state

The visual archive was built from the following canonical collections. Every item page retains its individual source paths and canonical links.

| Source key | Repository/collection | Recorded revision or state | Visual role |
|---|---|---|---|
| `zoe` | https://github.com/Ablation-Tool/zoe | Checkout `0305d4af4ff25e0a8ff5d8dd1642faba754075a9`, including present working-tree visual assets | Main Zoe, Dorothy, Neurogarden, CERN, mobile, component, branding, artwork, and interface sources |
| `zoe-autonomy` | https://github.com/Ablation-Tool/Zoe-Autonomy | `7dfd35cb0aab6814319b3ec7cddaaa16d61fd852` | Explanatory Autonomy diagrams, unified-paper figures, capability imagery |
| `next-token` | https://github.com/Ablation-Tool/next-token-predictability | `55429b57dc4c9de2cd2e98a24d56fd60083fa823` | Accessible Volume artwork, research figures, response-planning proof, brain-dialogue series, paper sources |
| `research-paper-figures` | https://github.com/Ablation-Tool/research-papers | `7146e696ddd3149a4241df5d1481660929300353` | Original embedded figures extracted from the 16-paper collection, with PDF-page metadata |
| `paper-source-figures` | Local `arxiv-autonomy-papers` source workspace | Reviewed source state | Original figure files used by the unified and focused papers |

## Collection totals

- Source image occurrences: **668**
- Byte-distinct archived files: **359**
- Archived image data: approximately **126 MB**

## Reproduction notes

The main Zoe checkout was behind its remote by seven non-visual-system commits at inventory time. New visual files introduced by those system changes—response-planning proof and capability browser imagery—were collected through the current Zoe-Autonomy and Accessible Volume clones listed above.

The archive builder does not fetch sources automatically. Set the environment variables documented in the README to known checkouts, then rerun the generator. This keeps source acquisition explicit and reproducible.
