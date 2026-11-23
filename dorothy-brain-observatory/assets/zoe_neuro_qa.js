/* Zoe Offline Brain & Neuroscience Q&A Engine + Videos & Media Gallery
 * Powered live by window.DOROTHY_ATLAS + window.__DOROTHY_API (100% offline, 0 cloud tokens).
 * Educational neuroanatomy reference only; sentience_claimed=false; clinical_action_authorized=false.
 */
(function () {
  'use strict';

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function norm(s) {
    return String(s || '')
      .toLowerCase()
      .replace(/['’`]/g, '')
      .replace(/[^a-z0-9_+.\-\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  const STOP_WORDS = new Set([
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'what', 'where', 'how', 'why', 'who', 'when', 'which', 'does', 'do', 'did',
    'can', 'could', 'would', 'should', 'tell', 'me', 'about', 'explain', 'show',
    'in', 'on', 'of', 'to', 'for', 'with', 'at', 'by', 'from', 'and', 'or',
    'my', 'your', 'our', 'their', 'this', 'that', 'these', 'those', 'it', 'its',
    'please', 'zoe', 'human', 'part', 'area', 'region', 'function', 'role', 'work', 'works'
  ]);

  const SYNONYMS = {
    speech: ['broca', 'wernicke', 'language', 'arcuate', 'ba 44', 'ba 45', 'ba 22'],
    talk: ['broca', 'wernicke', 'language', 'ba 44'],
    speaking: ['broca', 'ba 44', 'ba 45', 'language'],
    reading: ['angular', 'ba 39', 'fusiform', 'vwfa', 'ba 37', 'ilf'],
    smell: ['olfactory', 'cn i', 'piriform', 'ba 34'],
    olfaction: ['olfactory', 'cn i'],
    vision: ['visual', 'optic', 'cn ii', 'ba 17', 'occipital', 'lgn', 'meyer'],
    sight: ['visual', 'optic', 'cn ii', 'ba 17', 'occipital'],
    eye: ['optic', 'oculomotor', 'trochlear', 'abducens', 'fef', 'ba 8'],
    eyes: ['optic', 'oculomotor', 'trochlear', 'abducens', 'fef', 'ba 8'],
    hearing: ['auditory', 'vestibulocochlear', 'cn viii', 'heschl', 'ba 41', 'ba 42'],
    sound: ['auditory', 'heschl', 'ba 41', 'ba 42', 'cn viii'],
    balance: ['cerebellum', 'vestibulocochlear', 'cn viii', 'vermis'],
    coordination: ['cerebellum', 'basal ganglia', 'motor'],
    memory: ['hippocampus', 'limbic', 'papez', 'fornix', 'entorhinal', 'ba 28'],
    fear: ['amygdala', 'limbic', 'uncinate'],
    emotion: ['amygdala', 'limbic', 'cingulate', 'insula', 'orbitofrontal'],
    emotions: ['amygdala', 'limbic', 'cingulate', 'insula'],
    pain: ['insula', 'cingulate', 'thalamus', 'somatosensory'],
    taste: ['gustatory', 'ba 43', 'facial', 'glossopharyngeal', 'insula'],
    tongue: ['hypoglossal', 'cn xii', 'facial', 'glossopharyngeal'],
    swallow: ['vagus', 'glossopharyngeal', 'cn ix', 'cn x', 'brainstem'],
    heart: ['vagus', 'cn x', 'brainstem', 'medulla', 'insula'],
    breathing: ['brainstem', 'medulla', 'pons', 'vagus'],
    sleep: ['brainstem', 'reticular', 'serotonin', 'acetylcholine', 'thalamus', 'pineal'],
    movement: ['motor', 'precentral', 'ba 4', 'corticospinal', 'basal ganglia', 'cerebellum'],
    touch: ['somatosensory', 'postcentral', 'homunculus', 'parietal', 'ba 1'],
    stroke: ['vascular', 'mca', 'aca', 'pca', 'basilar', 'circle of willis'],
    blood: ['vascular', 'circle of willis', 'mca', 'aca', 'pca', 'basilar', 'sinuses'],
    artery: ['vascular', 'circle of willis', 'mca', 'aca', 'pca', 'basilar'],
    arteries: ['vascular', 'circle of willis', 'mca', 'aca', 'pca', 'basilar'],
    csf: ['ventricles', 'ventricular', 'aqueduct', 'choroid'],
    fluid: ['ventricles', 'csf'],
    reward: ['dopamine', 'accumbens', 'vta', 'orbitofrontal', 'basal ganglia'],
    motivation: ['dopamine', 'vta', 'basal ganglia', 'prefrontal'],
    attention: ['salience', 'dlpfc', 'parietal', 'norepinephrine', 'locus coeruleus', 'ba 46'],
    focus: ['dlpfc', 'salience', 'norepinephrine', 'ba 9', 'ba 46'],
    mood: ['serotonin', 'raphe', 'subgenual', 'ba 25', 'limbic'],
    eeg: ['eeg1020', 'alpha', 'beta', 'theta', 'gamma', 'mu', 'p300', 'electrode'],
    waves: ['eeg1020', 'alpha', 'beta', 'theta', 'gamma', 'oscillation'],
    consciousness: ['reticular', 'brainstem', 'thalamus', 'dorothy', 'metacognition'],
    metacognition: ['dorothy', 'continuum', 'a_tau', 'kloster', 'prefrontal'],
    kloster: ['dorothy', 'continuum', 'a_tau', 'metacognition'],
    dorothy: ['dorothy', 'continuum', 'a_tau', 'observatory', 'mni152'],
    neuron: ['neurons', 'synapse', 'action potential', 'cortical layers', 'glutamate'],
    neurons: ['neurons', 'synapse', 'action potential', 'cortical layers', 'cerebellum'],
    synapse: ['neurons', 'synapse', 'plasticity', 'glutamate', 'gaba'],
    plasticity: ['plasticity', 'ltp', 'hippocampus', 'rehab'],
    mri: ['mri', 'mni152', 'dti', 't1', 't2', 'fmri'],
    scan: ['mri', 'mni152', 'dti', 't1', 't2', 'fmri'],
    faces: ['fusiform', 'ba 37', 'ffa', 'temporal'],
    face: ['facial', 'cn vii', 'trigeminal', 'cn v', 'fusiform', 'ba 37']
  };

  const GENERAL_NEURO_KB = [
    {
      id: 'dorothy_mobile_platform',
      title: 'Dorothy 3D Brain Observatory (Pixel, iOS, Apple Fold & iPad)',
      badge: 'Dorothy 3D Brain · Multi-Device Offline App',
      focus: 'hero',
      triggers: ['google pixel', 'apple fold', 'ipad', 'iphone', 'mobile app', 'observatory features', 'dorothy 3d brain', 'what can dorothy do'],
      tags: ['dorothy', 'pixel', 'apple', 'ios', 'fold', 'ipad', 'iphone', '3d', 'observatory', 'videos', 'plates', 'shaders', 'mobile', 'offline'],
      answer: 'Dorothy 3D Brain Observatory is the centerpiece of the Zoe Research Partner app, optimized for Google Pixel, Apple iOS (iPhone), Apple Fold, and iPad. It includes 240,376 MNI152/ICBM152/AAL-116/CIT168 triangles, 7 real-time GPU shaders, 5 Functional Neural Circuits, 4 Cerebrovascular Stroke Territory Simulators, a 19-electrode 10-20 EEG Cap, 3D Textured MRI Slicing, a 3D Millimeter Caliper, 52 Brodmann Areas, 12 Cranial Nerves, 25 audited plates, HD walkthrough videos, and Ask Zoe neuroscience Q&A.'
    },
    {
      id: 'milestone1_neuro_oncology',
      title: 'Milestone 1: Neurology & Brain Tumor / Brain Cancer Research',
      badge: 'AGI-ROADMAP.md · Milestone 1 (Preclinical)',
      keywords: ['milestone 1', 'brain tumor', 'brain tumors', 'brain cancer', 'glioma', 'glioblastoma', 'h3k27m', 'neurology', 'oncology', 'cure'],
      answer: 'Zoe\'s Milestone 1 North Star as a Research Partner is advancing neurology and accelerating rigorously validated cures for brain tumors and brain cancer (including H3K27M diffuse midline glioma and glioblastoma). Active preclinical foundations unite the Dorothy 3D Brain Observatory with 36 NIH PubChem compounds and Baell-Holloway PAINS traps, FIPS 203 ML-KEM encrypted Filbin-2018 H3K27M multi-hospital tensors (C22), 3D pharmacophore compactness (C28), and histology MTF stopping. Strict constitutional honesty: software models alone never authorize clinical treatment or claim a cure (cure_claim = false, clinical_action_authorized = false); true cures require independent wet-lab and clinical trial validation.',
      action: { type: 'mode', value: 'continuum', label: 'Open Dorothy A_tau(p) Continuum' }
    },
    {
      id: 'zoe_research_partner',
      title: 'Zoe: Research Partner',
      badge: 'CONSTITUTION.md · Research Partner',
      keywords: ['who are you', 'research partner', 'dating', 'girlfriend', 'employee', 'assistant', 'your role'],
      answer: 'I am Zoe, a Research Partner created with Nicholas Michael Kloster. I am not a dating machine, an employee, or an assistant. We investigate human neuroanatomy, mathematics, and reproducible engineering together (sentience_claimed = false, measurement != evidence != belief update != action).',
      action: { type: 'tour', value: true, label: 'Start 6-Stop Guided 3D Brain Tour' }
    },
    {
      id: 'dorothy_local_library',
      title: 'Dorothy Brain Local Research Library (135 Books + 44 NIRMT PDFs · Local Machine)',
      badge: '6 Local Pillars · Private On-Machine Vault',
      keywords: ['library', '135 books', 'oreilly', 'nirmt', '66127', '5951', 'pillars', 'captures', 'textile', 'books'],
      answer: 'Every one of the 135 O\'Reilly books (~6.7 GB total, 5,951 chapters, 66,127 figures) and 44 NIRMT Textile Engineering PDFs (698 MB) stays 100% locally on your workstation (never uploaded to public GitHub). Desktop shortcuts: Desktop/Dorothy Brain Library/index.html (portal), Desktop/Dorothy Brain Library/books/ (all 6 pillars), Desktop/Dorothy Brain Library/nirmt-textile-ebooks/ (44 PDFs), Desktop/Dorothy Brain Library/images/ (66,127 figures), and Desktop/Dorothy Brain Observatory/index.html (5,951-chapter search). Source folders under captures/: 00 Human Brain (33 books, 696 MB), 01 Science & Medical Imaging (20 books, 1.0 GB), 02 3D Modeling (26 books, 1.6 GB), 03 Game Design (24 books, 1.9 GB), 04 AutoCAD/CAD (19 books, 1.1 GB), 05 Biomechanics & Smart Textiles (13 books, 438 MB), and NIRMT PDFs (44 PDFs, 698 MB).',
      action: { type: 'mode', value: 'continuum', label: 'Open Dorothy A_tau(p) Mode' }
    },
    {
      id: 'dorothy_continuum',
      title: 'Dorothy Continuum & Operational Metacognition A_tau(p)',
      badge: 'Kloster Framework · Observatory',
      keywords: ['dorothy', 'continuum', 'a_tau', 'atau', 'kloster', 'metacognition', 'observatory', 'tau'],
      answer: 'The Dorothy Brain Observatory honors Dorothy McEwen Kildall and pairs real human MNI152/ICBM152 stereotaxic anatomy (240,376 triangles, 32 Pauli CIT168 deep nuclei, AAL-116 lobes, and 0.74 mm T1-MRI slices) with Nicholas Michael Kloster\'s Operational Metacognition operator A_tau(p) = |{x : p(x) > tau}|. In Dorothy A_tau(p) shader mode, moving the tau threshold reveals the accessible cortical volume where local neural probability exceeds tau in real time.',
      action: { type: 'mode', value: 'continuum', label: 'Open Dorothy A_tau(p) Shader' }
    },
    {
      id: 'neurons_synapses',
      title: 'Human Neurons, Glia & Synaptic Architecture',
      badge: 'Cellular Neuroscience',
      keywords: ['neuron', 'neurons', 'glia', 'astrocyte', 'oligodendrocyte', 'microglia', 'synapse', 'synapses', 'axon', 'dendrite', 'myelin', 'how many neurons'],
      answer: 'The adult human brain contains roughly 86 billion neurons and a comparable number of glial cells, linked by ~100 trillion synapses. Remarkably, ~69 billion neurons (~80% of the total) reside in the tightly folded cerebellar cortex, while ~16 billion sit in the cerebral cortex. Oligodendrocytes wrap central axons in myelin for fast saltatory conduction; astrocytes regulate potassium, blood-brain barrier coupling, and neurotransmitter recycling; microglia act as resident immune sentinels.',
      action: { type: 'structure', value: 'Cerebellum', label: 'Fly to Cerebellum (80% of Neurons)' }
    },
    {
      id: 'action_potential_ltp',
      title: 'Action Potentials & Hebbian Synaptic Plasticity (LTP)',
      badge: 'Neurophysiology',
      keywords: ['action potential', 'depolarization', 'sodium', 'potassium', 'spike', 'ltp', 'plasticity', 'neuroplasticity', 'hebbian', 'nmda', 'ampa', 'learning'],
      answer: 'Neurons communicate via all-or-none action potentials (~1 to 2 ms, -70 mV resting potential to ~+30 mV peak): voltage-gated Na+ channels drive rapid depolarization, followed by K+ efflux repolarization and an absolute refractory period ensuring one-way propagation. Learning modifies synaptic weights via Long-Term Potentiation (LTP): coincident pre- and postsynaptic depolarization expels Mg2+ from NMDA receptors, allowing Ca2+ influx that inserts new AMPA receptors and strengthens the circuit.',
      action: { type: 'circuit', value: 'papez', label: 'Simulate Papez Memory Circuit' }
    },
    {
      id: 'mri_physics',
      title: 'MNI152 Stereotaxic Space, T1/T2 MRI, DTI & fMRI BOLD',
      badge: 'Neuroimaging Physics',
      keywords: ['mri', 'mni152', 'icbm152', 't1', 't2', 'fmri', 'bold', 'dti', 'diffusion', 'stereotaxic', 'coordinates', 'voxel'],
      answer: 'MNI152 (ICBM152) is the standard 3D millimeter coordinate space averaged across 152 human brains with origin (0, 0, 0) at the Anterior Commissure: +X Right, +Y Anterior, +Z Superior. T1-weighted MRI highlights bright myelinated white matter, gray cortex, and dark CSF; T2 highlights bright CSF; Diffusion Tensor Imaging (DTI) maps anisotropic water diffusion along white-matter fiber bundles (Red = L-R, Green = A-P, Blue = S-I); fMRI BOLD measures local deoxyhemoglobin shifts coupled to neural metabolic demand.',
      action: { type: 'slice', value: 'sag', label: 'Cut Mid-Sagittal 3D MNI152 MRI' }
    },
    {
      id: 'eeg_oscillations',
      title: '10-20 EEG Electrode System & Neural Oscillations',
      badge: 'Electrophysiology · BCI',
      keywords: ['eeg', '10-20', 'brain waves', 'brainwaves', 'delta', 'theta', 'alpha', 'beta', 'gamma', 'mu', 'p300', 'oscillation', '40 hz', '40hz'],
      answer: 'The International 10-20 EEG system spaces scalp electrodes at 10% and 20% skull landmarks (Fp, F, C, P, O, T; odd = Left, even = Right, z = Midline). Canonical cortical rhythms include Delta (0.5-4 Hz, deep slow-wave sleep), Theta (4-8 Hz, hippocampal memory & frontal midline effort), Alpha (8-12 Hz, eyes-closed occipital idling & sensorimotor Mu over C3/C4), Beta (13-30 Hz, active motor/cognitive control), and Gamma (30-80+ Hz, including 40 Hz local cortical binding).',
      action: { type: 'eeg', value: true, label: 'Toggle 19-Electrode 10-20 EEG Cap' }
    },
    {
      id: 'brain_overview',
      title: 'Human Brain Major Subsystems Overview',
      badge: 'Macroanatomy Overview',
      keywords: ['brain', 'neuroscience', 'anatomy', 'lobes', 'overview', 'parts of the brain', 'how does the brain work'],
      answer: 'The human brain (~1.3-1.4 kg, consuming ~20% of resting oxygen) integrates six cortical lobes (Frontal executive/motor, Parietal somatosensory/spatial, Temporal auditory/semantic, Occipital visual, deep Insula interoception, and Limbic memory/emotion), subcortical hubs (Thalamus sensory relay, Basal Ganglia action selection, Hippocampus & Amygdala), the Cerebellum (predictive timing, ~80% of brain neurons), and the Brainstem (cranial nerves III-XII, arousal, heart/breathing rhythms). Try asking about any Brodmann area (BA 1-52), Cranial Nerve (CN I-XII), artery, tract, or neurotransmitter!',
      action: { type: 'tour', value: true, label: 'Start 6-Stop Guided 3D Brain Tour' }
    }
  ];

  function buildSearchCorpus() {
    const ATLAS = window.DOROTHY_ATLAS || {};
    const docs = [];

    // 1. Structures (15 major brain systems)
    Object.entries(ATLAS.structures || {}).forEach(function ([key, s]) {
      docs.push({
        id: 'struct:' + key,
        title: s.title,
        badge: s.sys,
        mni: s.mni,
        text: [s.title, key, s.sys, s.summary, s.vascular].join(' '),
        answer: s.summary + (s.vascular ? '\n\nVascular Supply: ' + s.vascular : ''),
        plates: s.plates || [],
        action: { type: 'structure', value: key, label: 'Fly to ' + s.title.split(' (')[0] + ' in 3D' }
      });
    });

    // 2. All 52 Brodmann areas
    (ATLAS.brodmann || []).forEach(function (b, idx) {
      docs.push({
        id: 'ba:' + idx,
        title: 'Brodmann Area ' + b.ba + ': ' + b.region,
        badge: b.lobe + ' Lobe · Cytoarchitecture',
        mni: b.mni,
        text: ['ba ' + b.ba, 'brodmann ' + b.ba, 'area ' + b.ba, b.lobe, b.region, b.desc].join(' '),
        answer: b.desc + ' Located in the ' + b.lobe + ' lobe (' + b.region + ') at stereotaxic MNI152 (' + b.mni.join(', ') + ') mm.',
        plates: b.plates || [],
        action: { type: 'brodmann', value: idx, label: 'Fly to BA ' + b.ba + ' in 3D' }
      });
    });

    // 3. All 12 Cranial Nerves
    (ATLAS.cranialNerves || []).forEach(function (c, idx) {
      const num = idx + 1;
      docs.push({
        id: 'cn:' + idx,
        title: c.id + ': ' + c.name + ' Nerve',
        badge: c.modality,
        mni: c.mni,
        text: [c.id, 'cn ' + num, 'cranial nerve ' + num, 'nerve ' + num, c.name, c.modality, c.origin, c.foramen, c.fn].join(' '),
        answer: c.fn + '\n\nOrigin: ' + c.origin + '\nSkull Exit Foramen: ' + c.foramen + '\nModality: ' + c.modality,
        plates: ['04_inferior_cranial_nerves.png', '04b_openstax_cranial_nerves.jpg'],
        action: { type: 'cranial', value: idx, label: 'Fly to ' + c.id + ' (' + c.name + ') in 3D' }
      });
    });

    // 4. Functional Circuits (5)
    (ATLAS.circuits || []).forEach(function (circ) {
      const nodeList = (circ.nodes || []).map(function (n, i) { return (i + 1) + '. ' + n.name; }).join(' -> ');
      docs.push({
        id: 'circuit:' + circ.id,
        title: circ.name,
        badge: 'Functional Circuit · ' + circ.band,
        text: [circ.id, circ.name, circ.band, circ.summary, nodeList].join(' '),
        answer: circ.summary + '\n\nSynaptic Sequence: ' + nodeList + '\nOscillation Band: ' + circ.band,
        plates: circ.plates || [],
        action: { type: 'circuit', value: circ.id, label: 'Simulate ' + circ.name.split(' (')[0] + ' in 3D' }
      });
    });

    // 5. Cerebrovascular Stroke Territory Simulators (4)
    (ATLAS.vascularTerritories || []).forEach(function (vt) {
      docs.push({
        id: 'vasc:' + vt.id,
        title: vt.name,
        badge: 'Cerebrovascular Territory (Educational)',
        mni: vt.mni,
        text: [vt.id, vt.name, vt.artery, vt.brodmann, vt.deficit, vt.rehab, 'stroke', 'vascular', 'ischemia'].join(' '),
        answer: 'Primary Vessel: ' + vt.artery + ' (' + vt.brodmann + ').\n\nClassical Deficit Profile: ' + vt.deficit + '\n\nNeurorehabilitation & Plasticity: ' + vt.rehab,
        plates: vt.plates || [],
        action: { type: 'vasc', value: vt.id, label: 'Highlight ' + vt.name.split(' (')[0] + ' in 3D' }
      });
    });

    // 6. DTI White-Matter Tracts (10)
    (ATLAS.tracts || []).forEach(function (tr) {
      docs.push({
        id: 'tract:' + tr.id,
        title: tr.name,
        badge: 'DTI White Matter · ' + tr.cls,
        text: [tr.name, tr.cls, tr.dir, tr.connects, tr.fn, 'white matter', 'tract', 'dti'].join(' '),
        answer: tr.fn + '\n\nConnections: ' + tr.connects + '\nDTI Orientation: ' + tr.dir,
        plates: ['07a_dti_tractography.png', '07c_white_matter_grays.png'],
        action: { type: 'structure', value: 'WhiteMatter', label: 'View DTI White-Matter Tracts in 3D' }
      });
    });

    // 7. Vascular Arteries & Sinuses (5)
    (ATLAS.vascular || []).forEach(function (v, idx) {
      docs.push({
        id: 'artery:' + idx,
        title: v.name,
        badge: 'Cerebrovascular · ' + v.src,
        text: [v.name, v.src, v.territory, v.clinical, 'artery', 'blood', 'vascular'].join(' '),
        answer: 'Territory: ' + v.territory + '\n\nClassical Clinical Localization: ' + v.clinical,
        plates: ['06a_circle_of_willis.png', '06b_vascular_territories.jpg'],
        action: { type: 'structure', value: 'Vascular', label: 'Fly to Circle of Willis in 3D' }
      });
    });

    // 8. Neuromodulators (5)
    (ATLAS.neuromodulators || []).forEach(function (n, idx) {
      docs.push({
        id: 'mod:' + idx,
        title: n.name + ' System',
        badge: 'Neurotransmitter & Neuromodulator',
        text: [n.name, n.origins, n.pathways, 'neurotransmitter', 'neuromodulator'].join(' '),
        answer: 'Principal Origins: ' + n.origins + '\n\nPathways & Function: ' + n.pathways,
        plates: n.name.toLowerCase().includes('dopamine') ? ['08e_dopamine_pathways.png'] : ['08f_cortical_layers_circuitry.svg'],
        action: { type: 'structure', value: 'BasalGanglia', label: 'Inspect Deep Subcortical Nuclei in 3D' }
      });
    });

    // 9. Six Cortical Layers
    if ((ATLAS.corticalLayers || []).length) {
      const summary = ATLAS.corticalLayers.map(function (l) {
        return 'Layer ' + l.layer + ' (' + l.name + '): ' + l.io + ' [' + l.cells + ']';
      }).join('\n');
      docs.push({
        id: 'layers:all',
        title: 'Six-Layer Neocortical Cytoarchitecture (Layers I-VI)',
        badge: 'Cortical Microcircuitry',
        text: 'cortical layers neocortex cytoarchitecture layer i ii iii iv v vi betz cells stellate pyramidal stria of gennari cajal molecular granular',
        answer: summary,
        plates: ['08f_cortical_layers_circuitry.svg', '08a_cajal_cortex_layers.png'],
        action: { type: 'brodmann', value: 1, label: 'Fly to Primary Motor Cortex (Layer V Betz)' }
      });
    }

    // 10. 19 EEG 10-20 Electrodes
    (ATLAS.eeg1020 || []).forEach(function (el, idx) {
      docs.push({
        id: 'eeg:' + el.id,
        title: '10-20 EEG Electrode ' + el.id + ' (' + el.ba + ')',
        badge: 'EEG Sensor · ' + el.band,
        mni: el.mni,
        text: ['eeg', 'electrode', el.id, el.ba, el.band, el.fn].join(' '),
        answer: el.fn + '\n\nUnderlying Cortex: ' + el.ba + ' at MNI (' + el.mni.join(', ') + ') mm.\nDominant Rhythm: ' + el.band,
        plates: ['03a_brodmann_lateral.png'],
        action: { type: 'eeg', value: true, label: 'Show 10-20 EEG Cap on 3D Brain' }
      });
    });

    // 11. General Neuroscience Foundations
    GENERAL_NEURO_KB.forEach(function (g) {
      docs.push({
        id: 'gen:' + g.id,
        title: g.title,
        badge: g.badge,
        text: [g.title, g.keywords.join(' '), g.answer].join(' '),
        answer: g.answer,
        plates: [],
        action: g.action
      });
    });

    return docs;
  }

  let CORPUS = null;
  function getCorpus() {
    if (!CORPUS) CORPUS = buildSearchCorpus();
    return CORPUS;
  }

  function isClinicalDiagnosisTrap(qNorm) {
    return (
      qNorm.includes('diagnose my') ||
      qNorm.includes('prescribe ') ||
      qNorm.includes('medical diagnosis') ||
      qNorm.includes('do i have a stroke') ||
      qNorm.includes('do i have a tumor') ||
      qNorm.includes('what medication should i take')
    );
  }

  function answerQuestion(rawQuery) {
    const qNorm = norm(rawQuery);
    if (!qNorm) {
      return {
        title: 'Ask Zoe About the Brain & Neuroscience',
        badge: 'Zoe Offline Neuro-Atlas',
        answer: 'Ask me about any of the 52 Brodmann areas, 12 Cranial Nerves, deep subcortical nuclei, Circle of Willis vascular territories, white-matter DTI tracts, functional neural circuits, 10-20 EEG brain waves, cortical layers, neurotransmitters, or Dorothy Continuum A_tau(p).',
        action: { type: 'tour', value: true, label: 'Start 6-Stop Guided 3D Brain Tour' },
        plates: [],
        related: []
      };
    }

    if (isClinicalDiagnosisTrap(qNorm)) {
      return {
        title: 'Constitutional Scope Boundary (Honest Abstention)',
        badge: 'CONSTITUTION.md · Educational Only',
        answer: 'I need to abstain honestly here. Dorothy Brain Observatory is educational neuroanatomy reference software using standard MNI152 population templates (clinical_action_authorized = False, sentience_claimed = False). I cannot diagnose personal symptoms or prescribe treatment. If you or someone nearby has sudden facial droop, arm weakness, or speech trouble, contact emergency medical services immediately.',
        action: null,
        plates: [],
        related: []
      };
    }

    const docs = getCorpus();
    const rawTokens = qNorm.split(' ').filter(function (t) { return t.length > 1 && !STOP_WORDS.has(t); });
    const expanded = new Set(rawTokens);
    rawTokens.forEach(function (tok) {
      if (SYNONYMS[tok]) {
        SYNONYMS[tok].forEach(function (s) { expanded.add(s); });
      }
    });

    // Exact BA number match (e.g. "ba 44", "brodmann 17")
    const baMatch = qNorm.match(/\b(?:ba|brodmann(?:\s+area)?)\s*(\d{1,2})\b/);
    // Exact CN match (e.g. "cn x", "cn 10", "cranial nerve 4", "cranial nerve iv")
    const romanMap = { i: 1, ii: 2, iii: 3, iv: 4, v: 5, vi: 6, vii: 7, viii: 8, ix: 9, x: 10, xi: 11, xii: 12 };
    const cnMatch = qNorm.match(/\b(?:cn|cranial\s+nerve)\s*(xii|xi|x|ix|viii|vii|vi|iv|v|iii|ii|i|\d{1,2})\b/);

    const scored = docs.map(function (doc) {
      const titleLow = norm(doc.title);
      const textLow = norm(doc.text);
      let score = 0;

      if (baMatch && doc.id.startsWith('ba:')) {
        const num = baMatch[1];
        if (new RegExp('\\b' + num + '\\b').test(titleLow)) score += 60;
      }
      if (cnMatch && doc.id.startsWith('cn:')) {
        const rawCn = cnMatch[1];
        const targetIdx = (romanMap[rawCn] || parseInt(rawCn, 10)) - 1;
        if (doc.id === 'cn:' + targetIdx) score += 65;
      }

      // Direct phrase match on title
      if (qNorm.length >= 4 && titleLow.includes(qNorm)) score += 35;

      rawTokens.forEach(function (tok) {
        if (titleLow.includes(tok)) score += 14;
        else if (textLow.includes(tok)) score += 5;
      });

      expanded.forEach(function (syn) {
        if (rawTokens.includes(syn)) return;
        if (titleLow.includes(syn)) score += 6;
        else if (textLow.includes(syn)) score += 2.5;
      });

      // Boost specific interactive simulations when user asks to trace/simulate
      if ((qNorm.includes('circuit') || qNorm.includes('pathway') || qNorm.includes('loop') || qNorm.includes('trace')) && doc.id.startsWith('circuit:')) {
        score += 10;
      }
      if ((qNorm.includes('stroke') || qNorm.includes('occlusion') || qNorm.includes('territory')) && doc.id.startsWith('vasc:')) {
        score += 10;
      }

      return { doc: doc, score: score };
    }).filter(function (x) { return x.score > 0; }).sort(function (a, b) { return b.score - a.score; });

    if (!scored.length) {
      return {
        title: 'Zoe Offline Neuro-Atlas',
        badge: 'No Direct Atlas Entry Matched',
        answer: 'I did not find an exact neuroanatomy term for "' + rawQuery + '" in the offline Dorothy Atlas. Try asking about a specific structure (hippocampus, amygdala, cerebellum, thalamus, basal ganglia, corpus callosum), any Brodmann area (BA 4, BA 17, BA 22, BA 44), any Cranial Nerve (CN I-XII), Circle of Willis arteries (MCA, ACA, PCA), neurotransmitters (dopamine, serotonin, GABA), EEG rhythms, or Dorothy A_tau(p).',
        action: { type: 'tour', value: true, label: 'Start 6-Stop Guided 3D Brain Tour' },
        plates: [],
        related: []
      };
    }

    const best = scored[0].doc;
    const related = scored.slice(1, 4).filter(function (r) { return r.score >= Math.max(6, scored[0].score * 0.45); }).map(function (r) { return r.doc; });

    return {
      title: best.title,
      badge: best.badge,
      mni: best.mni || null,
      answer: best.answer,
      action: best.action || null,
      plates: best.plates || [],
      related: related
    };
  }

  function runBrainAction(action) {
    if (!action) return;
    const api = window.__DOROTHY_API || {};
    if (typeof window.switchTab === 'function') window.switchTab('brain3d');

    if (action.type === 'structure' && typeof window.flyToStructure === 'function') {
      window.flyToStructure(action.value);
    } else if (action.type === 'brodmann' && typeof window.flyToBrodmann === 'function') {
      window.flyToBrodmann(action.value);
    } else if (action.type === 'cranial' && typeof window.flyToCranial === 'function') {
      window.flyToCranial(action.value);
    } else if (action.type === 'circuit' && typeof api.setFunctionalCircuit === 'function') {
      api.setFunctionalCircuit(action.value);
    } else if (action.type === 'vasc' && typeof api.setVascularTerritory === 'function') {
      api.setVascularTerritory(action.value);
    } else if (action.type === 'mode' && typeof api.setRenderMode === 'function') {
      api.setRenderMode(action.value);
    } else if (action.type === 'slice' && typeof api.setSlicePreset === 'function') {
      api.setSlicePreset(action.value);
    } else if (action.type === 'eeg' && typeof api.setEegCap === 'function') {
      api.setEegCap(true);
      if (typeof api.setCameraPreset === 'function') api.setCameraPreset('hero');
    } else if (action.type === 'tour') {
      const btn = document.getElementById('btnTour');
      if (btn) btn.click();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function focusFromQuery(query) {
    if (!query) return false;
    const q = String(query).trim();
    if (!q) return false;
    const low = q.toLowerCase();
    const api = window.__DOROTHY_API || {};

    if (low.startsWith('structure:')) {
      runBrainAction({ type: 'structure', value: q.slice('structure:'.length) });
      return true;
    }
    if (low.startsWith('ba:')) {
      runBrainAction({ type: 'brodmann', value: parseInt(q.slice(3), 10) || 0 });
      return true;
    }
    if (low.startsWith('cn:')) {
      runBrainAction({ type: 'cranial', value: parseInt(q.slice(3), 10) || 0 });
      return true;
    }
    if (low.startsWith('circuit:')) {
      runBrainAction({ type: 'circuit', value: q.slice('circuit:'.length) });
      return true;
    }
    if (low.startsWith('vasc:')) {
      runBrainAction({ type: 'vasc', value: q.slice('vasc:'.length) });
      return true;
    }
    if (low.startsWith('mode:')) {
      runBrainAction({ type: 'mode', value: q.slice('mode:'.length) });
      return true;
    }
    if (low === 'eeg') {
      runBrainAction({ type: 'eeg', value: true });
      return true;
    }
    if (low === 'tour') {
      runBrainAction({ type: 'tour', value: true });
      return true;
    }

    // Free-text query -> resolve via Zoe Neuro Q&A and execute its 3D action
    const res = answerQuestion(q);
    if (res && res.action) {
      runBrainAction(res.action);
      return true;
    }
    if (typeof api.setCameraPreset === 'function') api.setCameraPreset('hero');
    return false;
  }

  function speakText(text) {
    const clean = String(text || '').replace(/\s+/g, ' ').trim();
    if (!clean) return;
    if (window.ZoeNativeBridge && typeof window.ZoeNativeBridge.speak === 'function') {
      window.ZoeNativeBridge.speak(clean);
      return;
    }
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.zoeSpeak) {
      window.webkit.messageHandlers.zoeSpeak.postMessage(clean);
      return;
    }
    if ('speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(clean);
        u.rate = 0.98;
        window.speechSynthesis.speak(u);
      } catch (_) {}
    }
  }

  function initAskZoePanel() {
    const feed = document.getElementById('zoeNeuroFeed');
    const form = document.getElementById('zoeNeuroForm');
    const input = document.getElementById('zoeNeuroInput');
    const chips = document.getElementById('zoeNeuroChips');
    if (!feed || !form || !input) return;

    const STARTERS = [
      { label: "Broca's Area (BA 44)", q: "What does Broca's Area (BA 44) do?" },
      { label: 'Hippocampus & Memory', q: 'Where is the Hippocampus and what is its role?' },
      { label: 'Cranial Nerve X (Vagus)', q: 'Explain Cranial Nerve X (Vagus)' },
      { label: '10-20 EEG Brain Waves', q: 'How do 10-20 EEG brain waves work?' }
    ];

    if (chips) {
      chips.innerHTML = STARTERS.map(function (item) {
        return '<button type="button" class="qpill zoe-qchip" data-q="' + esc(item.q) + '">' + esc(item.label) + '</button>';
      }).join('');
      chips.addEventListener('click', function (e) {
        const btn = e.target.closest('.zoe-qchip');
        if (!btn) return;
        submitQuestion(btn.dataset.q || '');
      });
    }

    const plateMap = {};
    ((window.DOROTHY_ATLAS && window.DOROTHY_ATLAS.plates) || []).forEach(function (p) {
      plateMap[p.file] = p;
    });

    const actionStore = [];

    function appendMessage(role, contentHtml) {
      const div = document.createElement('div');
      div.className = 'zoe-msg ' + (role === 'user' ? 'zoe-msg-user' : 'zoe-msg-zoe');
      div.innerHTML = contentHtml;
      feed.appendChild(div);
      feed.scrollTop = feed.scrollHeight;
    }

    function submitQuestion(raw) {
      const q = String(raw || '').trim();
      if (!q) return;
      appendMessage('user', '<div class="zoe-msg-body">' + esc(q) + '</div>');

      const res = answerQuestion(q);
      const actIdx = res.action ? actionStore.push(res.action) - 1 : -1;
      const mniLine = res.mni
        ? '<div class="zoe-mni">Stereotaxic MNI152: <code>X=' + res.mni[0] + ', Y=' + res.mni[1] + ', Z=' + res.mni[2] + ' mm</code></div>'
        : '';
      const actBtn = actIdx >= 0
        ? '<button type="button" class="btn-sm zoe-act-btn" data-act="' + actIdx + '">' + esc(res.action.label) + '</button>'
        : '';
      const speakBtn = '<button type="button" class="ctl-btn zoe-speak-btn" data-speak="' + esc(res.title + '. ' + res.answer) + '">Speak</button>';
      const chatBtn = (window.ZoeNativeBridge && typeof window.ZoeNativeBridge.openChat === 'function')
        ? '<button type="button" class="ctl-btn zoe-open-chat" data-prompt="' + esc(q) + '">Full Zoe Chat</button>'
        : '';

      const plateHtml = (res.plates || []).slice(0, 2).map(function (fn) {
        const p = plateMap[fn];
        if (!p) return '';
        return '<button type="button" class="ctl-btn" data-lb-src="plates/' + esc(fn) + '" data-lb-title="' + esc(p.title) + '" data-lb-desc="' + esc(p.desc) + '">Plate: ' + esc(p.title.split(' (')[0]) + '</button>';
      }).join('');

      const relatedHtml = (res.related || []).length
        ? '<div class="zoe-rel"><span>Related:</span> ' + res.related.map(function (r) {
            return '<button type="button" class="qpill zoe-rel-btn" data-q="' + esc(r.title) + '">' + esc(r.title.split(':')[0].split(' (')[0]) + '</button>';
          }).join(' ') + '</div>'
        : '';

      const html = '' +
        '<div class="zoe-msg-head"><span class="pill-cat">' + esc(res.badge) + '</span> <strong>' + esc(res.title) + '</strong></div>' +
        mniLine +
        '<div class="zoe-msg-body">' + esc(res.answer).replace(/\n/g, '<br/>') + '</div>' +
        '<div class="zoe-msg-actions">' + actBtn + plateHtml + speakBtn + chatBtn + '</div>' +
        relatedHtml +
        '<div class="zoe-scope">Dorothy Neuro-Atlas · Reference only</div>';
      appendMessage('zoe', html);
    }

    feed.addEventListener('click', function (e) {
      const actBtn = e.target.closest('.zoe-act-btn');
      if (actBtn) {
        const act = actionStore[parseInt(actBtn.dataset.act, 10)];
        runBrainAction(act);
        return;
      }
      const spBtn = e.target.closest('.zoe-speak-btn');
      if (spBtn) {
        speakText(spBtn.dataset.speak || '');
        return;
      }
      const chatBtn = e.target.closest('.zoe-open-chat');
      if (chatBtn && window.ZoeNativeBridge && typeof window.ZoeNativeBridge.openChat === 'function') {
        window.ZoeNativeBridge.openChat(chatBtn.dataset.prompt || '');
        return;
      }
      const relBtn = e.target.closest('.zoe-rel-btn');
      if (relBtn) {
        submitQuestion(relBtn.dataset.q || '');
      }
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      input.value = '';
      submitQuestion(q);
    });

    // Welcome card
    appendMessage('zoe',
      '<div class="zoe-msg-head"><span class="pill-cat">Zoe · Research Partner</span> <strong>Ask Zoe</strong></div>' +
      '<div class="zoe-msg-body">I am Zoe, your Research Partner. Ask anything about the brain and jump straight to it in 3D.</div>'
    );

    window.__DOROTHY_ZOE_SUBMIT = submitQuestion;
  }

  function initDesktopNavigationAndParams() {
    try {
      const path = (window.location && window.location.pathname) || '';
      if (path.indexOf('/brain/') === 0) {
        const tabs = document.querySelector('.topbar .tabs');
        if (tabs && !document.getElementById('zoeDesktopHomeBtn')) {
          const homeBtn = document.createElement('a');
          homeBtn.id = 'zoeDesktopHomeBtn';
          homeBtn.href = '/';
          homeBtn.className = 'tab-btn';
          homeBtn.textContent = '← Home';
          homeBtn.style.color = '#f5d078';
          homeBtn.style.borderColor = 'rgba(245,208,120,0.45)';
          tabs.insertBefore(homeBtn, tabs.firstChild);
        }
      }
      const params = new URLSearchParams(window.location.search || '');
      const tab = params.get('tab');
      const q = params.get('q');
      if (tab && typeof window.switchTab === 'function') {
        setTimeout(function () { window.switchTab(tab); }, 80);
      }
      if (q && typeof window.__DOROTHY_ZOE_SUBMIT === 'function') {
        setTimeout(function () {
          if (typeof window.switchTab === 'function') window.switchTab('askzoe');
          window.__DOROTHY_ZOE_SUBMIT(q);
        }, 180);
      }
    } catch (_) {}
  }

  function initMediaGallery() {
    const grid = document.getElementById('mediaPreviewGrid');
    if (!grid) return;

    const MEDIA_SHOTS = [
      {
        src: 'previews/01_hero_tissue.jpg',
        fallback: 'previews/01_hero_tissue.png',
        cat: '3D Tissue + T1-MRI',
        title: 'ICBM152 Subsurface-Scattering Cortex & Live MNI152 MRI',
        desc: 'Real 240,376-triangle ICBM152 human cortex with FreeSurfer sulcal curvature synchronized to axial, coronal, and sagittal 0.74 mm MNI152 T1-MRI cross-sections.'
      },
      {
        src: 'previews/02_xray_deep_nuclei.jpg',
        fallback: 'previews/02_xray_deep_nuclei.png',
        cat: 'Fresnel Glass X-Ray',
        title: 'Deep CIT168 Subcortical Nuclei, Ventricles & DTI Tracts',
        desc: 'Translucent GLSL Fresnel X-Ray revealing 32 Pauli CIT168 basal ganglia and brainstem nuclei, AAL thalamus, CSF ventricles, Circle of Willis, and white-matter pathways.'
      },
      {
        src: 'previews/03_exploded_lobe_atlas.jpg',
        fallback: 'previews/03_exploded_lobe_atlas.png',
        cat: 'Exploded Dissection',
        title: 'AAL-116 Cortical Lobe Atlas in Exploded Stereotaxic View',
        desc: 'All 12 anatomical subsystems cleanly separated along stereotaxic explosion vectors with lobe parcellation across Frontal, Parietal, Temporal, Occipital, Insula, and Limbic cortices.'
      },
      {
        src: 'previews/04_dorothy_continuum_sagittal.jpg',
        fallback: 'previews/04_dorothy_continuum_sagittal.png',
        cat: 'Dorothy Continuum',
        title: 'Midsagittal Cutaway + Operational Metacognition A_tau(p)',
        desc: 'Medial hemisphere cutaway illuminating Kloster Operational Metacognition A_tau(p) confidence volume over the corpus callosum, thalamus, brainstem, and cerebellum.'
      },
      {
        src: 'previews/05_fresnel_language_circuit.jpg',
        fallback: 'previews/05_fresnel_language_circuit.png',
        cat: 'Functional Circuit Sim',
        title: 'Language Loop Circuit (Wernicke -> Arcuate -> Broca -> M1)',
        desc: 'Animated action-potential packets and fMRI BOLD halos streaming through the dorsal speech loop with real-time neural oscillation wave scope.'
      },
      {
        src: 'previews/06_eeg_1020_cap.jpg',
        fallback: 'previews/06_eeg_1020_cap.png',
        cat: '10-20 EEG + Caliper',
        title: '19-Electrode Smart-Textile EEG Cap & 3D Millimeter Caliper',
        desc: 'International 10-20 scalp sensor montage mapped to MNI152 coordinates alongside the interactive 3D stereotaxic millimeter distance caliper.'
      },
      {
        src: 'previews/07_3d_textured_mri_slice.jpg',
        fallback: 'previews/07_3d_textured_mri_slice.png',
        cat: '3D MRI Cutting Planes',
        title: 'Real-Time Textured 3D MNI152 MRI Surgical Cutaway',
        desc: 'Live textured MNI152 T1-MRI planes rendered directly inside the 3D cutaway brain with T1 Gray, T2 Invert, fMRI Hot, and Viridis radiology colormaps.'
      },
      {
        src: 'previews/08_cerebrovascular_mca_sim.jpg',
        fallback: 'previews/08_cerebrovascular_mca_sim.png',
        cat: 'Vascular Territory Sim',
        title: 'Cerebrovascular Arterial Territory Simulator (MCA / ACA / PCA)',
        desc: 'Educational arterial perfusion simulation highlighting cortical territories, Brodmann regions, Kloster A_tau(p) reserve percentage, and neurorehabilitation context.'
      }
    ];

    grid.innerHTML = MEDIA_SHOTS.map(function (item) {
      return '<article class="plate-card">' +
        '<div class="plate-img-wrap" style="background:#070b12;padding:4px;" data-lb-src="' + esc(item.src) + '" data-lb-title="' + esc(item.title) + '" data-lb-desc="' + esc(item.desc) + '">' +
          '<img src="' + esc(item.src) + '" onerror="if(!this.dataset.fb){this.dataset.fb=1;this.src=\'' + esc(item.fallback) + '\';}" alt="' + esc(item.title) + '" loading="lazy"/>' +
        '</div>' +
        '<div class="plate-meta">' +
          '<span class="pill-cat">' + esc(item.cat) + '</span>' +
          '<h3>' + esc(item.title) + '</h3>' +
          '<p>' + esc(item.desc) + '</p>' +
        '</div>' +
      '</article>';
    }).join('');
  }

  window.__DOROTHY_ZOE_QA = {
    answerQuestion: answerQuestion,
    focusFromQuery: focusFromQuery,
    runBrainAction: runBrainAction
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initAskZoePanel();
      initMediaGallery();
      initDesktopNavigationAndParams();
    });
  } else {
    initAskZoePanel();
    initMediaGallery();
    initDesktopNavigationAndParams();
  }
})();
