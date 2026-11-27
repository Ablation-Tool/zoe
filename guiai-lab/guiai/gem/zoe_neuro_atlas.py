"""Offline Dorothy 3D Brain & Neuroscience Q&A Engine (1:1 port of Zoe App NeuroscienceKnowledge)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

SCOPE_NOTE = "\n\n[Dorothy Neuro-Atlas · Reference only]"
_BA_NUM_RE = re.compile(r"\b(?:ba|brodmann(?:\s+area)?)\s*(\d{1,2})\b")
_CN_NUM_RE = re.compile(r"\b(?:cn|cranial\s+nerve)\s*(xii|xi|x|ix|viii|vii|vi|iv|v|iii|ii|i|\d{1,2})\b")

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "what", "where", "how", "why",
    "who", "when", "which", "does", "do", "did", "can", "could", "tell", "me", "about",
    "explain", "show", "in", "on", "of", "to", "for", "with", "at", "by", "from", "and",
    "or", "my", "your", "this", "that", "it", "its", "please", "zoe", "human", "part", "area",
})

_ROMAN_CN: dict[str, int] = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
}


@dataclass(frozen=True)
class NeuroAnswer:
    title: str
    reply: str
    citation: str
    focus_query: str
    score: int


@dataclass(frozen=True)
class _Entry:
    entry_id: str
    title: str
    citation: str
    focus_query: str
    answer: str
    triggers: tuple[str, ...]
    tags: tuple[str, ...]


_ENTRIES: tuple[_Entry, ...] = (
    _Entry(
        "dorothy_mobile_platform",
        "Dorothy 3D Brain Observatory (Google Pixel, Apple iOS, Apple Fold & iPad)",
        "Dorothy 3D Brain · Multi-Device Offline App",
        "hero",
        "Dorothy 3D Brain Observatory is the centerpiece of the Zoe Research Partner app, optimized across Google Pixel, Apple iOS (iPhone), Apple Fold, and iPad with proper scientific capitalization matching the web version. It includes 240,376 MNI152/ICBM152/AAL-116/CIT168 triangles, 7 GPU shaders, 5 Functional Neural Circuits, 4 Cerebrovascular Territory Simulators, 19-electrode 10-20 EEG Cap, 3D Textured MRI Slicing, 3D Millimeter Caliper, 52 Brodmann Areas, 12 Cranial Nerves, 25 audited plates, HD videos, and Ask Zoe neuroscience Q&A.",
        ("google pixel", "apple fold", "ipad", "iphone", "dorothy 3d brain", "observatory features", "what can dorothy do"),
        ("dorothy", "pixel", "apple", "ios", "fold", "ipad", "iphone", "3d", "observatory", "videos", "plates", "shaders", "offline"),
    ),
    _Entry(
        "milestone1_neuro_oncology",
        "Milestone 1: Neurology & Brain Tumor / Brain Cancer Research",
        "AGI-ROADMAP.md · Milestone 1 & Preclinical C17-C28",
        "mode:continuum",
        "Zoe's Milestone 1 North Star as a Research Partner is advancing neurology and helping discover verified, wet-lab and clinically validated cures for brain tumors and brain cancer (including H3K27M diffuse midline glioma and glioblastoma). Active preclinical work spans the Dorothy 3D Brain Observatory, 36 NIH PubChem botanical compounds with Baell-Holloway PAINS negative controls, FIPS 203 ML-KEM encrypted Filbin-2018 H3K27M multi-hospital gene-module tensors (C22), 3D pharmacophore modeling (C28), and histology MTF stopping. Honest constitutional boundary: software modeling alone is never a clinical cure or medical treatment (`cure_claim = false`, `clinical_action_authorized = false`); real cures require independent wet-lab and regulated clinical trial validation.",
        ("milestone 1", "brain tumor", "brain tumors", "brain cancer", "glioma", "glioblastoma", "h3k27m", "neuro oncology", "neuro-oncology", "curing brain"),
        ("milestone", "tumor", "tumors", "cancer", "glioma", "glioblastoma", "oncology", "neurology", "h3k27m", "cure"),
    ),
    _Entry(
        "dorothy_local_library",
        "Dorothy Brain Local Research Library (135 Books + 44 NIRMT PDFs · Local Machine Only)",
        "Dorothy Brain Library · 6 Local Research Pillars",
        "mode:continuum",
        "All 135 O'Reilly books (~6.7 GB total, 5,951 indexed chapters, 66,127 consolidated figures) and 44 NIRMT Textile Engineering PDFs (698 MB) are stored 100% locally on your workstation (never uploaded to the public GitHub repository), spanning Human Brain & Neuroimaging (33 books), Science & Medical Imaging (20), 3D Modeling & Graphics (26), Video Game Design & Engines (24), AutoCAD & Engineering CAD (19), Biomechanics & Smart Textiles (13), and 44 NIRMT Textile Engineering PDFs.",
        ("dorothy brain library", "135 books", "oreilly books", "o reilly books", "nirmt", "66127", "5951 chapters", "six pillars", "6 pillars", "local library"),
        ("library", "books", "oreilly", "nirmt", "textile", "pillars", "chapters", "figures"),
    ),
    _Entry(
        "dorothy_brain_overview",
        "Dorothy 3D Brain Observatory",
        "Dorothy Brain Observatory · MNI152 / ICBM152",
        "mode:continuum",
        "Dorothy 3D Brain Observatory unites 240,376 real human stereotaxic anatomical triangles (ICBM152 cerebral cortex with FreeSurfer sulcal curvature, AAL-116 cerebellum, 32 Pauli CIT168 deep subcortical nuclei), synchronized 0.74 mm MNI152 T1-MRI slices, 5 interactive functional neural circuits, a 19-electrode 10-20 EEG smart-textile cap, 4 cerebrovascular territory simulators, 25 audited plates, and Dorothy Continuum Operational Metacognition A_tau(p).",
        ("dorothy brain", "dorothy 3d brain", "brain observatory", "human brain", "parts of the brain", "how does the brain work", "neuroanatomy", "neuroscience"),
        ("dorothy", "brain", "neuroscience", "neuroanatomy", "observatory", "mni152", "icbm152", "lobes"),
    ),
    _Entry(
        "struct_frontal",
        "Frontal Lobe (MNI: -32, 36, 30 mm)",
        "Dorothy Atlas · Cerebral Cortex",
        "structure:Frontal",
        "The Frontal Lobe governs executive control, planning, working memory (DLPFC, BA 9/46), voluntary contralateral movement (Primary Motor Cortex M1, BA 4 with giant Layer V Betz cells), motor sequencing (Premotor/SMA, BA 6), voluntary eye saccades (Frontal Eye Fields, BA 8), expressive speech production (Broca's area, BA 44/45), and value-based decision making (Orbitofrontal cortex, BA 11/12). Vascular supply: Anterior Cerebral Artery (medial) and Middle Cerebral Artery (lateral).",
        ("frontal lobe", "prefrontal cortex", "dlpfc", "orbitofrontal", "executive function"),
        ("frontal", "prefrontal", "dlpfc", "orbitofrontal", "executive", "planning"),
    ),
    _Entry(
        "struct_parietal",
        "Parietal Lobe (MNI: -36, -46, 52 mm)",
        "Dorothy Atlas · Cerebral Cortex",
        "structure:Parietal",
        "The Parietal Lobe houses Primary Somatosensory Cortex (S1, Postcentral Gyrus, BA 1-3, organizing the tactile Somatosensory Homunculus), proprioception and reaching guidance (Superior Parietal Lobule, BA 5/7), and multimodal reading, arithmetic, praxis, and spatial attention (Angular Gyrus BA 39 and Supramarginal Gyrus BA 40). Vascular supply: ACA (medial) and MCA (lateral).",
        ("parietal lobe", "somatosensory cortex", "postcentral gyrus", "homunculus", "angular gyrus", "supramarginal"),
        ("parietal", "somatosensory", "postcentral", "homunculus", "touch", "proprioception", "spatial"),
    ),
    _Entry(
        "struct_temporal",
        "Temporal Lobe (MNI: -56, -24, -10 mm)",
        "Dorothy Atlas · Cerebral Cortex",
        "structure:Temporal",
        "The Temporal Lobe integrates Primary Auditory Cortex (Heschl's gyrus, BA 41/42), speech comprehension (Wernicke's area, posterior BA 22), ventral 'what' stream visual object and face recognition (Inferior Temporal BA 20 and Fusiform Face Area BA 37), cross-modal semantics (Temporal Pole BA 38), and medial temporal declarative memory structures. Vascular supply: MCA (superior/lateral) and PCA (inferior/medial).",
        ("temporal lobe", "fusiform gyrus", "fusiform face area", "heschl gyrus", "auditory cortex"),
        ("temporal", "auditory", "fusiform", "hearing", "semantic", "heschl"),
    ),
    _Entry(
        "struct_occipital",
        "Occipital Lobe & Primary Visual Cortex V1 (MNI: -18, -88, 6 mm)",
        "Dorothy Atlas · Visual Cortex (BA 17-19)",
        "structure:Occipital",
        "The Occipital Lobe contains Primary Visual Cortex (V1 / Striate Cortex, BA 17) along the banks of the calcarine sulcus, distinguished by the myelinated Stria of Gennari in Layer IVb. Extrastriate areas V2-V5/MT (BA 18-19) compute contours, stereoscopic depth, color constancy (V4), and visual motion (V5/MT). Supplied by the Posterior Cerebral Artery (PCA), with frequent dual MCA collateral supply at the macular pole.",
        ("occipital lobe", "visual cortex", "primary visual", "calcarine", "stria of gennari", "striate cortex"),
        ("occipital", "visual", "vision", "v1", "calcarine", "retinotopic", "extrastriate"),
    ),
    _Entry(
        "struct_insula",
        "Insular Cortex / Island of Reil (MNI: -38, 4, 2 mm)",
        "Dorothy Atlas · Deep Cortical Lobe (BA 13-16)",
        "structure:Insula",
        "Folded deep inside the Lateral (Sylvian) Fissure beneath the frontal, parietal, and temporal opercula, the Insula integrates interoception (heartbeat, visceral state), pain salience, disgust, gustatory perception, autonomic balance, and switching between the Default Mode and Executive Control networks. Vascular supply: M2 insular branches of the Middle Cerebral Artery.",
        ("insula", "insular cortex", "island of reil", "interoception", "salience network"),
        ("insula", "insular", "interoception", "sylvian", "salience", "gustatory"),
    ),
    _Entry(
        "struct_hippocampus",
        "Hippocampus & Limbic Memory System (MNI: -24, -20, -14 mm)",
        "Dorothy Atlas · Limbic & Papez Circuit",
        "structure:Limbic",
        "The Hippocampus (nested inside the medial temporal lobe) consolidates episodic declarative memories and builds cognitive spatial maps via place cells, partnered with grid cells in the adjacent Entorhinal Cortex (BA 28/34). Its main output arch, the Fornix, projects to the Mammillary Bodies -> Anterior Thalamus -> Cingulate Gyrus -> Parahippocampal Gyrus (Papez memory circuit). Vascular supply: Posterior Cerebral and Anterior Choroidal arteries.",
        ("hippocampus", "hippocampal", "limbic system", "entorhinal", "place cells", "grid cells", "episodic memory"),
        ("hippocampus", "limbic", "memory", "entorhinal", "fornix", "papez", "cingulate"),
    ),
    _Entry(
        "struct_amygdala",
        "Amygdala (MNI: -22, -4, -18 mm)",
        "Dorothy Atlas · Limbic & Emotional Salience",
        "structure:Limbic",
        "The Amygdala is an almond-shaped nuclear complex just anterior to the hippocampus in the medial temporal lobe. It detects biological threat and emotional salience, mediates fear conditioning and emotional memory tagging, and connects directly to orbitofrontal cortex via the Uncinate Fasciculus and to hypothalamus/brainstem autonomic outputs via the stria terminalis.",
        ("amygdala", "fear conditioning", "emotional salience"),
        ("amygdala", "fear", "emotion", "limbic", "salience", "uncinate"),
    ),
    _Entry(
        "struct_cerebellum",
        "Cerebellum / 'Little Brain' (MNI: 0, -60, -32 mm)",
        "Dorothy Atlas · AAL-116 Cerebellum & Vermis",
        "structure:Cerebellum",
        "The Cerebellum packs ~69 billion neurons (roughly 80% of all neurons in the entire human brain) into tightly folded folia across the anterior, posterior, and flocculonodular lobes plus midline vermis. Rather than initiating movement directly, it acts as a fast forward predictive model for motor timing, balance, posture, error correction, and implicit cognitive sequencing via four paired deep nuclei (Dentate, Emboliform, Globose, Fastigial). Supplied by SCA, AICA, and PICA.",
        ("cerebellum", "cerebellar", "vermis", "purkinje", "dentate nucleus"),
        ("cerebellum", "balance", "coordination", "folia", "purkinje", "vermis", "ataxia"),
    ),
    _Entry(
        "struct_brainstem",
        "Brainstem: Midbrain, Pons & Medulla (MNI: 0, -26, -34 mm)",
        "Dorothy Atlas · Vital Autonomic Core",
        "structure:Brainstem",
        "The Brainstem links cerebrum and cerebellum to the spinal cord across three levels: Midbrain (CN III-IV, substantia nigra, superior/inferior colliculi), Pons (CN V-VIII, pontocerebellar relay), and Medulla Oblongata (CN IX-XII, pyramidal decussation, vital cardiovascular and respiratory rhythm centers). Its core Reticular Activating System regulates consciousness and sleep-wake arousal. Supplied by Basilar and Vertebral arteries.",
        ("brainstem", "brain stem", "midbrain", "pons", "medulla", "reticular activating"),
        ("brainstem", "midbrain", "pons", "medulla", "reticular", "breathing", "autonomic"),
    ),
    _Entry(
        "struct_thalamus",
        "Thalamus: Diencephalic Relay Hub (MNI: -12, -19, 6 mm)",
        "Dorothy Atlas · AAL Thalamus & Relays",
        "structure:Thalamus",
        "The paired Thalami act as the brain's active cortical gateway, partitioned by the Y-shaped internal medullary lamina into Anterior (Papez memory), Mediodorsal (prefrontal executive), Ventral Anterior/Lateral (motor/cerebellar/basal ganglia), VPL/VPM (body & face touch), LGN (vision), MGN (audition), and Pulvinar (visual attention), all gated by the inhibitory GABAergic Thalamic Reticular Nucleus (TRN). Smell (CN I) is the sole primary sense that reaches cortex before the thalamus.",
        ("thalamus", "thalamic", "lgn", "mgn", "pulvinar", "diencephalon"),
        ("thalamus", "relay", "geniculate", "pulvinar", "diencephalon"),
    ),
    _Entry(
        "struct_basal_ganglia",
        "Basal Ganglia & Pauli CIT168 Deep Nuclei (MNI: -18, -2, -2 mm)",
        "Dorothy Atlas · Pauli CIT168 32 Subcortical Nuclei",
        "structure:BasalGanglia",
        "The Basal Ganglia include the Striatum (Caudate, Putamen, Nucleus Accumbens), Globus Pallidus (GPe & GPi), Subthalamic Nucleus (STN), and Substantia Nigra (SNc dopamine & SNr output). They govern action selection through three parallel pathways: Direct (D1+, 'GO' disinhibits thalamus), Indirect (D2-, 'NO-GO' suppresses competing actions), and Hyperdirect (cortex -> STN -> GPi rapid brake). Dorothy includes all 32 real Pauli CIT168 subcortical meshes.",
        ("basal ganglia", "striatum", "caudate", "putamen", "globus pallidus", "substantia nigra", "subthalamic", "cit168", "nucleus accumbens"),
        ("basal", "ganglia", "striatum", "caudate", "putamen", "pallidus", "nigra", "stn", "cit168"),
    ),
    _Entry(
        "struct_corpus_callosum",
        "Corpus Callosum (MNI: 0, 0, 22 mm)",
        "Dorothy Atlas · Commissural White Matter",
        "structure:CorpusCallosum",
        "The Corpus Callosum is the largest white-matter bridge in the human brain, carrying ~200 million myelinated axons uniting the left and right cerebral hemispheres across four anatomical divisions: Rostrum, Genu, Body, and Splenium. Vascular supply: Pericallosal artery (ACA) supplies the anterior four-fifths; the Posterior Cerebral Artery supplies the splenium.",
        ("corpus callosum", "callosum", "splenium", "genu", "interhemispheric"),
        ("callosum", "commissural", "hemispheres", "splenium", "axons"),
    ),
    _Entry(
        "struct_ventricles",
        "Ventricular System & Cerebrospinal Fluid (MNI: 0, -10, 14 mm)",
        "Dorothy Atlas · CSF Circulation",
        "structure:Ventricles",
        "Choroid plexus produces ~500 mL of clear Cerebrospinal Fluid (CSF) daily to cushion and flush the brain. CSF flows sequentially: Bilateral Lateral Ventricles -> Foramina of Monro -> midline 3rd Ventricle -> Cerebral Aqueduct of Sylvius -> diamond-shaped 4th Ventricle -> Foramina of Luschka & Magendie -> subarachnoid space -> reabsorbed into the Superior Sagittal Sinus via arachnoid granulations.",
        ("ventricle", "ventricles", "ventricular system", "cerebrospinal fluid", "csf", "choroid plexus", "aqueduct of sylvius"),
        ("ventricles", "csf", "cerebrospinal", "choroid", "aqueduct", "monro"),
    ),
    _Entry("ba_44", "Broca's Area · Brodmann Areas 44 & 45 (MNI: -50, 14, 16 mm)", "Dorothy Atlas · Frontal Lobe (IFG)", "ba:39",
           "Broca's area occupies the inferior frontal gyrus of the dominant (typically left) hemisphere: BA 44 (pars opercularis) handles phonological assembly, articulatory motor planning, and hierarchical syntax; BA 45 (pars triangularis) supports semantic retrieval and expressive language. Connected to Wernicke's area via the dorsal Arcuate Fasciculus and supplied by the superior division of the Left Middle Cerebral Artery.",
           ("broca", "brocas area", "pars opercularis", "pars triangularis", "ba 44", "ba 45", "expressive speech", "speech production"),
           ("broca", "ba44", "ba45", "speech", "syntax", "language", "expressive")),
    _Entry("ba_45", "Anterior Broca's Area · Brodmann Area 45 (MNI: -50, 28, 12 mm)", "Dorothy Atlas · Pars Triangularis", "ba:40",
           "Brodmann Area 45 (pars triangularis of the inferior frontal gyrus) forms the anterior part of Broca's area in the dominant hemisphere, driving semantic selection, syntactic structure building, and expressive language generation alongside BA 44.",
           ("ba 45", "brodmann 45", "pars triangularis"), ("ba45", "broca", "triangularis", "semantic", "syntax")),
    _Entry("ba_22", "Wernicke's Area · Brodmann Area 22 (MNI: -58, -36, 12 mm)", "Dorothy Atlas · Superior Temporal Gyrus", "ba:15",
           "Posterior Brodmann Area 22 on the dominant (usually left) superior temporal gyrus forms Wernicke's area, essential for spoken and written speech comprehension and phonological-to-semantic mapping. It streams forward to Broca's area (BA 44/45) along the Arcuate Fasciculus and is supplied by the inferior division of the Middle Cerebral Artery.",
           ("wernicke", "wernickes area", "ba 22", "brodmann 22", "speech comprehension"), ("wernicke", "ba22", "comprehension", "temporal", "language")),
    _Entry("ba_4", "Primary Motor Cortex M1 · Brodmann Area 4 (MNI: -38, -16, 56 mm)", "Dorothy Atlas · Precentral Gyrus", "ba:1",
           "Brodmann Area 4 occupies the precentral gyrus immediately anterior to the central sulcus. It is agranular cortex packed with giant Layer V Betz pyramidal cells that project down the Corticospinal Tract (decussating ~85-90% in the medullary pyramids) to drive precise contralateral voluntary movement along the somatotopic Motor Homunculus.",
           ("primary motor cortex", "precentral gyrus", "betz cells", "ba 4", "brodmann 4", "motor cortex"), ("motor", "m1", "precentral", "betz", "ba4", "movement")),
    _Entry("ba_17", "Primary Visual Cortex V1 · Brodmann Area 17 (MNI: -10, -88, 2 mm)", "Dorothy Atlas · Calcarine Striate Cortex", "ba:10",
           "Brodmann Area 17 (V1, striate cortex) lines the upper and lower banks of the calcarine sulcus in the occipital lobe. It receives retinotopic input from the thalamic Lateral Geniculate Nucleus (LGN) via the Optic Radiations into Layer IVb (creating the macroscopic white band known as the Stria of Gennari).",
           ("ba 17", "brodmann 17", "striate cortex", "v1"), ("ba17", "v1", "visual", "calcarine", "striate", "gennari")),
    _Entry("ba_41", "Primary Auditory Cortex A1 · Brodmann Areas 41 & 42 (MNI: -48, -22, 8 mm)", "Dorothy Atlas · Heschl's Gyrus", "ba:36",
           "Brodmann Area 41 (anterior Heschl's gyrus on the superior temporal plane) is Primary Auditory Cortex (A1), tonotopically organized by sound frequency and receiving direct thalamic input from the Medial Geniculate Nucleus (MGN). Adjacent BA 42 performs secondary pitch and speech-sound analysis.",
           ("ba 41", "ba 42", "brodmann 41", "heschl", "primary auditory"), ("ba41", "ba42", "auditory", "heschl", "tonotopic", "hearing")),
    _Entry("ba_46", "Dorsolateral Prefrontal Cortex (DLPFC) · BA 9 & 46 (MNI: -44, 36, 22 mm)", "Dorothy Atlas · Middle Frontal Gyrus", "ba:41",
           "Brodmann Areas 9 and 46 form the Dorsolateral Prefrontal Cortex (DLPFC), core to active working memory manipulation, sustained executive attention, rule switching, abstract reasoning, and top-down cognitive control.",
           ("ba 46", "ba 9", "brodmann 46", "brodmann 9", "working memory"), ("ba46", "ba9", "dlpfc", "working", "executive", "attention")),
    _Entry("cn_1", "CN I: Olfactory Nerve (MNI: -10, 44, -20 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:0",
           "Special Sensory (SVA) for smell. Originates from olfactory receptor neurons passing through the cribriform plate of the ethmoid bone to the olfactory bulb. Uniquely, CN I is the sole primary sensory pathway that reaches cortex (piriform cortex) without first relaying in the thalamus.",
           ("cn i", "cn 1", "cranial nerve 1", "cranial nerve i", "olfactory nerve", "sense of smell"), ("olfactory", "smell", "cribriform", "cn1")),
    _Entry("cn_2", "CN II: Optic Nerve (MNI: 0, 4, -18 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:1",
           "Special Sensory (SSA) for vision and the afferent limb of the pupillary light reflex. Retinal ganglion cell axons exit via the optic canal, partially decussate at the optic chiasm (nasal fibers cross), and project to the thalamic LGN and pretectal nuclei. Embryologically a CNS diencephalic tract myelinated by oligodendrocytes.",
           ("cn ii", "cn 2", "cranial nerve 2", "cranial nerve ii", "optic nerve", "optic chiasm"), ("optic", "vision", "retina", "chiasm", "cn2")),
    _Entry("cn_3", "CN III: Oculomotor Nerve (MNI: -4, -18, -16 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:2",
           "Motor + Parasympathetic nerve exiting the ventral midbrain (interpeduncular fossa) through the superior orbital fissure. Drives 4 extraocular muscles (SR, IR, MR, IO), elevates the upper eyelid (levator palpebrae superioris), and carries Edinger-Westphal parasympathetic fibers for pupillary constriction and lens accommodation.",
           ("cn iii", "cn 3", "cranial nerve 3", "cranial nerve iii", "oculomotor"), ("oculomotor", "pupil", "midbrain", "eyelid", "cn3")),
    _Entry("cn_4", "CN IV: Trochlear Nerve (MNI: -5, -30, -16 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:3",
           "Pure Motor (GSE) nerve with two famous anatomical distinctions: it is the ONLY cranial nerve to exit the dorsal surface of the brainstem (dorsal midbrain) and its fibers completely decussate before entering the superior orbital fissure to innervate the contralateral superior oblique muscle (eye intorsion and depression when adducted).",
           ("cn iv", "cn 4", "cranial nerve 4", "cranial nerve iv", "trochlear"), ("trochlear", "dorsal", "oblique", "cn4")),
    _Entry("cn_5", "CN V: Trigeminal Nerve (MNI: -14, -22, -29 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:4",
           "Mixed nerve emerging from the lateral pons with three divisions: V1 Ophthalmic (superior orbital fissure), V2 Maxillary (foramen rotundum), and V3 Mandibular (foramen ovale). Provides facial and anterior 2/3 tongue general sensation, the corneal blink reflex afferent, and V3 motor control of mastication (chewing) muscles.",
           ("cn v", "cn 5", "cranial nerve 5", "cranial nerve v", "trigeminal"), ("trigeminal", "pons", "mastication", "corneal", "cn5")),
    _Entry("cn_6", "CN VI: Abducens Nerve (MNI: -4, -24, -38 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:5",
           "Pure Motor (GSE) nerve emerging at the medial pontomedullary junction and traversing the cavernous sinus and superior orbital fissure to innervate the ipsilateral lateral rectus muscle, which abducts the eye laterally.",
           ("cn vi", "cn 6", "cranial nerve 6", "cranial nerve vi", "abducens"), ("abducens", "lateral rectus", "abduction", "cn6")),
    _Entry("cn_7", "CN VII: Facial Nerve (MNI: -12, -28, -38 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:6",
           "Mixed nerve emerging at the cerebellopontine angle and passing through the internal acoustic meatus to the stylomastoid foramen. Controls muscles of facial expression and stapedius, carries taste from the anterior 2/3 of the tongue (chorda tympani), and parasympathetic innervation of lacrimal, submandibular, and sublingual glands.",
           ("cn vii", "cn 7", "cranial nerve 7", "cranial nerve vii", "facial nerve"), ("facial", "expression", "taste", "stapedius", "cn7")),
    _Entry("cn_8", "CN VIII: Vestibulocochlear Nerve (MNI: -16, -30, -39 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:7",
           "Special Sensory (SSA) nerve entering the lateral cerebellopontine angle through the internal acoustic meatus. Its cochlear division transmits hearing from the inner ear cochlea; its vestibular division senses head angular/linear acceleration and gravity for balance and the vestibulo-ocular reflex.",
           ("cn viii", "cn 8", "cranial nerve 8", "cranial nerve viii", "vestibulocochlear"), ("vestibulocochlear", "cochlear", "vestibular", "hearing", "cn8")),
    _Entry("cn_9", "CN IX: Glossopharyngeal Nerve (MNI: -10, -33, -44 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:8",
           "Mixed nerve emerging from the upper medulla (postolivary sulcus) through the jugular foramen. Provides taste and touch to the posterior 1/3 of the tongue, the afferent limb of the gag reflex, carotid body/sinus baroreceptor feedback, parotid gland parasympathetics, and motor control of stylopharyngeus.",
           ("cn ix", "cn 9", "cranial nerve 9", "cranial nerve ix", "glossopharyngeal"), ("glossopharyngeal", "gag", "parotid", "carotid", "cn9")),
    _Entry("cn_10", "CN X: Vagus Nerve (MNI: -10, -34, -48 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:9",
           "Mixed nerve emerging from the medullary postolivary sulcus via the jugular foramen. The body's primary parasympathetic superhighway regulating heart rate, respiration, and thoracic/abdominal viscera down to the splenic flexure, plus motor control of pharynx, larynx (voice), soft palate, and the gag efferent limb.",
           ("cn x", "cn 10", "cranial nerve 10", "cranial nerve x", "vagus", "vagus nerve"), ("vagus", "parasympathetic", "larynx", "heart", "viscera", "cn10")),
    _Entry("cn_11", "CN XI: Spinal Accessory Nerve (MNI: -9, -35, -56 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:10",
           "Motor nerve arising from cervical spinal cord segments C1-C5, ascending through the foramen magnum and exiting via the jugular foramen to innervate the sternocleidomastoid (turns head contralaterally) and trapezius (elevates shoulders).",
           ("cn xi", "cn 11", "cranial nerve 11", "cranial nerve xi", "accessory nerve"), ("accessory", "trapezius", "sternocleidomastoid", "cn11")),
    _Entry("cn_12", "CN XII: Hypoglossal Nerve (MNI: -5, -31, -50 mm)", "Dorothy Atlas · Cranial Nerves I-XII", "cn:11",
           "Pure Motor (GSE) nerve exiting the ventral medulla (preolivary sulcus) through the hypoglossal canal to drive all intrinsic and extrinsic tongue muscles except palatoglossus (CN X).",
           ("cn xii", "cn 12", "cranial nerve 12", "cranial nerve xii", "hypoglossal"), ("hypoglossal", "tongue", "medulla", "cn12")),
    _Entry("cn_overview", "All 12 Cranial Nerves (CN I-XII)", "Dorothy Atlas · Cranial Nerves Overview", "structure:CranialNerves",
           "The 12 bilateral Cranial Nerves are: I Olfactory (smell), II Optic (vision), III Oculomotor (eye muscles/pupil), IV Trochlear (superior oblique, sole dorsal brainstem exit), V Trigeminal (facial sensation & chewing), VI Abducens (lateral eye movement), VII Facial (expression & anterior taste), VIII Vestibulocochlear (hearing & balance), IX Glossopharyngeal (posterior tongue/gag afferent), X Vagus (parasympathetic viscera/larynx), XI Accessory (neck/shoulder), XII Hypoglossal (tongue).",
           ("cranial nerves", "12 cranial nerves", "twelve cranial nerves"), ("cranial", "nerves", "foramen", "brainstem")),
    _Entry("circuit_language", "Language Loop Circuit (Wernicke -> Arcuate -> Broca -> M1)", "Dorothy Atlas · Functional Circuit Simulator", "circuit:language",
           "The canonical left-dominant dorsal language pathway converts acoustic phonemes in Heschl's gyrus (BA 41) into lexical meaning in Wernicke's area (BA 22), streams forward through the Arcuate Fasciculus to Broca's area (BA 44/45) for syntactic and phonological assembly, and activates articulatory motor neurons in ventral M1 (BA 4). Operates across Theta/Gamma speech rhythms (4-8 Hz & 40 Hz).",
           ("language loop", "language circuit", "language pathway", "arcuate fasciculus", "how does speech work"), ("language", "arcuate", "wernicke", "broca", "speech", "circuit")),
    _Entry("circuit_visual", "Visual Pathway (CN II -> LGN -> Meyer's Loop -> V1)", "Dorothy Atlas · Functional Circuit Simulator", "circuit:visual",
           "Retinal ganglion signals travel via the Optic Nerve & Chiasm (CN II) to the thalamic Lateral Geniculate Nucleus (LGN), fan posteriorly through the Optic Radiations (with inferior fibers looping through temporal lobe via Meyer's loop) to Calcarine V1 (BA 17), then split into the Dorsal ('Where/How' Parietal) and Ventral ('What' Fusiform/Temporal) streams.",
           ("visual pathway", "visual circuit", "optic radiation", "meyers loop", "meyer loop", "dorsal stream", "ventral stream"), ("visual", "pathway", "lgn", "meyer", "optic", "dorsal", "ventral")),
    _Entry("circuit_motor", "Motor & Corticospinal Loop (M1 -> Basal Ganglia -> Thalamus -> Spine)", "Dorothy Atlas · Functional Circuit Simulator", "circuit:motor",
           "Voluntary motor commands arise in M1/Premotor cortex (BA 4/6), undergo action selection through the Striatum -> GPi -> VA/VL Thalamus loop and cerebellar error calibration, and descend via the posterior limb of the Internal Capsule and Cerebral Peduncles before ~85-90% cross in the Medullary Pyramids to control contralateral limbs.",
           ("motor loop", "motor pathway", "corticospinal tract", "pyramidal tract", "pyramidal decussation"), ("motor", "corticospinal", "pyramidal", "decussation", "circuit")),
    _Entry("circuit_papez", "Papez Limbic Memory Circuit", "Dorothy Atlas · Functional Circuit Simulator", "circuit:papez",
           "The Papez circuit forms the classical anatomical loop for episodic memory consolidation: Hippocampus -> Fornix -> Mammillary Bodies -> Mammillothalamic Tract -> Anterior Thalamic Nuclei -> Cingulate Gyrus -> Cingulum Bundle -> Parahippocampal / Entorhinal Cortex -> back to Hippocampus.",
           ("papez circuit", "papez memory", "memory circuit", "fornix", "mammillary bodies"), ("papez", "memory", "fornix", "mammillary", "cingulum", "hippocampus")),
    _Entry("vasc_willis", "Circle of Willis & Cerebral Blood Supply (MNI: 0, -2, -16 mm)", "Dorothy Atlas · Cerebrovascular Tree", "structure:Vascular",
           "The Circle of Willis is an anastomotic arterial ring at the base of the brain uniting the Anterior Circulation (paired Internal Carotid Arteries -> ACA, ACom, MCA) with the Posterior Circulation (Vertebral -> Basilar -> PCA, PCom, SCA, AICA, PICA). It delivers ~15-20% of total cardiac output to sustain ~20% of the body's resting oxygen demand, draining via valveless Dural Venous Sinuses.",
           ("circle of willis", "cerebral blood", "blood supply", "cerebral arteries", "dural venous sinuses"), ("willis", "artery", "arteries", "vascular", "circulation", "blood")),
    _Entry("vasc_mca", "Middle Cerebral Artery (MCA) Territory", "Dorothy Atlas · Vascular Territory Simulator", "vasc:mcaL",
           "The Middle Cerebral Artery (MCA) perfuses the lateral frontal, parietal, and superior temporal convexities plus deep basal ganglia and internal capsule via lenticulostriate perforators. Classical educational localization of an MCA occlusion involves contralateral face & arm > leg weakness/sensory loss, plus aphasia (if dominant hemisphere, BA 44/45/22) or hemispatial neglect (non-dominant).",
           ("mca", "middle cerebral artery", "mca stroke", "lenticulostriate"), ("mca", "middle", "cerebral", "artery", "stroke", "aphasia")),
    _Entry("vasc_aca", "Anterior Cerebral Artery (ACA) Territory", "Dorothy Atlas · Vascular Territory Simulator", "vasc:aca",
           "The Anterior Cerebral Artery (ACA) supplies the medial frontal and parietal lobes, paracentral lobule, and anterior four-fifths of the corpus callosum. Classical educational localization of ACA ischemia involves contralateral leg > arm weakness and sensory loss, alongside frontal abulia or behavioral disinhibition.",
           ("aca", "anterior cerebral artery", "aca stroke", "pericallosal"), ("aca", "anterior", "cerebral", "paracentral", "abulia")),
    _Entry("vasc_pca", "Posterior Cerebral Artery (PCA) Territory", "Dorothy Atlas · Vascular Territory Simulator", "vasc:pca",
           "The Posterior Cerebral Artery (PCA) branches from the top of the Basilar Artery to supply the occipital lobe (calcarine V1), inferior/medial temporal lobe, splenium, and posterior thalamus. Classical educational localization includes contralateral homonymous hemianopia (often with macular sparing from MCA collaterals).",
           ("pca", "posterior cerebral artery", "pca stroke", "basilar artery"), ("pca", "posterior", "basilar", "hemianopia", "occipital")),
    _Entry("layers_6", "Six-Layer Neocortical Cytoarchitecture (Layers I-VI)", "Dorothy Atlas · Cortical Microcircuitry", "ba:1",
           "Canonical neocortex is organized into 6 layers from pial surface to white matter: Layer I (Molecular: apical dendritic tufts & top-down modulation), Layer II (External Granular: local intracortical links), Layer III (External Pyramidal: corticocortical & callosal output), Layer IV (Internal Granular: primary thalamic sensory INPUT, thick with Stria of Gennari in V1, absent in agranular M1), Layer V (Internal Pyramidal: subcortical/spinal OUTPUT including giant Betz cells), Layer VI (Multiform: reciprocal corticothalamic feedback).",
           ("cortical layers", "six layers", "6 layers", "neocortex layers", "cytoarchitecture", "layer iv", "layer v", "cajal"), ("layers", "neocortex", "cytoarchitecture", "pyramidal", "stellate", "cajal")),
    _Entry("mod_dopamine", "Dopamine & Neuromodulatory Systems", "Dorothy Atlas · Neuromodulators", "structure:BasalGanglia",
           "Four major Dopamine (DA) pathways arise from SNc, VTA, and hypothalamus: Nigrostriatal (motor initiation via striatum), Mesolimbic (reward prediction & salience to nucleus accumbens), Mesocortical (executive prefrontal cognition), and Tuberoinfundibular (inhibits prolactin). Partner systems include Serotonin (5-HT, Raphe nuclei: mood & sleep), Norepinephrine (Locus Coeruleus: arousal & attention gain), Acetylcholine (Basal Forebrain: cortical arousal & hippocampal memory), Glutamate (fast excitation), and GABA (fast inhibition).",
           ("dopamine", "serotonin", "norepinephrine", "acetylcholine", "glutamate", "gaba", "neurotransmitter", "neurotransmitters", "neuromodulator"), ("dopamine", "serotonin", "norepinephrine", "acetylcholine", "glutamate", "gaba", "neurotransmitter", "synapse")),
    _Entry("dti_tracts", "DTI White-Matter Connectome & Tractography", "Dorothy Atlas · White-Matter Pathways", "structure:WhiteMatter",
           "Diffusion Tensor Imaging (DTI) maps long-range myelinated fiber highways by orientation: Red = Left-Right Commissural (Corpus Callosum, Anterior/Posterior Commissures), Green = Anterior-Posterior Association (Arcuate/SLF, ILF, IFOF, Uncinate, Cingulum), and Blue = Superior-Inferior Projection (Corticospinal Tract, Internal Capsule, Corona Radiata, Fornix, Optic Radiations).",
           ("white matter", "dti", "tractography", "fasciculus", "internal capsule", "connectome"), ("dti", "tractography", "white", "matter", "connectome", "fasciculus", "tracts")),
    _Entry("eeg_waves", "10-20 EEG Cap & Brain Wave Rhythms", "Dorothy Atlas · 19-Electrode 10-20 EEG", "eeg",
           "The International 10-20 EEG system places 19 scalp electrodes (Fp1/2, F7/3/z/4/8, T3/4/5/6, C3/z/4, P3/z/4, O1/2) at proportional skull landmarks. Primary rhythms: Delta (0.5-4 Hz, deep sleep), Theta (4-8 Hz, hippocampal navigation & frontal effort), Alpha/Mu (8-12 Hz, occipital eyes-closed idling & C3/C4 motor imagery), Beta (13-30 Hz, active focus), and Gamma (30-80+ Hz, including 40 Hz synchrony).",
           ("eeg", "10-20", "brain waves", "brainwaves", "alpha wave", "theta wave", "gamma wave", "40 hz", "p300"), ("eeg", "alpha", "beta", "theta", "gamma", "delta", "oscillation", "electrode")),
    _Entry("neurons_ltp", "Neurons, Glia, Action Potentials & Synaptic Plasticity", "Dorothy Atlas · Cellular Neurophysiology", "structure:Cerebellum",
           "The human brain contains ~86 billion neurons (~69 billion in the cerebellum alone) and ~100 trillion synapses, supported by oligodendrocytes (myelin), astrocytes (metabolic & BBB support), and microglia. Neurons fire ~1-2 ms all-or-none action potentials via voltage-gated Na+/K+ channels and adapt through Long-Term Potentiation (LTP: NMDA Ca2+ influx strengthening active AMPA synapses).",
           ("action potential", "how many neurons", "synaptic plasticity", "neuroplasticity", "long term potentiation", "ltp", "myelin", "glia", "astrocyte", "oligodendrocyte"), ("neuron", "neurons", "synapse", "synapses", "axon", "dendrite", "myelin", "plasticity", "ltp")),
    _Entry("mri_space", "MNI152 Space & Brain MRI (T1, T2, fMRI, DTI)", "Dorothy Atlas · Neuroimaging Physics", "structure:Frontal",
           "MNI152 is the standard millimeter brain template averaged from 152 human MRI scans with origin (0, 0, 0) at the Anterior Commissure (+X Right, +Y Anterior, +Z Superior). T1-weighted MRI shows bright white matter, gray cortex, and dark CSF; T2 makes CSF bright; fMRI BOLD tracks oxygenated blood flow shifts; DTI maps white-matter axon geometry. Dorothy bundles live 0.74 mm MNI152 slices synced directly to 3D cutting planes.",
           ("mni152", "mri", "t1 mri", "t2 mri", "fmri", "bold signal", "stereotaxic"), ("mri", "mni152", "icbm152", "fmri", "bold", "t1", "t2", "voxel")),
)


def _extract_cn_target(norm: str) -> int | None:
    match = _CN_NUM_RE.search(norm)
    if not match:
        return None
    tok = match.group(1)
    if tok in _ROMAN_CN:
        return _ROMAN_CN[tok]
    if tok.isdigit() and 1 <= int(tok) <= 12:
        return int(tok)
    return None


def _score_entry(entry: _Entry, norm: str, tokens: Sequence[str], ba_target: str | None, cn_target: int | None) -> int:
    score = 0
    if ba_target is not None and entry.entry_id == f"ba_{ba_target}":
        score += 80
    if cn_target is not None and entry.entry_id == f"cn_{cn_target}":
        score += 85
    for trig in entry.triggers:
        if trig in norm:
            score += 26 if " " in trig else 16
    for tok in tokens:
        for tag in entry.tags:
            if tag == tok:
                score += 9
            elif len(tag) >= 4 and (tag in tok or tok in tag):
                score += 4
    return score


def lookup_neuroscience(raw_input: str) -> NeuroAnswer | None:
    """Lookup an offline Dorothy Brain Observatory neuroanatomy answer."""
    if not raw_input or not raw_input.strip():
        return None
    norm = re.sub(r"['’`]", "", raw_input.lower())
    norm = re.sub(r"[^a-z0-9_+\-\s]", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    if not norm:
        return None
    ba_match = _BA_NUM_RE.search(norm)
    ba_target = ba_match.group(1) if ba_match else None
    cn_target = _extract_cn_target(norm)
    tokens = [t for t in norm.split(" ") if len(t) > 1 and t not in _STOP_WORDS]
    best: _Entry | None = None
    best_score = 0
    for entry in _ENTRIES:
        score = _score_entry(entry, norm, tokens, ba_target, cn_target)
        if score > best_score:
            best_score = score
            best = entry
    if best is None or best_score < 14:
        return None
    return NeuroAnswer(
        title=best.title,
        reply=f"{best.title}\n\n{best.answer}{SCOPE_NOTE}",
        citation=best.citation,
        focus_query=best.focus_query,
        score=best_score,
    )
