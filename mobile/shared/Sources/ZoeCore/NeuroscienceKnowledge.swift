import Foundation

/// Zoe Offline Neuroscience & Dorothy Brain Q&A Engine (Swift / ZoeCore, 100% offline, 0 cloud tokens).
///
/// Mirrors `NeuroscienceKnowledge.java` across iOS, iPadOS, macOS, and Linux Swift tests.
/// Grounded in the Dorothy Brain Observatory MNI152 / ICBM152 / AAL-116 / CIT168 atlas.
/// Educational neuroanatomy reference only (`clinical_action_authorized = false`, `sentience_claimed = false`).
public enum NeuroscienceKnowledge {
    public struct NeuroAnswer: Equatable, Sendable {
        public let title: String
        public let reply: String
        public let citation: String
        public let focusQuery: String
        public let score: Int

        public init(title: String, reply: String, citation: String, focusQuery: String, score: Int) {
            self.title = title
            self.reply = reply
            self.citation = citation
            self.focusQuery = focusQuery
            self.score = score
        }
    }

    private struct Entry {
        let id: String
        let title: String
        let citation: String
        let focusQuery: String
        let answer: String
        let triggers: [String]
        let tags: [String]
    }

    private static let scopeNote =
        "\n\n[Dorothy Neuro-Atlas · Reference only]"

    private static let stopWords: Set<String> = [
        "a", "an", "the", "is", "are", "was", "were", "be", "what", "where", "how", "why",
        "who", "when", "which", "does", "do", "did", "can", "could", "tell", "me", "about",
        "explain", "show", "in", "on", "of", "to", "for", "with", "at", "by", "from", "and",
        "or", "my", "your", "this", "that", "it", "its", "please", "zoe", "human", "part", "area",
    ]

    private static let romanCn: [String: Int] = [
        "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
        "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
    ]

    public static func lookup(_ rawInput: String) -> NeuroAnswer? {
        let trimmed = rawInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        let strippedQuotes = trimmed.lowercased()
            .replacingOccurrences(of: "'", with: "")
            .replacingOccurrences(of: "\u{2019}", with: "")
            .replacingOccurrences(of: "`", with: "")
        let normChars = strippedQuotes.unicodeScalars.map { scalar -> Character in
            if CharacterSet.alphanumerics.contains(scalar) || scalar == "_" || scalar == "+" || scalar == "-" || scalar == " " {
                return Character(scalar)
            }
            return " "
        }
        let norm = String(normChars)
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
        guard !norm.isEmpty else { return nil }

        let baTarget = firstRegexGroup(norm, pattern: #"\b(?:ba|brodmann(?:\s+area)?)\s*(\d{1,2})\b"#)
        var cnTarget: Int?
        if let cnTok = firstRegexGroup(norm, pattern: #"\b(?:cn|cranial\s+nerve)\s*(xii|xi|x|ix|viii|vii|vi|iv|v|iii|ii|i|\d{1,2})\b"#) {
            if let r = romanCn[cnTok] {
                cnTarget = r
            } else if let n = Int(cnTok), (1...12).contains(n) {
                cnTarget = n
            }
        }

        let tokens = norm.split(separator: " ").map(String.init).filter { $0.count > 1 && !stopWords.contains($0) }

        var best: Entry?
        var bestScore = 0
        for e in entries {
            var score = 0
            if let ba = baTarget, e.id == "ba_\(ba)" { score += 80 }
            if let cn = cnTarget, e.id == "cn_\(cn)" { score += 85 }
            for trig in e.triggers where norm.contains(trig) {
                score += trig.contains(" ") ? 26 : 16
            }
            for tok in tokens {
                for tag in e.tags {
                    if tag == tok {
                        score += 9
                    } else if tag.count >= 4 && (tag.contains(tok) || tok.contains(tag)) {
                        score += 4
                    }
                }
            }
            if score > bestScore {
                bestScore = score
                best = e
            }
        }

        guard let match = best, bestScore >= 14 else { return nil }
        return NeuroAnswer(
            title: match.title,
            reply: "\(match.title)\n\n\(match.answer)\(scopeNote)",
            citation: match.citation,
            focusQuery: match.focusQuery,
            score: bestScore
        )
    }

    private static func firstRegexGroup(_ text: String, pattern: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else { return nil }
        let range = NSRange(text.startIndex..., in: text)
        guard let match = regex.firstMatch(in: text, options: [], range: range),
              match.numberOfRanges > 1,
              let r = Range(match.range(at: 1), in: text) else {
            return nil
        }
        return String(text[r])
    }

    private static let entries: [Entry] = [
        Entry(
            id: "dorothy_mobile_platform",
            title: "Dorothy 3D Brain Observatory (Google Pixel, Apple iOS, Apple Fold & iPad)",
            citation: "Dorothy 3D Brain · Multi-Device Offline App",
            focusQuery: "hero",
            answer: "Dorothy 3D Brain Observatory is the centerpiece of the Zoe Research Partner app, optimized across Google Pixel, Apple iOS (iPhone), Apple Fold, and iPad with proper scientific capitalization matching the web version. It includes 240,376 MNI152/ICBM152/AAL-116/CIT168 triangles, 7 GPU shaders, 5 Functional Neural Circuits, 4 Cerebrovascular Territory Simulators, 19-electrode 10-20 EEG Cap, 3D Textured MRI Slicing, 3D Millimeter Caliper, 52 Brodmann Areas, 12 Cranial Nerves, 25 audited plates, HD videos, and Ask Zoe neuroscience Q&A.",
            triggers: ["google pixel", "apple fold", "ipad", "iphone", "dorothy 3d brain", "observatory features", "what can dorothy do"],
            tags: ["dorothy", "pixel", "apple", "ios", "fold", "ipad", "iphone", "3d", "observatory", "videos", "plates", "shaders", "offline"]
        ),
        Entry(
            id: "milestone1_neuro_oncology",
            title: "Milestone 1: Neurology & Brain Tumor / Brain Cancer Research",
            citation: "AGI-ROADMAP.md · Milestone 1 & Preclinical C17-C28",
            focusQuery: "mode:continuum",
            answer: "Zoe's Milestone 1 North Star as a Research Partner is advancing neurology and helping accelerate verified, wet-lab and clinically validated cures for brain tumors and brain cancer (including H3K27M diffuse midline glioma and glioblastoma). Active preclinical foundations include Dorothy 3D Brain Observatory, 36 NIH PubChem compounds with PAINS negative controls, FIPS 203 ML-KEM encrypted Filbin-2018 H3K27M tensors (C22), 3D pharmacophore compactness (C28), and histology MTF stopping. Constitutional boundary: computational modeling alone is never a cure or medical advice (`cure_claim = false`, `clinical_action_authorized = false`).",
            triggers: ["milestone 1", "brain tumor", "brain tumors", "brain cancer", "glioma", "glioblastoma", "h3k27m", "neuro oncology", "neuro-oncology", "curing brain"],
            tags: ["milestone", "tumor", "tumors", "cancer", "glioma", "glioblastoma", "oncology", "neurology", "h3k27m", "cure"]
        ),
        Entry(
            id: "dorothy_local_library",
            title: "Dorothy Brain Local Research Library (135 Books + 44 NIRMT PDFs · Local Machine Only)",
            citation: "Dorothy Brain Library · 6 Local Research Pillars",
            focusQuery: "mode:continuum",
            answer: "All 135 O'Reilly books (~6.7 GB total, 5,951 indexed chapters, 66,127 consolidated figures) and 44 NIRMT Textile Engineering PDFs (698 MB) are saved 100% locally on your workstation (never uploaded to the public GitHub repository).\n\nDesktop Access:\n• Visual Library Portal: Desktop/Dorothy Brain Library/index.html\n• All 6 Book Folders: Desktop/Dorothy Brain Library/books/\n• 44 NIRMT PDFs (698 MB): Desktop/Dorothy Brain Library/nirmt-textile-ebooks/\n• 66,127 Figures: Desktop/Dorothy Brain Library/images/\n• 3D Brain + 5,951-Chapter Search Vault: Desktop/Dorothy Brain Observatory/index.html\n\nExact Source Folders (captures/):\n• 00 Human Brain & Neuroimaging (33 books, 696 MB): captures/human-brain-books/\n• 01 Science & Medical Imaging (20 books, 1.0 GB): captures/dorothy-brain-library/01-science-imaging/\n• 02 3D Modeling & Graphics (26 books, 1.6 GB): captures/dorothy-brain-library/02-3d-modeling/\n• 03 Video Game Design & Engines (24 books, 1.9 GB): captures/dorothy-brain-library/03-video-game-design/\n• 04 AutoCAD & Engineering CAD (19 books, 1.1 GB): captures/dorothy-brain-library/04-autocad-cad/\n• 05 Biomechanics & Smart Textiles (13 books, 438 MB): captures/dorothy-brain-library/05-biomechanics-textiles/\n• NIRMT Textile Engineering PDFs (44 PDFs, 698 MB): captures/nirmt-textile-engineering-ebooks/",
            triggers: ["dorothy brain library", "135 books", "oreilly books", "o reilly books", "nirmt", "66127", "5951 chapters", "six pillars", "6 pillars", "local library", "captures"],
            tags: ["library", "books", "oreilly", "nirmt", "textile", "pillars", "captures", "chapters", "figures", "desktop"]
        ),
        Entry(
            id: "dorothy_brain_overview",
            title: "Dorothy 3D Brain Observatory",
            citation: "Dorothy Brain Observatory · MNI152 / ICBM152",
            focusQuery: "mode:continuum",
            answer: "Dorothy 3D Brain Observatory unites 240,376 real human stereotaxic anatomical triangles (ICBM152 cerebral cortex with FreeSurfer sulcal curvature, AAL-116 cerebellum, 32 Pauli CIT168 deep subcortical nuclei), synchronized 0.74 mm MNI152 T1-MRI slices, 5 interactive functional neural circuits, a 19-electrode 10-20 EEG smart-textile cap, 4 cerebrovascular territory simulators, 25 audited plates, and Dorothy Continuum Operational Metacognition A_tau(p).",
            triggers: ["dorothy brain", "dorothy 3d brain", "brain observatory", "human brain", "parts of the brain", "how does the brain work", "neuroanatomy", "neuroscience"],
            tags: ["dorothy", "brain", "neuroscience", "neuroanatomy", "observatory", "mni152", "icbm152", "lobes"]
        ),
        Entry(
            id: "struct_frontal",
            title: "Frontal Lobe (MNI: -32, 36, 30 mm)",
            citation: "Dorothy Atlas · Cerebral Cortex",
            focusQuery: "structure:Frontal",
            answer: "The Frontal Lobe governs executive control, planning, working memory (DLPFC, BA 9/46), voluntary contralateral movement (Primary Motor Cortex M1, BA 4 with giant Layer V Betz cells), motor sequencing (Premotor/SMA, BA 6), voluntary eye saccades (Frontal Eye Fields, BA 8), expressive speech production (Broca's area, BA 44/45), and value-based decision making (Orbitofrontal cortex, BA 11/12). Vascular supply: ACA (medial) and MCA (lateral).",
            triggers: ["frontal lobe", "prefrontal cortex", "dlpfc", "orbitofrontal", "executive function"],
            tags: ["frontal", "prefrontal", "dlpfc", "orbitofrontal", "executive", "planning"]
        ),
        Entry(
            id: "struct_parietal",
            title: "Parietal Lobe (MNI: -36, -46, 52 mm)",
            citation: "Dorothy Atlas · Cerebral Cortex",
            focusQuery: "structure:Parietal",
            answer: "The Parietal Lobe houses Primary Somatosensory Cortex (S1, Postcentral Gyrus, BA 1-3, Somatosensory Homunculus), proprioception and reaching guidance (BA 5/7), and multimodal reading, arithmetic, praxis, and spatial attention (Angular Gyrus BA 39 and Supramarginal Gyrus BA 40). Vascular supply: ACA (medial) and MCA (lateral).",
            triggers: ["parietal lobe", "somatosensory cortex", "postcentral gyrus", "homunculus", "angular gyrus", "supramarginal"],
            tags: ["parietal", "somatosensory", "postcentral", "homunculus", "touch", "proprioception", "spatial"]
        ),
        Entry(
            id: "struct_temporal",
            title: "Temporal Lobe (MNI: -56, -24, -10 mm)",
            citation: "Dorothy Atlas · Cerebral Cortex",
            focusQuery: "structure:Temporal",
            answer: "The Temporal Lobe integrates Primary Auditory Cortex (Heschl's gyrus, BA 41/42), speech comprehension (Wernicke's area, posterior BA 22), ventral visual object and face recognition (BA 20 and Fusiform Face Area BA 37), cross-modal semantics (BA 38), and medial temporal declarative memory structures. Vascular supply: MCA (superior/lateral) and PCA (inferior/medial).",
            triggers: ["temporal lobe", "fusiform gyrus", "fusiform face area", "heschl gyrus", "auditory cortex"],
            tags: ["temporal", "auditory", "fusiform", "hearing", "semantic", "heschl"]
        ),
        Entry(
            id: "struct_occipital",
            title: "Occipital Lobe & Primary Visual Cortex V1 (MNI: -18, -88, 6 mm)",
            citation: "Dorothy Atlas · Visual Cortex (BA 17-19)",
            focusQuery: "structure:Occipital",
            answer: "The Occipital Lobe contains Primary Visual Cortex (V1 / Striate Cortex, BA 17) along the calcarine sulcus banks, featuring the myelinated Stria of Gennari in Layer IVb. Extrastriate areas V2-V5/MT (BA 18-19) compute contours, depth, color constancy (V4), and motion (V5/MT). Supplied by the Posterior Cerebral Artery (PCA).",
            triggers: ["occipital lobe", "visual cortex", "primary visual", "calcarine", "stria of gennari", "striate cortex"],
            tags: ["occipital", "visual", "vision", "v1", "calcarine", "retinotopic", "extrastriate"]
        ),
        Entry(
            id: "struct_insula",
            title: "Insular Cortex / Island of Reil (MNI: -38, 4, 2 mm)",
            citation: "Dorothy Atlas · Deep Cortical Lobe (BA 13-16)",
            focusQuery: "structure:Insula",
            answer: "Folded deep inside the Lateral (Sylvian) Fissure, the Insula integrates interoception (heartbeat, visceral state), pain salience, disgust, gustatory perception, autonomic regulation, and salience network switching. Supplied by M2 insular branches of the MCA.",
            triggers: ["insula", "insular cortex", "island of reil", "interoception", "salience network"],
            tags: ["insula", "insular", "interoception", "sylvian", "salience", "gustatory"]
        ),
        Entry(
            id: "struct_hippocampus",
            title: "Hippocampus & Limbic Memory System (MNI: -24, -20, -14 mm)",
            citation: "Dorothy Atlas · Limbic & Papez Circuit",
            focusQuery: "structure:Limbic",
            answer: "The Hippocampus consolidates episodic declarative memories and builds spatial maps via place cells, partnered with grid cells in Entorhinal Cortex (BA 28/34). Its main output arch, the Fornix, projects through the Papez circuit (Mammillary Bodies -> Anterior Thalamus -> Cingulate Gyrus -> Parahippocampal Gyrus). Supplied by PCA and Anterior Choroidal arteries.",
            triggers: ["hippocampus", "hippocampal", "limbic system", "entorhinal", "place cells", "grid cells", "episodic memory"],
            tags: ["hippocampus", "limbic", "memory", "entorhinal", "fornix", "papez", "cingulate"]
        ),
        Entry(
            id: "struct_amygdala",
            title: "Amygdala (MNI: -22, -4, -18 mm)",
            citation: "Dorothy Atlas · Limbic & Emotional Salience",
            focusQuery: "structure:Limbic",
            answer: "The Amygdala sits anterior to the hippocampus in the medial temporal lobe. It detects threat and emotional salience, mediates fear conditioning and emotional memory tagging, and connects to orbitofrontal cortex via the Uncinate Fasciculus and to hypothalamic/brainstem autonomic outputs.",
            triggers: ["amygdala", "fear conditioning", "emotional salience"],
            tags: ["amygdala", "fear", "emotion", "limbic", "salience", "uncinate"]
        ),
        Entry(
            id: "struct_cerebellum",
            title: "Cerebellum / 'Little Brain' (MNI: 0, -60, -32 mm)",
            citation: "Dorothy Atlas · AAL-116 Cerebellum & Vermis",
            focusQuery: "structure:Cerebellum",
            answer: "The Cerebellum packs ~69 billion neurons (~80% of all neurons in the human brain!) into tightly folded folia across anterior, posterior, and flocculonodular lobes plus midline vermis. It provides predictive motor timing, balance, posture, error correction, and implicit cognitive models via deep nuclei (Dentate, Emboliform, Globose, Fastigial). Supplied by SCA, AICA, and PICA.",
            triggers: ["cerebellum", "cerebellar", "vermis", "purkinje", "dentate nucleus"],
            tags: ["cerebellum", "balance", "coordination", "folia", "purkinje", "vermis", "ataxia"]
        ),
        Entry(
            id: "struct_brainstem",
            title: "Brainstem: Midbrain, Pons & Medulla (MNI: 0, -26, -34 mm)",
            citation: "Dorothy Atlas · Vital Autonomic Core",
            focusQuery: "structure:Brainstem",
            answer: "The Brainstem spans Midbrain (CN III-IV, substantia nigra, colliculi), Pons (CN V-VIII, pontocerebellar relay), and Medulla Oblongata (CN IX-XII, pyramidal decussation, cardiovascular & respiratory rhythm centers), plus the Reticular Activating System governing arousal. Supplied by Basilar and Vertebral arteries.",
            triggers: ["brainstem", "brain stem", "midbrain", "pons", "medulla", "reticular activating"],
            tags: ["brainstem", "midbrain", "pons", "medulla", "reticular", "breathing", "autonomic"]
        ),
        Entry(
            id: "struct_thalamus",
            title: "Thalamus: Diencephalic Relay Hub (MNI: -12, -19, 6 mm)",
            citation: "Dorothy Atlas · AAL Thalamus & Relays",
            focusQuery: "structure:Thalamus",
            answer: "The paired Thalami act as the brain's active cortical gateway: Anterior (Papez memory), Mediodorsal (prefrontal), VA/VL (motor/cerebellar/basal ganglia), VPL/VPM (body & face touch), LGN (vision), MGN (audition), and Pulvinar (visual attention), gated by the GABAergic Thalamic Reticular Nucleus. Only olfaction (CN I) reaches cortex before the thalamus.",
            triggers: ["thalamus", "thalamic", "lgn", "mgn", "pulvinar", "diencephalon"],
            tags: ["thalamus", "relay", "geniculate", "pulvinar", "diencephalon"]
        ),
        Entry(
            id: "struct_basal_ganglia",
            title: "Basal Ganglia & Pauli CIT168 Deep Nuclei (MNI: -18, -2, -2 mm)",
            citation: "Dorothy Atlas · Pauli CIT168 32 Subcortical Nuclei",
            focusQuery: "structure:BasalGanglia",
            answer: "The Basal Ganglia include Striatum (Caudate, Putamen, Nucleus Accumbens), Globus Pallidus (GPe & GPi), Subthalamic Nucleus (STN), and Substantia Nigra (SNc dopamine & SNr output), governing Direct ('GO'), Indirect ('NO-GO'), and Hyperdirect (rapid brake) action selection. Dorothy includes all 32 Pauli CIT168 subcortical meshes.",
            triggers: ["basal ganglia", "striatum", "caudate", "putamen", "globus pallidus", "substantia nigra", "subthalamic", "cit168", "nucleus accumbens"],
            tags: ["basal", "ganglia", "striatum", "caudate", "putamen", "pallidus", "nigra", "stn", "cit168"]
        ),
        Entry(
            id: "struct_corpus_callosum",
            title: "Corpus Callosum (MNI: 0, 0, 22 mm)",
            citation: "Dorothy Atlas · Commissural White Matter",
            focusQuery: "structure:CorpusCallosum",
            answer: "The Corpus Callosum carries ~200 million myelinated axons uniting the left and right cerebral hemispheres across Rostrum, Genu, Body, and Splenium. Pericallosal artery (ACA) supplies the anterior 4/5; PCA supplies the splenium.",
            triggers: ["corpus callosum", "callosum", "splenium", "genu", "interhemispheric"],
            tags: ["callosum", "commissural", "hemispheres", "splenium", "axons"]
        ),
        Entry(
            id: "struct_ventricles",
            title: "Ventricular System & Cerebrospinal Fluid (MNI: 0, -10, 14 mm)",
            citation: "Dorothy Atlas · CSF Circulation",
            focusQuery: "structure:Ventricles",
            answer: "Choroid plexus produces ~500 mL of CSF daily flowing: Lateral Ventricles -> Foramina of Monro -> 3rd Ventricle -> Cerebral Aqueduct of Sylvius -> 4th Ventricle -> Foramina of Luschka & Magendie -> subarachnoid space -> arachnoid granulations into the dural venous sinuses.",
            triggers: ["ventricle", "ventricles", "ventricular system", "cerebrospinal fluid", "csf", "choroid plexus", "aqueduct of sylvius"],
            tags: ["ventricles", "csf", "cerebrospinal", "choroid", "aqueduct", "monro"]
        ),
        Entry(
            id: "ba_44",
            title: "Broca's Area · Brodmann Areas 44 & 45 (MNI: -50, 14, 16 mm)",
            citation: "Dorothy Atlas · Frontal Lobe (IFG)",
            focusQuery: "ba:39",
            answer: "Broca's area occupies the dominant inferior frontal gyrus: BA 44 (pars opercularis) drives phonological assembly, articulatory motor planning, and hierarchical syntax; BA 45 (pars triangularis) supports semantic selection and expressive speech. Linked to Wernicke's area via the Arcuate Fasciculus and supplied by the Left MCA.",
            triggers: ["broca", "brocas area", "pars opercularis", "pars triangularis", "ba 44", "ba 45", "expressive speech", "speech production"],
            tags: ["broca", "ba44", "ba45", "speech", "syntax", "language", "expressive"]
        ),
        Entry(
            id: "ba_45",
            title: "Anterior Broca's Area · Brodmann Area 45 (MNI: -50, 28, 12 mm)",
            citation: "Dorothy Atlas · Pars Triangularis",
            focusQuery: "ba:40",
            answer: "Brodmann Area 45 (pars triangularis) forms anterior Broca's area in the dominant hemisphere, supporting semantic retrieval, syntactic structure building, and expressive language alongside BA 44.",
            triggers: ["ba 45", "brodmann 45", "pars triangularis"],
            tags: ["ba45", "broca", "triangularis", "semantic", "syntax"]
        ),
        Entry(
            id: "ba_22",
            title: "Wernicke's Area · Brodmann Area 22 (MNI: -58, -36, 12 mm)",
            citation: "Dorothy Atlas · Superior Temporal Gyrus",
            focusQuery: "ba:15",
            answer: "Posterior Brodmann Area 22 on the dominant superior temporal gyrus forms Wernicke's area for speech comprehension and phonological-to-semantic mapping, streaming forward to Broca's area via the Arcuate Fasciculus.",
            triggers: ["wernicke", "wernickes area", "ba 22", "brodmann 22", "speech comprehension"],
            tags: ["wernicke", "ba22", "comprehension", "temporal", "language"]
        ),
        Entry(
            id: "ba_4",
            title: "Primary Motor Cortex M1 · Brodmann Area 4 (MNI: -38, -16, 56 mm)",
            citation: "Dorothy Atlas · Precentral Gyrus",
            focusQuery: "ba:1",
            answer: "Brodmann Area 4 (precentral gyrus) is agranular cortex containing giant Layer V Betz pyramidal cells projecting via the Corticospinal Tract (~85-90% pyramidal decussation) for contralateral voluntary movement.",
            triggers: ["primary motor cortex", "precentral gyrus", "betz cells", "ba 4", "brodmann 4", "motor cortex"],
            tags: ["motor", "m1", "precentral", "betz", "ba4", "movement"]
        ),
        Entry(
            id: "ba_17",
            title: "Primary Visual Cortex V1 · Brodmann Area 17 (MNI: -10, -88, 2 mm)",
            citation: "Dorothy Atlas · Calcarine Striate Cortex",
            focusQuery: "ba:10",
            answer: "Brodmann Area 17 (V1, striate cortex) lines the calcarine sulcus in the occipital lobe, receiving retinotopic LGN input into Layer IVb (Stria of Gennari).",
            triggers: ["ba 17", "brodmann 17", "striate cortex", "v1"],
            tags: ["ba17", "v1", "visual", "calcarine", "striate", "gennari"]
        ),
        Entry(
            id: "ba_41",
            title: "Primary Auditory Cortex A1 · Brodmann Areas 41 & 42 (MNI: -48, -22, 8 mm)",
            citation: "Dorothy Atlas · Heschl's Gyrus",
            focusQuery: "ba:36",
            answer: "Brodmann Area 41 (anterior Heschl's gyrus) is tonotopically organized Primary Auditory Cortex receiving MGN thalamic input; BA 42 performs secondary pitch and speech-sound analysis.",
            triggers: ["ba 41", "ba 42", "brodmann 41", "heschl", "primary auditory"],
            tags: ["ba41", "ba42", "auditory", "heschl", "tonotopic", "hearing"]
        ),
        Entry(
            id: "ba_46",
            title: "Dorsolateral Prefrontal Cortex (DLPFC) · BA 9 & 46 (MNI: -44, 36, 22 mm)",
            citation: "Dorothy Atlas · Middle Frontal Gyrus",
            focusQuery: "ba:41",
            answer: "Brodmann Areas 9 and 46 form DLPFC, governing active working memory manipulation, sustained executive attention, cognitive flexibility, and rule switching.",
            triggers: ["ba 46", "ba 9", "brodmann 46", "brodmann 9", "working memory"],
            tags: ["ba46", "ba9", "dlpfc", "working", "executive", "attention"]
        ),
        Entry(id: "cn_1", title: "CN I: Olfactory Nerve (MNI: -10, 44, -20 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:0",
              answer: "Special Sensory (SVA) for smell through the cribriform plate to the olfactory bulb. Uniquely bypasses the thalamus before reaching piriform cortex.",
              triggers: ["cn i", "cn 1", "cranial nerve 1", "cranial nerve i", "olfactory nerve", "sense of smell"], tags: ["olfactory", "smell", "cribriform", "cn1"]),
        Entry(id: "cn_2", title: "CN II: Optic Nerve (MNI: 0, 4, -18 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:1",
              answer: "Special Sensory (SSA) for vision and pupillary light reflex afferent via the optic canal and optic chiasm to the thalamic LGN.",
              triggers: ["cn ii", "cn 2", "cranial nerve 2", "cranial nerve ii", "optic nerve", "optic chiasm"], tags: ["optic", "vision", "retina", "chiasm", "cn2"]),
        Entry(id: "cn_3", title: "CN III: Oculomotor Nerve (MNI: -4, -18, -16 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:2",
              answer: "Motor + Parasympathetic from ventral midbrain via superior orbital fissure: SR, IR, MR, IO, levator palpebrae, plus pupillary constriction and lens accommodation.",
              triggers: ["cn iii", "cn 3", "cranial nerve 3", "cranial nerve iii", "oculomotor"], tags: ["oculomotor", "pupil", "midbrain", "eyelid", "cn3"]),
        Entry(id: "cn_4", title: "CN IV: Trochlear Nerve (MNI: -5, -30, -16 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:3",
              answer: "Pure Motor (GSE) nerve: the ONLY cranial nerve exiting the dorsal brainstem (dorsal midbrain), decussating completely to innervate the contralateral superior oblique muscle.",
              triggers: ["cn iv", "cn 4", "cranial nerve 4", "cranial nerve iv", "trochlear"], tags: ["trochlear", "dorsal", "oblique", "cn4"]),
        Entry(id: "cn_5", title: "CN V: Trigeminal Nerve (MNI: -14, -22, -29 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:4",
              answer: "Mixed nerve from lateral pons (V1 superior orbital fissure, V2 foramen rotundum, V3 foramen ovale): facial sensation, corneal reflex afferent, and muscles of mastication.",
              triggers: ["cn v", "cn 5", "cranial nerve 5", "cranial nerve v", "trigeminal"], tags: ["trigeminal", "pons", "mastication", "corneal", "cn5"]),
        Entry(id: "cn_6", title: "CN VI: Abducens Nerve (MNI: -4, -24, -38 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:5",
              answer: "Pure Motor (GSE) from medial pontomedullary junction via superior orbital fissure driving ipsilateral lateral rectus eye abduction.",
              triggers: ["cn vi", "cn 6", "cranial nerve 6", "cranial nerve vi", "abducens"], tags: ["abducens", "lateral rectus", "abduction", "cn6"]),
        Entry(id: "cn_7", title: "CN VII: Facial Nerve (MNI: -12, -28, -38 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:6",
              answer: "Mixed nerve from cerebellopontine angle via internal acoustic meatus -> stylomastoid foramen: facial expression, stapedius, anterior 2/3 tongue taste, and lacrimal/salivary glands.",
              triggers: ["cn vii", "cn 7", "cranial nerve 7", "cranial nerve vii", "facial nerve"], tags: ["facial", "expression", "taste", "stapedius", "cn7"]),
        Entry(id: "cn_8", title: "CN VIII: Vestibulocochlear Nerve (MNI: -16, -30, -39 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:7",
              answer: "Special Sensory (SSA) via internal acoustic meatus carrying hearing (cochlear division) and balance/head acceleration (vestibular division).",
              triggers: ["cn viii", "cn 8", "cranial nerve 8", "cranial nerve viii", "vestibulocochlear"], tags: ["vestibulocochlear", "cochlear", "vestibular", "hearing", "cn8"]),
        Entry(id: "cn_9", title: "CN IX: Glossopharyngeal Nerve (MNI: -10, -33, -44 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:8",
              answer: "Mixed medullary nerve via jugular foramen: posterior 1/3 tongue taste & touch, gag reflex afferent, carotid baroreceptors, parotid gland, and stylopharyngeus.",
              triggers: ["cn ix", "cn 9", "cranial nerve 9", "cranial nerve ix", "glossopharyngeal"], tags: ["glossopharyngeal", "gag", "parotid", "carotid", "cn9"]),
        Entry(id: "cn_10", title: "CN X: Vagus Nerve (MNI: -10, -34, -48 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:9",
              answer: "Mixed medullary nerve via jugular foramen providing major parasympathetic control of heart, lungs, and abdominal viscera, plus pharynx, larynx (voice), and gag reflex efferent.",
              triggers: ["cn x", "cn 10", "cranial nerve 10", "cranial nerve x", "vagus", "vagus nerve"], tags: ["vagus", "parasympathetic", "larynx", "heart", "viscera", "cn10"]),
        Entry(id: "cn_11", title: "CN XI: Spinal Accessory Nerve (MNI: -9, -35, -56 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:10",
              answer: "Motor nerve arising from C1-C5 spinal cord, ascending through foramen magnum and exiting via jugular foramen to innervate sternocleidomastoid and trapezius.",
              triggers: ["cn xi", "cn 11", "cranial nerve 11", "cranial nerve xi", "accessory nerve"], tags: ["accessory", "trapezius", "sternocleidomastoid", "cn11"]),
        Entry(id: "cn_12", title: "CN XII: Hypoglossal Nerve (MNI: -5, -31, -50 mm)", citation: "Dorothy Atlas · Cranial Nerves I-XII", focusQuery: "cn:11",
              answer: "Pure Motor (GSE) nerve from ventral medulla via hypoglossal canal driving all intrinsic and extrinsic tongue muscles except palatoglossus (CN X).",
              triggers: ["cn xii", "cn 12", "cranial nerve 12", "cranial nerve xii", "hypoglossal"], tags: ["hypoglossal", "tongue", "medulla", "cn12"]),
        Entry(id: "cn_overview", title: "All 12 Cranial Nerves (CN I-XII)", citation: "Dorothy Atlas · Cranial Nerves Overview", focusQuery: "structure:CranialNerves",
              answer: "CN I Olfactory, II Optic, III Oculomotor, IV Trochlear (sole dorsal brainstem exit), V Trigeminal, VI Abducens, VII Facial, VIII Vestibulocochlear, IX Glossopharyngeal, X Vagus, XI Accessory, XII Hypoglossal.",
              triggers: ["cranial nerves", "12 cranial nerves", "twelve cranial nerves"], tags: ["cranial", "nerves", "foramen", "brainstem"]),
        Entry(id: "circuit_language", title: "Language Loop Circuit (Wernicke -> Arcuate -> Broca -> M1)", citation: "Dorothy Atlas · Functional Circuit Simulator", focusQuery: "circuit:language",
              answer: "Canonical left-dominant dorsal speech pathway: Heschl's gyrus (BA 41) -> Wernicke's area (BA 22) -> Arcuate Fasciculus -> Broca's area (BA 44/45) -> ventral M1 (BA 4) across Theta/Gamma speech rhythms.",
              triggers: ["language loop", "language circuit", "language pathway", "arcuate fasciculus", "how does speech work"], tags: ["language", "arcuate", "wernicke", "broca", "speech", "circuit"]),
        Entry(id: "circuit_visual", title: "Visual Pathway (CN II -> LGN -> Meyer's Loop -> V1)", citation: "Dorothy Atlas · Functional Circuit Simulator", focusQuery: "circuit:visual",
              answer: "Retina -> Optic Nerve/Chiasm (CN II) -> thalamic LGN -> Optic Radiations (Meyer's loop) -> Calcarine V1 (BA 17) -> Dorsal ('Where') & Ventral ('What') streams.",
              triggers: ["visual pathway", "visual circuit", "optic radiation", "meyers loop", "meyer loop", "dorsal stream", "ventral stream"], tags: ["visual", "pathway", "lgn", "meyer", "optic", "dorsal", "ventral"]),
        Entry(id: "circuit_motor", title: "Motor & Corticospinal Loop", citation: "Dorothy Atlas · Functional Circuit Simulator", focusQuery: "circuit:motor",
              answer: "M1/Premotor (BA 4/6) -> Striatum/GPi/Thalamus selection & cerebellar calibration -> Internal Capsule -> ~85-90% pyramidal decussation in medulla -> spinal motor neurons.",
              triggers: ["motor loop", "motor pathway", "corticospinal tract", "pyramidal tract", "pyramidal decussation"], tags: ["motor", "corticospinal", "pyramidal", "decussation", "circuit"]),
        Entry(id: "circuit_papez", title: "Papez Limbic Memory Circuit", citation: "Dorothy Atlas · Functional Circuit Simulator", focusQuery: "circuit:papez",
              answer: "Hippocampus -> Fornix -> Mammillary Bodies -> Anterior Thalamic Nuclei -> Cingulate Gyrus -> Cingulum -> Entorhinal Cortex -> Hippocampus.",
              triggers: ["papez circuit", "papez memory", "memory circuit", "fornix", "mammillary bodies"], tags: ["papez", "memory", "fornix", "mammillary", "cingulum", "hippocampus"]),
        Entry(id: "vasc_willis", title: "Circle of Willis & Cerebral Blood Supply (MNI: 0, -2, -16 mm)", citation: "Dorothy Atlas · Cerebrovascular Tree", focusQuery: "structure:Vascular",
              answer: "Anastomotic arterial ring uniting Anterior (ICA -> ACA, ACom, MCA) and Posterior (Vertebral -> Basilar -> PCA, PCom, SCA, AICA, PICA) circulations, delivering ~15-20% of cardiac output for ~20% of resting oxygen demand.",
              triggers: ["circle of willis", "cerebral blood", "blood supply", "cerebral arteries", "dural venous sinuses"], tags: ["willis", "artery", "arteries", "vascular", "circulation", "blood"]),
        Entry(id: "vasc_mca", title: "Middle Cerebral Artery (MCA) Territory", citation: "Dorothy Atlas · Vascular Territory Simulator", focusQuery: "vasc:mcaL",
              answer: "Perfuses lateral frontal, parietal, and superior temporal cortex plus deep lenticulostriate branches to basal ganglia and internal capsule. Educational localization: contralateral face & arm > leg weakness, aphasia (dominant) or hemineglect (non-dominant).",
              triggers: ["mca", "middle cerebral artery", "mca stroke", "lenticulostriate"], tags: ["mca", "middle", "cerebral", "artery", "stroke", "aphasia"]),
        Entry(id: "vasc_aca", title: "Anterior Cerebral Artery (ACA) Territory", citation: "Dorothy Atlas · Vascular Territory Simulator", focusQuery: "vasc:aca",
              answer: "Perfuses medial frontal and parietal lobes, paracentral lobule, and anterior 4/5 of corpus callosum. Educational localization: contralateral leg > arm weakness and frontal abulia.",
              triggers: ["aca", "anterior cerebral artery", "aca stroke", "pericallosal"], tags: ["aca", "anterior", "cerebral", "paracentral", "abulia"]),
        Entry(id: "vasc_pca", title: "Posterior Cerebral Artery (PCA) Territory", citation: "Dorothy Atlas · Vascular Territory Simulator", focusQuery: "vasc:pca",
              answer: "Perfuses occipital lobe (calcarine V1), inferior/medial temporal lobe, splenium, and posterior thalamus. Educational localization: contralateral homonymous hemianopia (often with macular sparing).",
              triggers: ["pca", "posterior cerebral artery", "pca stroke", "basilar artery"], tags: ["pca", "posterior", "basilar", "hemianopia", "occipital"]),
        Entry(id: "layers_6", title: "Six-Layer Neocortical Cytoarchitecture (Layers I-VI)", citation: "Dorothy Atlas · Cortical Microcircuitry", focusQuery: "ba:1",
              answer: "Layer I Molecular (top-down tufts), Layer II External Granular (local links), Layer III External Pyramidal (callosal/corticocortical), Layer IV Internal Granular (thalamic sensory INPUT), Layer V Internal Pyramidal (subcortical/spinal OUTPUT incl. Betz cells), Layer VI Multiform (corticothalamic feedback).",
              triggers: ["cortical layers", "six layers", "6 layers", "neocortex layers", "cytoarchitecture", "layer iv", "layer v", "cajal"], tags: ["layers", "neocortex", "cytoarchitecture", "pyramidal", "stellate", "cajal"]),
        Entry(id: "mod_dopamine", title: "Dopamine & Neuromodulatory Systems", citation: "Dorothy Atlas · Neuromodulators", focusQuery: "structure:BasalGanglia",
              answer: "Dopamine pathways (Nigrostriatal motor, Mesolimbic reward, Mesocortical executive, Tuberoinfundibular), Serotonin (Raphe mood/sleep), Norepinephrine (Locus Coeruleus arousal), Acetylcholine (Basal Forebrain arousal/memory), Glutamate (fast excitation), and GABA (fast inhibition).",
              triggers: ["dopamine", "serotonin", "norepinephrine", "acetylcholine", "glutamate", "gaba", "neurotransmitter", "neurotransmitters", "neuromodulator"], tags: ["dopamine", "serotonin", "norepinephrine", "acetylcholine", "glutamate", "gaba", "neurotransmitter", "synapse"]),
        Entry(id: "dti_tracts", title: "DTI White-Matter Connectome & Tractography", citation: "Dorothy Atlas · White-Matter Pathways", focusQuery: "structure:WhiteMatter",
              answer: "DTI color convention: Red = L-R Commissural (Corpus Callosum), Green = A-P Association (Arcuate/SLF, ILF, IFOF, Uncinate, Cingulum), Blue = S-I Projection (Corticospinal, Internal Capsule, Fornix, Optic Radiations).",
              triggers: ["white matter", "dti", "tractography", "fasciculus", "internal capsule", "connectome"], tags: ["dti", "tractography", "white", "matter", "connectome", "fasciculus", "tracts"]),
        Entry(id: "eeg_waves", title: "10-20 EEG Cap & Brain Wave Rhythms", citation: "Dorothy Atlas · 19-Electrode 10-20 EEG", focusQuery: "eeg",
              answer: "International 10-20 montage (19 scalp electrodes) measures Delta (0.5-4 Hz sleep), Theta (4-8 Hz memory/effort), Alpha/Mu (8-12 Hz visual idling/motor imagery), Beta (13-30 Hz active control), and Gamma (30-80+ Hz binding, including 40 Hz).",
              triggers: ["eeg", "10-20", "brain waves", "brainwaves", "alpha wave", "theta wave", "gamma wave", "40 hz", "p300"], tags: ["eeg", "alpha", "beta", "theta", "gamma", "delta", "oscillation", "electrode"]),
        Entry(id: "neurons_ltp", title: "Neurons, Glia, Action Potentials & Synaptic Plasticity", citation: "Dorothy Atlas · Cellular Neurophysiology", focusQuery: "structure:Cerebellum",
              answer: "~86 billion neurons (~69 billion in cerebellum!) and ~100 trillion synapses communicate via 1-2 ms Na+/K+ action potentials and adapt via NMDA/AMPA Long-Term Potentiation (LTP), supported by oligodendrocytes, astrocytes, and microglia.",
              triggers: ["action potential", "how many neurons", "synaptic plasticity", "neuroplasticity", "long term potentiation", "ltp", "myelin", "glia", "astrocyte", "oligodendrocyte"], tags: ["neuron", "neurons", "synapse", "synapses", "axon", "dendrite", "myelin", "plasticity", "ltp"]),
        Entry(id: "mri_space", title: "MNI152 Space & Brain MRI (T1, T2, fMRI, DTI)", citation: "Dorothy Atlas · Neuroimaging Physics", focusQuery: "structure:Frontal",
              answer: "MNI152 stereotaxic space has origin (0,0,0) at the Anterior Commissure (+X Right, +Y Anterior, +Z Superior). T1 highlights bright white matter & dark CSF, T2 brightens CSF, fMRI BOLD tracks neurovascular coupling, and DTI maps axon tracts.",
              triggers: ["mni152", "mri", "t1 mri", "t2 mri", "fmri", "bold signal", "stereotaxic"], tags: ["mri", "mni152", "icbm152", "fmri", "bold", "t1", "t2", "voxel"]),
    ]
}
