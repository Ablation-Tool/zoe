/* Dorothy Brain Observatory — Real MNI152/ICBM152/CIT168 WebGL2 3D Navigable Brain
 * + Synchronized Real MNI152 Tri-Planar T1-MRI + Verified Plates + Dorothy Library Vault
 * 100% offline-capable (works directly via file:// with zero external network calls).
 */
(() => {
  'use strict';

  const MESHES = window.DOROTHY_MESHES;
  const ATLAS = window.DOROTHY_ATLAS;
  const VAULT = window.DOROTHY_VAULT;

  // ── Helper: decode base64 binary typed arrays ─────────────────────────────
  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  // Exact right-handed MNI152 (X:L->R, Y:P->A, Z:I->S) -> Three.js (-X, Z, Y) [det = +1]
  function mniToThree(x, y, z) {
    return new THREE.Vector3(-x, z, y);
  }
  function threeToMni(v) {
    return [-v.x, v.z, v.y];
  }

  function decodeMeshBuffers(rec, mirrorX = false) {
    const vBytes = b64ToBytes(rec.v);
    const i16 = new Int16Array(vBytes.buffer);
    const scale = MESHES.scale || 100.0;
    const pos = new Float32Array(rec.nv * 3);
    for (let i = 0; i < rec.nv; i++) {
      let mx = i16[i * 3] / scale;
      const my = i16[i * 3 + 1] / scale;
      const mz = i16[i * 3 + 2] / scale;
      if (mirrorX) mx = -mx;
      // Right-handed rotation: (-mx, mz, my)
      pos[i * 3] = -mx;
      pos[i * 3 + 1] = mz;
      pos[i * 3 + 2] = my;
    }
    const fBytes = b64ToBytes(rec.f);
    let idx;
    if (rec.ft === 'u16') {
      idx = new Uint16Array(fBytes.buffer);
    } else {
      idx = new Uint32Array(fBytes.buffer);
    }
    if (mirrorX) {
      // Flip triangle winding so mirrored hemisphere keeps outward normals
      const flipped = rec.ft === 'u16' ? new Uint16Array(idx.length) : new Uint32Array(idx.length);
      for (let i = 0; i < idx.length; i += 3) {
        flipped[i] = idx[i];
        flipped[i + 1] = idx[i + 2];
        flipped[i + 2] = idx[i + 1];
      }
      idx = flipped;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.computeVertexNormals();
    return geo;
  }

  // Deterministic palette helpers
  const LOBE_NAMES = ['', 'Frontal', 'Parietal', 'Temporal', 'Occipital', 'Insula', 'Limbic'];
  const LOBE_COLORS = {
    1: [0.28, 0.56, 0.96], // Frontal - azure blue
    2: [0.16, 0.78, 0.72], // Parietal - teal
    3: [0.95, 0.65, 0.22], // Temporal - warm amber
    4: [0.88, 0.34, 0.68], // Occipital - rose magenta
    5: [0.64, 0.42, 0.96], // Insula - violet
    6: [0.24, 0.80, 0.48], // Limbic - emerald
  };
  function hslToRgb(h, s, l) {
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60) [r, g, b] = [c, x, 0];
    else if (h < 120) [r, g, b] = [x, c, 0];
    else if (h < 180) [r, g, b] = [0, c, x];
    else if (h < 240) [r, g, b] = [0, x, c];
    else if (h < 300) [r, g, b] = [x, 0, c];
    else [r, g, b] = [c, 0, x];
    return [r + m, g + m, b + m];
  }

  // ── Global App State ──────────────────────────────────────────────────────
  const state = {
    mode: 'tissue', // tissue | lobe | aal | xray | connectome | continuum | cad
    cortexOpacity: 1.0,
    explode: 0.0,
    tau: 0.62,
    autoOrbit: false,
    clipEnabled: false,
    mni: [0, -14, 6], // active crosshair (X, Y, Z mm)
    pulsesOn: true,
    pulseSpeed: 1.0,
    layers: {
      cortexL: true,
      cortexR: true,
      cerebellum: true,
      brainstem: true,
      callosum: true,
      ventricles: true,
      thalamus: true,
      limbic: true,
      cit168: true,
      vascular: true,
      cranial: true,
      tracts: true,
      pins: false,
      eegCap: false,
    },
    activeCircuit: '',
    activeVasc: '',
    mriCmap: 't1',
    measureMode: false,
    selectedKey: 'Frontal',
    activeTab: 'brain3d',
  };

  // ── 3D SCENE INITIALIZATION ───────────────────────────────────────────────
  const container = document.getElementById('viewport3d');
  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(40, 1, 1, 1800);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.localClippingEnabled = true;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  container.appendChild(renderer.domElement);

  // Subtle starfield / spatial reference grid
  const gridHelper = new THREE.PolarGridHelper(135, 12, 6, 64, 0x203554, 0x111d30);
  gridHelper.position.y = -76;
  scene.add(gridHelper);

  // Studio Neuroimaging Lighting (3-point + cool rim for crisp sulcal depth)
  const hemiLight = new THREE.HemisphereLight(0xe4f0ff, 0x2a1f34, 0.80);
  scene.add(hemiLight);
  const keyLight = new THREE.DirectionalLight(0xfff6ea, 0.96);
  keyLight.position.set(175, 220, 195);
  scene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x56beff, 0.68);
  rimLight.position.set(-195, 95, -185);
  scene.add(rimLight);
  const underLight = new THREE.DirectionalLight(0xf59e0b, 0.28);
  underLight.position.set(0, -220, 85);
  scene.add(underLight);

  // Live Clipping Planes (Sagittal X, Coronal Y, Axial Z in MNI space)
  const clipSag = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 1000);
  const clipCor = new THREE.Plane(new THREE.Vector3(0, 0, -1), 1000);
  const clipAx  = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1000);
  const activeClipPlanes = [];

  // Live 3D Textured MNI152 MRI Cutting Planes (exact millimeter registration inside the 3D brain!)
  function makeTexturedSlicePlane(axis, borderHex) {
    const b = MESHES.mriMeta.bounds_mm;
    const x0 = b.x[0], x1 = b.x[1], y0 = b.y[0], y1 = b.y[1], z0 = b.z[0], z1 = b.z[1];
    // 4 corners in Three.js space matching CanvasTexture UVs: TL(0,1), TR(1,1), BL(0,0), BR(1,0)
    let c;
    if (axis === 'ax') {
      c = [mniToThree(x0, y1, 0), mniToThree(x1, y1, 0), mniToThree(x0, y0, 0), mniToThree(x1, y0, 0)];
    } else if (axis === 'cor') {
      c = [mniToThree(x0, 0, z1), mniToThree(x1, 0, z1), mniToThree(x0, 0, z0), mniToThree(x1, 0, z0)];
    } else {
      c = [mniToThree(0, y0, z1), mniToThree(0, y1, z1), mniToThree(0, y0, z0), mniToThree(0, y1, z0)];
    }
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array([
      c[0].x, c[0].y, c[0].z,
      c[1].x, c[1].y, c[1].z,
      c[2].x, c[2].y, c[2].z,
      c[3].x, c[3].y, c[3].z,
    ]);
    const uvs = new Float32Array([0, 1, 1, 1, 0, 0, 1, 0]);
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    geo.setIndex([0, 2, 1, 1, 2, 3]);

    const cvs = document.createElement('canvas');
    cvs.width = 160; cvs.height = 160;
    const tex = new THREE.CanvasTexture(cvs);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;

    const mat = new THREE.MeshBasicMaterial({
      map: tex, transparent: true, alphaTest: 0.14, opacity: 0.98, side: THREE.DoubleSide, depthWrite: true,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.renderOrder = 5;

    const borderGeo = new THREE.BufferGeometry().setFromPoints([c[0], c[1], c[3], c[2], c[0]]);
    const borderMat = new THREE.LineBasicMaterial({ color: borderHex, transparent: true, opacity: 0.58 });
    const border = new THREE.Line(borderGeo, borderMat);

    const g = new THREE.Group();
    g.add(mesh, border);
    g.userData = { cvs, tex, mesh, border };
    g.visible = false;
    scene.add(g);
    return g;
  }
  const frameSag = makeTexturedSlicePlane('sag', 0xf5d078);
  const frameCor = makeTexturedSlicePlane('cor', 0x38bdf8);
  const frameAx  = makeTexturedSlicePlane('ax',  0x34d399);

  // Master Brain Root & Subgroups (each has explode vector!)
  const brainRoot = new THREE.Group();
  scene.add(brainRoot);

  const groups = {};
  const clickableMeshes = [];
  function makeGroup(name, explodeVec) {
    const g = new THREE.Group();
    g.userData.explode = new THREE.Vector3(...explodeVec);
    brainRoot.add(g);
    groups[name] = g;
    return g;
  }

  const gCortexL    = makeGroup('cortexL',    [ 38,  8,  0]);
  const gCortexR    = makeGroup('cortexR',    [-38,  8,  0]);
  const gCerebellum = makeGroup('cerebellum', [  0, -24, -32]);
  const gBrainstem  = makeGroup('brainstem',  [  0, -34, -8]);
  const gCallosum   = makeGroup('callosum',   [  0,  22,  0]);
  const gVentricles = makeGroup('ventricles', [  0,  14,  8]);
  const gThalamus   = makeGroup('thalamus',   [  0,   6, -4]);
  const gLimbic     = makeGroup('limbic',     [  0,  -4, 14]);
  const gCIT168     = makeGroup('cit168',     [  0,   4, 10]);
  const gVascular   = makeGroup('vascular',   [  0, -16, 16]);
  const gCranial    = makeGroup('cranial',    [  0, -28, 12]);
  const gTracts     = makeGroup('tracts',     [  0,  16, -6]);
  const gPins       = makeGroup('pins',       [  0,   0,  0]);
  const gEegCap     = makeGroup('eegCap',     [  0,  22,  0]);
  const gCircuit    = makeGroup('circuit',    [  0,   0,  0]);
  const gCaliper    = new THREE.Group();
  scene.add(gCaliper);

  // ── 1. REAL ICBM152 CORTEX HEMISPHERES (LEFT & RIGHT) ─────────────────────
  const curvBytes = b64ToBytes(MESHES.cortexLH.curv);
  const aalLBytes = b64ToBytes(MESHES.cortexLH.aalL);
  const lobeLBytes = b64ToBytes(MESHES.cortexLH.lobeL);
  const aalRBytes = b64ToBytes(MESHES.cortexLH.aalR);
  const lobeRBytes = b64ToBytes(MESHES.cortexLH.lobeR);

  const geoL = decodeMeshBuffers(MESHES.cortexLH, false);
  const geoR = decodeMeshBuffers(MESHES.cortexLH, true);

  function buildCortexColors(geo, aalArr, lobeArr, mode, tau, highlightAal = -1) {
    const nv = curvBytes.length;
    const col = new Float32Array(nv * 3);
    const pos = geo.attributes.position;
    let accessibleCount = 0;
    let vascCount = 0;
    const activeCircObj = state.activeCircuit ? (ATLAS.circuits || []).find(c => c.id === state.activeCircuit) : null;
    const circNodes = activeCircObj ? activeCircObj.nodes : null;
    const isLeftHemi = (geo === geoL);

    for (let i = 0; i < nv; i++) {
      // Enhanced S-curve sulcal/gyral curvature for lifelike sculptural depth
      const rawC = curvBytes[i] / 255.0;
      const c = rawC * rawC * (3.0 - 2.0 * rawC); // smoothstep contrast
      const ao = 0.48 + 0.56 * c;
      let r, g, b;

      if (mode === 'tissue') {
        // Organic pial cortex: luminous warm ivory-peach gyri -> deep vascular-rose sulcal valleys
        r = 0.44 + 0.52 * c;
        g = 0.27 + 0.51 * c;
        b = 0.25 + 0.47 * c;
      } else if (mode === 'lobe') {
        const lc = LOBE_COLORS[lobeArr[i]] || [0.7, 0.7, 0.7];
        r = lc[0] * (0.42 + 0.68 * c);
        g = lc[1] * (0.42 + 0.68 * c);
        b = lc[2] * (0.42 + 0.68 * c);
      } else if (mode === 'aal') {
        const aid = aalArr[i];
        const rgb = hslToRgb((aid * 47) % 360, 0.68, 0.56);
        r = rgb[0] * (0.46 + 0.62 * c);
        g = rgb[1] * (0.46 + 0.62 * c);
        b = rgb[2] * (0.46 + 0.62 * c);
      } else if (mode === 'xray') {
        r = 0.36 + 0.42 * c;
        g = 0.74 + 0.24 * c;
        b = 0.96;
      } else if (mode === 'connectome') {
        r = 0.06 + 0.16 * c;
        g = 0.12 + 0.26 * c;
        b = 0.26 + 0.38 * c;
      } else if (mode === 'continuum') {
        const vx = pos.getX(i), vy = pos.getY(i), vz = pos.getZ(i);
        const p = Math.min(1, Math.max(0,
          0.32 + 0.30 * c +
          0.34 * Math.exp(-((vz - 20) * (vz - 20) + (vy - 25) * (vy - 25)) / 1800) +
          0.26 * Math.exp(-((vz + 75) * (vz + 75) + vy * vy) / 1400) +
          0.22 * Math.exp(-((Math.abs(vx) - 48) * (Math.abs(vx) - 48) + (vz + 15) * (vz + 15)) / 900)
        ));
        if (p > tau) {
          accessibleCount++;
          const t = Math.min(1, (p - tau) / Math.max(0.05, 1.0 - tau));
          if (t < 0.5) {
            const u = t * 2;
            r = 0.05 + 0.90 * u;
            g = 0.78 + 0.05 * u;
            b = 0.98 * (1 - u) + 0.20 * u;
          } else {
            const u = (t - 0.5) * 2;
            r = 0.95 + 0.05 * u;
            g = 0.83 * (1 - u) + 0.12 * u;
            b = 0.20 + 0.38 * u;
          }
        } else {
          r = 0.14 * ao;
          g = 0.16 * ao;
          b = 0.23 * ao;
        }
      } else {
        r = 0.22; g = 0.88; b = 0.98;
      }

      // Cerebrovascular Territory Simulator overlay (exact MNI152 cortical arterial territories!)
      if (state.activeVasc) {
        const mx = -pos.getX(i), my = pos.getZ(i), mz = pos.getY(i);
        let inVasc = false;
        if (state.activeVasc === 'mcaL') {
          inVasc = isLeftHemi && mx < -18 && my > -64 && my < 50 && mz > -26 && mz < 62 && lobeArr[i] !== 4;
        } else if (state.activeVasc === 'aca') {
          inVasc = Math.abs(mx) < 22 && my > -38 && mz > -16 && (lobeArr[i] === 1 || lobeArr[i] === 2 || lobeArr[i] === 6);
        } else if (state.activeVasc === 'pca') {
          inVasc = isLeftHemi && (lobeArr[i] === 4 || (my < -34 && mz < 10 && mx > -46));
        }
        if (inVasc) {
          vascCount++;
          const vr = state.activeVasc === 'pca' ? 0.82 : 0.96;
          const vg = state.activeVasc === 'aca' ? 0.44 : (state.activeVasc === 'pca' ? 0.26 : 0.18);
          const vb = state.activeVasc === 'pca' ? 0.96 : 0.16;
          r = r * 0.22 + vr * (0.45 + 0.55 * c);
          g = g * 0.22 + vg * (0.45 + 0.55 * c);
          b = b * 0.22 + vb * (0.45 + 0.55 * c);
        }
      }

      // 3D fMRI BOLD Cortical Activation Hotspots when a Functional Neural Circuit is active
      if (circNodes) {
        const mx = -pos.getX(i), my = pos.getZ(i), mz = pos.getY(i);
        let bold = 0;
        for (let k = 0; k < circNodes.length; k++) {
          const nm = circNodes[k].mni;
          const d2 = (mx - nm[0]) * (mx - nm[0]) + (my - nm[1]) * (my - nm[1]) + (mz - nm[2]) * (mz - nm[2]);
          if (d2 < 420) bold = Math.max(bold, Math.exp(-d2 / 140));
        }
        if (bold > 0.08) {
          r = Math.min(1, r * (1 - bold * 0.6) + 1.0 * bold * 0.85);
          g = Math.min(1, g * (1 - bold * 0.6) + 0.72 * bold * 0.85);
          b = Math.min(1, b * (1 - bold * 0.6) + 0.16 * bold * 0.85);
        }
      }

      // Live AAL-116 clicked parcel highlight glow!
      if (highlightAal > 0 && aalArr[i] === highlightAal) {
        r = Math.min(1, r * 0.45 + 0.98 * 0.65);
        g = Math.min(1, g * 0.45 + 0.82 * 0.65);
        b = Math.min(1, b * 0.45 + 0.22 * 0.65);
      }
      col[i * 3] = Math.min(1, r);
      col[i * 3 + 1] = Math.min(1, g);
      col[i * 3 + 2] = Math.min(1, b);
    }
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    return { accessibleCount, vascCount, total: nv };
  }

  let selectedAalId = -1;
  const matCortexL = new THREE.MeshStandardMaterial({
    vertexColors: true, roughness: 0.38, metalness: 0.06,
    transparent: false, opacity: 1.0, depthWrite: true,
    side: THREE.FrontSide, clippingPlanes: activeClipPlanes,
  });
  const matCortexR = matCortexL.clone();

  // Custom GLSL Physically Based Subsurface Scattering (SSS) + Dual-Lobe Wet-Pia Cortical Shader!
  const matTissueSSS = new THREE.ShaderMaterial({
    uniforms: {
      uOpacity: { value: 1.0 },
    },
    vertexShader: `
      #include <common>
      #include <clipping_planes_pars_vertex>
      varying vec3 vNormalView;
      varying vec3 vViewPos;
      varying vec3 vColor;
      void main() {
        vColor = color;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vViewPos = -mvPosition.xyz;
        vNormalView = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * mvPosition;
        #include <clipping_planes_vertex>
      }
    `,
    fragmentShader: `
      #include <common>
      #include <clipping_planes_pars_fragment>
      uniform float uOpacity;
      varying vec3 vNormalView;
      varying vec3 vViewPos;
      varying vec3 vColor;
      void main() {
        #include <clipping_planes_fragment>
        vec3 N = normalize(vNormalView);
        if (!gl_FrontFacing) N = -N;
        vec3 V = normalize(vViewPos);

        // Studio neurosurgical 3-point lighting (key upper-right, cool cyan rim, warm bounce)
        vec3 L1 = normalize(vec3(0.56, 0.72, 0.64));
        vec3 L2 = normalize(vec3(-0.76, 0.32, -0.56));
        vec3 L3 = normalize(vec3(0.0, -0.84, 0.54));

        // Wrapped diffuse + warm vascularized pial subsurface scatter bell along terminator
        float ndl1 = dot(N, L1);
        float wrap1 = max(0.0, (ndl1 + 0.36) / 1.36);
        float sssBell = smoothstep(-0.35, 0.42, ndl1) * (1.0 - smoothstep(0.16, 0.86, ndl1));
        float ndl2 = max(0.0, dot(N, L2));
        float ndl3 = max(0.0, dot(N, L3));

        // Dual-lobe wet-pia specular (crisp CSF highlight + soft broad pial sheen)
        vec3 H1 = normalize(L1 + V);
        float ndh1 = max(0.0, dot(N, H1));
        float specSharp = pow(ndh1, 60.0) * 0.26;
        float specBroad = pow(ndh1, 14.0) * 0.09;

        // Grazing translucent subsurface rim glow
        float rim = pow(1.0 - max(0.0, dot(N, V)), 2.9);
        vec3 sssTint = vec3(0.96, 0.32, 0.20);

        vec3 hemi = mix(vec3(0.16, 0.12, 0.18), vec3(0.32, 0.34, 0.38), N.y * 0.5 + 0.5);
        vec3 col = vColor * (hemi + vec3(0.95, 0.91, 0.87) * wrap1 * 0.88 + vec3(0.36, 0.70, 0.96) * ndl2 * 0.34 + vec3(0.95, 0.68, 0.38) * ndl3 * 0.16);
        col += sssTint * (sssBell * 0.17 + rim * 0.20) * (0.45 + 0.55 * vColor.r);
        col += vec3(0.42, 0.78, 1.0) * rim * ndl2 * 0.20;
        col += vec3(1.0, 0.97, 0.94) * (specSharp + specBroad);

        // Smooth ACES-style highlight rolloff
        col = col / (col + vec3(0.84)) * 1.64;
        gl_FragColor = vec4(col, uOpacity);
      }
    `,
    vertexColors: true,
    transparent: false,
    depthWrite: true,
    side: THREE.FrontSide,
    clipping: true,
    clippingPlanes: activeClipPlanes,
  });

  // Custom GLSL Holographic Fresnel Rim Glass Shader (with full Three.js clipping plane support!)
  function makeFresnelMat(rimHex, coreHex, opVal, rimPow) {
    return new THREE.ShaderMaterial({
      uniforms: {
        uRimColor:  { value: new THREE.Color(rimHex) },
        uCoreColor: { value: new THREE.Color(coreHex) },
        uOpacity:   { value: opVal },
        uRimPower:  { value: rimPow },
      },
      vertexShader: `
        #include <common>
        #include <clipping_planes_pars_vertex>
        varying vec3 vNormalView;
        varying vec3 vViewPos;
        varying vec3 vColor;
        void main() {
          vColor = color;
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          vViewPos = -mvPosition.xyz;
          vNormalView = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * mvPosition;
          #include <clipping_planes_vertex>
        }
      `,
      fragmentShader: `
        #include <common>
        #include <clipping_planes_pars_fragment>
        uniform vec3 uRimColor;
        uniform vec3 uCoreColor;
        uniform float uOpacity;
        uniform float uRimPower;
        varying vec3 vNormalView;
        varying vec3 vViewPos;
        varying vec3 vColor;
        void main() {
          #include <clipping_planes_fragment>
          vec3 N = normalize(vNormalView);
          vec3 V = normalize(vViewPos);
          float fresnel = pow(1.0 - abs(dot(N, V)), uRimPower);
          float lum = dot(vColor, vec3(0.333));
          vec3 col = mix(uCoreColor * (0.55 + 0.65 * lum), uRimColor, clamp(fresnel * 1.25, 0.0, 1.0));
          float alpha = clamp(uOpacity * (0.24 + 1.55 * fresnel), 0.03, 0.86);
          gl_FragColor = vec4(col, alpha);
        }
      `,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      clipping: true,
      clippingPlanes: activeClipPlanes,
    });
  }
  const matFresnelXray = makeFresnelMat(0x56d8ff, 0x164e63, 0.34, 2.1);
  const matFresnelConn = makeFresnelMat(0x6366f1, 0x0b1124, 0.30, 2.4);

  buildCortexColors(geoL, aalLBytes, lobeLBytes, 'tissue', state.tau);
  buildCortexColors(geoR, aalRBytes, lobeRBytes, 'tissue', state.tau);

  const meshCortexL = new THREE.Mesh(geoL, matCortexL);
  meshCortexL.userData = { kind: 'cortex', hemi: 'Left', aalArr: aalLBytes, lobeArr: lobeLBytes };
  gCortexL.add(meshCortexL);
  clickableMeshes.push(meshCortexL);

  const meshCortexR = new THREE.Mesh(geoR, matCortexR);
  meshCortexR.userData = { kind: 'cortex', hemi: 'Right', aalArr: aalRBytes, lobeArr: lobeRBytes };
  gCortexR.add(meshCortexR);
  clickableMeshes.push(meshCortexR);

  // ── 2. REAL AAL-116 CEREBELLUM, THALAMUS & LIMBIC CORE ────────────────────
  function makeIndexedAtlasMesh(rec, colorFn, kind, labelMap, matOpts = {}) {
    const geo = decodeMeshBuffers(rec, false);
    const ids = b64ToBytes(rec.id);
    const col = new Float32Array(rec.nv * 3);
    const pos = geo.attributes.position;
    for (let i = 0; i < rec.nv; i++) {
      const rgb = colorFn(ids[i], pos.getX(i), pos.getY(i), pos.getZ(i));
      col[i * 3] = rgb[0]; col[i * 3 + 1] = rgb[1]; col[i * 3 + 2] = rgb[2];
    }
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    const mat = new THREE.MeshStandardMaterial(Object.assign({
      vertexColors: true, roughness: 0.45, metalness: 0.08,
      side: THREE.DoubleSide, clippingPlanes: activeClipPlanes,
    }, matOpts));
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { kind, idArr: ids, labelMap };
    clickableMeshes.push(mesh);
    return mesh;
  }

  // Real Cerebellum with subtle horizontal cerebellar folia striations!
  const meshCerebellum = makeIndexedAtlasMesh(
    MESHES.cerebellum,
    (id, x, y, z) => {
      const folia = 0.84 + 0.16 * Math.sin(y * 1.45 + z * 0.35);
      const isVermis = id >= 109;
      return isVermis ? [0.82 * folia, 0.56 * folia, 0.48 * folia] : [0.76 * folia, 0.58 * folia, 0.52 * folia];
    },
    'cerebellum', MESHES.aalNames, { roughness: 0.55 }
  );
  gCerebellum.add(meshCerebellum);

  // Real AAL Thalamus (warm amber-gold)
  const meshThalamus = makeIndexedAtlasMesh(
    MESHES.thalamus,
    () => [0.95, 0.72, 0.24],
    'thalamus', MESHES.aalNames, { roughness: 0.35, metalness: 0.12 }
  );
  gThalamus.add(meshThalamus);

  // Real AAL Hippocampus (emerald) + Amygdala (coral-crimson)
  const meshLimbicCore = makeIndexedAtlasMesh(
    MESHES.limbicCore,
    (id) => (id === 41 || id === 42) ? [0.95, 0.28, 0.44] : [0.18, 0.84, 0.58],
    'limbic', MESHES.aalNames, { roughness: 0.34, metalness: 0.12 }
  );
  gLimbic.add(meshLimbicCore);

  // Real Pauli CIT168 32 Human Subcortical Nuclei (Putamen, Caudate, NAcc, GPe, GPi, STN, SNc, SNr, RN, VTA, HTH, MN, HN)
  const CIT_PALETTE = {
    1: [0.32, 0.58, 0.96], 2: [0.32, 0.58, 0.96],   // Putamen - cobalt
    3: [0.16, 0.82, 0.92], 4: [0.16, 0.82, 0.92],   // Caudate - cyan
    5: [0.98, 0.82, 0.20], 6: [0.98, 0.82, 0.20],   // Nucleus Accumbens - gold
    7: [0.85, 0.42, 0.95], 8: [0.85, 0.42, 0.95],   // Extended Amygdala - orchid
    9: [0.55, 0.46, 0.98], 10: [0.55, 0.46, 0.98],  // GPe - indigo
    11: [0.74, 0.34, 0.94], 12: [0.74, 0.34, 0.94], // GPi - purple
    13: [0.98, 0.52, 0.16], 14: [0.98, 0.52, 0.16], // SNc (Dopamine) - fiery orange
    15: [0.94, 0.22, 0.28], 16: [0.94, 0.22, 0.28], // Red Nucleus - ruby
    17: [0.86, 0.38, 0.18], 18: [0.86, 0.38, 0.18], // SNr
    19: [0.96, 0.64, 0.30], 20: [0.96, 0.64, 0.30], // PBP
    21: [0.98, 0.88, 0.34], 22: [0.98, 0.88, 0.34], // VTA
    23: [0.46, 0.66, 0.92], 24: [0.46, 0.66, 0.92], // Ventral Pallidum
    25: [0.92, 0.92, 0.96], 26: [0.92, 0.92, 0.96], // Habenula
    27: [0.96, 0.36, 0.66], 28: [0.96, 0.36, 0.66], // Hypothalamus
    29: [0.98, 0.50, 0.78], 30: [0.98, 0.50, 0.78], // Mammillary Bodies
    31: [0.30, 0.96, 0.48], 32: [0.30, 0.96, 0.48], // STN - bright green
  };
  const meshCIT168 = makeIndexedAtlasMesh(
    MESHES.cit168,
    (id) => CIT_PALETTE[id] || [0.7, 0.7, 0.9],
    'cit168', MESHES.cit168Names, { roughness: 0.30, metalness: 0.16 }
  );
  gCIT168.add(meshCIT168);

  // ── 3. ANATOMICALLY MNI152-REGISTERED DEEP ASSEMBLIES ─────────────────────
  function addTube(parent, ptsMni, radius, colorHex, opts = {}, userData = {}) {
    const curve = new THREE.CatmullRomCurve3(ptsMni.map(p => mniToThree(p[0], p[1], p[2])));
    const geo = new THREE.TubeGeometry(curve, opts.segs || 36, radius, opts.radSegs || 12, false);
    const mat = new THREE.MeshStandardMaterial(Object.assign({
      color: colorHex, roughness: 0.35, metalness: 0.1,
      clippingPlanes: activeClipPlanes,
    }, opts.mat || {}));
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = userData;
    parent.add(mesh);
    if (userData.kind) clickableMeshes.push(mesh);
    return { mesh, curve };
  }

  // 3A. BRAINSTEM (Midbrain, Pons bulge, Medulla Oblongata in exact MNI coords)
  {
    const bsMat = new THREE.MeshStandardMaterial({
      color: 0xe3cbb9, roughness: 0.48, metalness: 0.05, side: THREE.DoubleSide, clippingPlanes: activeClipPlanes,
    });
    // Exact MNI centerline: Midbrain (0,-20,-8) -> Pons (0,-24,-28) -> Medulla (0,-32,-48) -> Cord (0,-37,-68)
    const bsPts = [
      [0, -19, -6], [0, -22, -16], [0, -24, -28], [0, -30, -42], [0, -35, -56], [0, -38, -68]
    ];
    const bsRx = [12.5, 11.5, 16.5, 10.2, 7.6, 6.2]; // mediolateral half-width (X)
    const bsRz = [ 9.5,  9.5, 14.0,  9.2, 6.8, 5.8]; // anteroposterior half-depth (Z_three = Y_mni)
    const curve = new THREE.CatmullRomCurve3(bsPts.map(p => mniToThree(p[0], p[1], p[2])));
    const segs = 40, radSegs = 24;
    const verts = [], indices = [];
    for (let i = 0; i <= segs; i++) {
      const t = i / segs;
      const p = curve.getPointAt(t);
      const fi = t * (bsRx.length - 1);
      const i0 = Math.floor(fi), i1 = Math.min(bsRx.length - 1, i0 + 1);
      const frac = fi - i0;
      const rx = bsRx[i0] * (1 - frac) + bsRx[i1] * frac;
      const rz = bsRz[i0] * (1 - frac) + bsRz[i1] * frac;
      const ponsAnterior = Math.exp(-Math.pow((t - 0.36) / 0.14, 2)) * 5.2;
      for (let j = 0; j <= radSegs; j++) {
        const ang = (j / radSegs) * Math.PI * 2;
        const cx = Math.cos(ang), cz = Math.sin(ang);
        // Clean horizontal ring around brainstem axis (no Frenet twist!)
        const px = p.x + cx * rx;
        const py = p.y;
        const pz = p.z + cz * rz + (cz > 0 ? ponsAnterior * cz : 0);
        verts.push(px, py, pz);
      }
    }
    for (let i = 0; i < segs; i++) {
      for (let j = 0; j < radSegs; j++) {
        const a = i * (radSegs + 1) + j;
        const b = (i + 1) * (radSegs + 1) + j;
        indices.push(a, a + 1, b, b, a + 1, b + 1);
      }
    }
    const bsGeo = new THREE.BufferGeometry();
    bsGeo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    bsGeo.setIndex(indices);
    bsGeo.computeVertexNormals();
    const bsMesh = new THREE.Mesh(bsGeo, bsMat);
    bsMesh.userData = { kind: 'structure', key: 'Brainstem', label: 'Brainstem (Midbrain, Pons & Medulla)' };
    gBrainstem.add(bsMesh);
    clickableMeshes.push(bsMesh);

    // Superior & Inferior Colliculi (Tectum on dorsal midbrain)
    [[-4.5, -31, -6], [4.5, -31, -6], [-4.2, -32, -12], [4.2, -32, -12]].forEach((p, idx) => {
      const m = new THREE.Mesh(new THREE.SphereGeometry(3.2, 16, 12), bsMat);
      m.position.copy(mniToThree(p[0], p[1], p[2]));
      m.userData = { kind: 'structure', key: 'Brainstem', label: idx < 2 ? 'Superior Colliculus (Midbrain Tectum)' : 'Inferior Colliculus (Midbrain Tectum)' };
      gBrainstem.add(m);
      clickableMeshes.push(m);
    });
    // Bilateral Cerebellar Peduncles (Middle, Superior & Inferior) uniting Brainstem -> Cerebellum!
    for (const s of [-1, 1]) {
      const sn = s < 0 ? 'Left ' : 'Right ';
      addTube(gBrainstem, [[s * 12, -25, -28], [s * 19, -36, -30], [s * 24, -46, -32]], 4.2, 0xe0c4b2, { segs: 16, radSegs: 10 },
        { kind: 'structure', key: 'Brainstem', label: sn + 'Middle Cerebellar Peduncle (Brachium Pontis)' });
      addTube(gBrainstem, [[s * 6, -28, -16], [s * 11, -38, -22], [s * 15, -48, -28]], 2.2, 0xdcc0ae, { segs: 14, radSegs: 8 },
        { kind: 'structure', key: 'Brainstem', label: sn + 'Superior Cerebellar Peduncle' });
    }
    // Pituitary Gland + Infundibular Stalk & Pineal Gland (iconic sagittal landmarks!)
    const glandMat = new THREE.MeshStandardMaterial({ color: 0xf472b6, roughness: 0.34, metalness: 0.1, emissive: 0x831843, emissiveIntensity: 0.25, clippingPlanes: activeClipPlanes });
    const pit = new THREE.Mesh(new THREE.SphereGeometry(4.4, 20, 16), glandMat);
    pit.position.copy(mniToThree(0, 3, -27));
    pit.scale.set(1.25, 0.85, 1.0);
    pit.userData = { kind: 'structure', key: 'Thalamus', label: 'Pituitary Gland (Hypophysis)' };
    gThalamus.add(pit); clickableMeshes.push(pit);
    addTube(gThalamus, [[0, -1, -13], [0, 1.5, -20], [0, 3, -26]], 1.15, 0xf9a8d4, { segs: 10, radSegs: 8 },
      { kind: 'structure', key: 'Thalamus', label: 'Infundibulum (Pituitary Stalk)' });
    const pin = new THREE.Mesh(new THREE.SphereGeometry(3.1, 16, 12), new THREE.MeshStandardMaterial({ color: 0xfbbf24, roughness: 0.3, emissive: 0x78350f, emissiveIntensity: 0.35, clippingPlanes: activeClipPlanes }));
    pin.position.copy(mniToThree(0, -28, 3));
    pin.scale.set(0.9, 0.9, 1.35);
    pin.userData = { kind: 'structure', key: 'Limbic', label: 'Pineal Gland (Epiphysis — Melatonin / Circadian)' };
    gLimbic.add(pin); clickableMeshes.push(pin);
  }

  // 3B. SCULPTED SINGLE-MESH ORGANIC CORPUS CALLOSUM (Rostrum, Genu, Body, Splenium)
  {
    const ccArch = [
      [0, 13, 3.5], [0, 24, 9], [0, 26, 19], [0, 14, 27],
      [0, -4, 29], [0, -24, 25], [0, -37, 17], [0, -39, 11]
    ];
    const ccThick = [2.6, 5.2, 6.2, 4.4, 3.8, 4.0, 5.8, 4.6];
    const curve = new THREE.CatmullRomCurve3(ccArch.map(p => mniToThree(p[0], p[1], p[2])));
    const segs = 44, uSegs = 22;
    const verts = [], indices = [];
    const halfSpan = 13.5; // seamless medial-to-lateral callosal bridge
    for (let i = 0; i <= segs; i++) {
      const t = i / segs;
      const p = curve.getPointAt(t);
      const tang = curve.getTangentAt(t);
      // Normal in sagittal Y-Z plane (perpendicular to tangent and X-axis)
      const nSag = new THREE.Vector3(0, tang.z, -tang.y).normalize();
      const fi = t * (ccThick.length - 1);
      const i0 = Math.floor(fi), i1 = Math.min(ccThick.length - 1, i0 + 1);
      const thick = ccThick[i0] * (1 - (fi - i0)) + ccThick[i1] * (fi - i0);
      for (let j = 0; j <= uSegs; j++) {
        const ang = (j / uSegs) * Math.PI * 2;
        // Superellipse cross-section: wide mediolaterally (X), smooth organic thickness along nSag
        const cx = Math.cos(ang), cy = Math.sin(ang);
        const sgnX = Math.sign(cx), sgnY = Math.sign(cy);
        const sx = sgnX * Math.pow(Math.abs(cx), 0.55) * halfSpan;
        const sy = sgnY * Math.pow(Math.abs(cy), 0.78) * thick;
        const archLift = (sx * sx) / (halfSpan * halfSpan) * 2.2;
        verts.push(p.x + sx, p.y + nSag.y * sy + archLift, p.z + nSag.z * sy);
      }
    }
    for (let i = 0; i < segs; i++) {
      for (let j = 0; j < uSegs; j++) {
        const a = i * (uSegs + 1) + j;
        const b = (i + 1) * (uSegs + 1) + j;
        indices.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
    const ccGeo = new THREE.BufferGeometry();
    ccGeo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    ccGeo.setIndex(indices);
    ccGeo.computeVertexNormals();
    const ccMesh = new THREE.Mesh(ccGeo, new THREE.MeshStandardMaterial({
      color: 0xf6efe6, roughness: 0.36, metalness: 0.05, side: THREE.DoubleSide, clippingPlanes: activeClipPlanes,
    }));
    ccMesh.userData = { kind: 'structure', key: 'CorpusCallosum', label: 'Corpus Callosum (Rostrum, Genu, Body & Splenium)' };
    gCallosum.add(ccMesh);
    clickableMeshes.push(ccMesh);
  }

  // 3C. SCULPTED TAPERED VENTRICULAR SYSTEM (Sapphire translucent CSF cavities)
  {
    const vMat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8, roughness: 0.14, metalness: 0.22, transparent: true, opacity: 0.72,
      emissive: 0x0c4a6e, emissiveIntensity: 0.42, side: THREE.DoubleSide, clippingPlanes: activeClipPlanes,
    });
    function addTaperedTube(parent, ptsMni, radii, userData) {
      const curve = new THREE.CatmullRomCurve3(ptsMni.map(p => mniToThree(p[0], p[1], p[2])));
      const segs = 34, radSegs = 14;
      const frames = curve.computeFrenetFrames(segs, false);
      const verts = [], indices = [];
      for (let i = 0; i <= segs; i++) {
        const t = i / segs;
        const p = curve.getPointAt(t);
        const fi = t * (radii.length - 1);
        const i0 = Math.floor(fi), i1 = Math.min(radii.length - 1, i0 + 1);
        const r = radii[i0] * (1 - (fi - i0)) + radii[i1] * (fi - i0);
        for (let j = 0; j <= radSegs; j++) {
          const ang = (j / radSegs) * Math.PI * 2;
          const nrm = frames.normals[i].clone().multiplyScalar(Math.cos(ang)).add(frames.binormals[i].clone().multiplyScalar(Math.sin(ang)));
          verts.push(p.x + nrm.x * r, p.y + nrm.y * r, p.z + nrm.z * r);
        }
      }
      for (let i = 0; i < segs; i++) {
        for (let j = 0; j < radSegs; j++) {
          const a = i * (radSegs + 1) + j, b = (i + 1) * (radSegs + 1) + j;
          indices.push(a, b, a + 1, b, b + 1, a + 1);
        }
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
      g.setIndex(indices);
      g.computeVertexNormals();
      const m = new THREE.Mesh(g, vMat);
      m.userData = userData;
      parent.add(m);
      clickableMeshes.push(m);
    }
    for (const side of [-1, 1]) {
      addTaperedTube(gVentricles,
        [[side * 10, 26, 9], [side * 7, 13, 16], [side * 9, -6, 20], [side * 16, -28, 16], [side * 22, -48, 10], [side * 19, -66, 6]],
        [1.4, 4.4, 4.2, 5.0, 3.2, 0.9],
        { kind: 'structure', key: 'Ventricles', label: (side < 0 ? 'Left' : 'Right') + ' Lateral Ventricle (CSF)' });
      addTaperedTube(gVentricles,
        [[side * 17, -30, 14], [side * 26, -27, -2], [side * 28, -15, -14], [side * 24, -5, -18]],
        [3.4, 2.8, 2.1, 0.8],
        { kind: 'structure', key: 'Ventricles', label: (side < 0 ? 'Left' : 'Right') + ' Lateral Ventricle — Temporal Horn' });
      addTaperedTube(gVentricles, [[side * 7, 4, 13], [0, -2, 6]], [1.6, 1.5],
        { kind: 'structure', key: 'Ventricles', label: 'Interventricular Foramen of Monro' });
    }
    addTaperedTube(gVentricles, [[0, 3, 4], [0, -10, 4], [0, -20, 2]], [2.2, 3.5, 1.8],
      { kind: 'structure', key: 'Ventricles', label: 'Third Ventricle (Midline Diencephalon)' });
    addTaperedTube(gVentricles, [[0, -20, 2], [0, -28, -12], [0, -34, -26]], [1.3, 1.1, 1.4],
      { kind: 'structure', key: 'Ventricles', label: 'Cerebral Aqueduct of Sylvius' });
    const v4 = new THREE.Mesh(new THREE.OctahedronGeometry(6.0, 2), vMat);
    v4.position.copy(mniToThree(0, -37, -34));
    v4.scale.set(1.15, 1.35, 0.72);
    v4.userData = { kind: 'structure', key: 'Ventricles', label: 'Fourth Ventricle (Pons / Cerebellum)' };
    gVentricles.add(v4);
    clickableMeshes.push(v4);
  }

  // 3D. FORNIX ARCHES (part of Limbic group!)
  {
    const fxMat = { color: 0x34d399, roughness: 0.35, emissive: 0x064e3b, emissiveIntensity: 0.2 };
    for (const side of [-1, 1]) {
      addTube(gLimbic, [
        [side * 26, -24, -12], [side * 22, -32, 0], [side * 10, -22, 14],
        [side * 3, -6, 16], [side * 3, 2, 4], [side * 2.5, -8, -12]
      ], 1.7, 0x34d399, { segs: 32, mat: fxMat },
        { kind: 'structure', key: 'Limbic', label: (side < 0 ? 'Left' : 'Right') + ' Fornix (Hippocampus → Mammillary Body)' });
    }
  }

  // 3E. CIRCLE OF WILLIS & MAJOR CEREBRAL ARTERIES
  const arteryMeshes = [];
  {
    const artMat = { color: 0xef4444, roughness: 0.25, metalness: 0.15, emissive: 0x7f1d1d, emissiveIntensity: 0.45 };
    const addArt = (pts, r, lbl) => {
      const { mesh } = addTube(gVascular, pts, r, 0xef4444, { segs: 24, radSegs: 10, mat: artMat },
        { kind: 'structure', key: 'Vascular', label: lbl });
      arteryMeshes.push(mesh);
    };
    // Basilar & Vertebrals
    addArt([[0, -22, -16], [0, -23, -24], [0, -25, -35]], 1.9, 'Basilar Artery');
    for (const s of [-1, 1]) {
      const sn = s < 0 ? 'Left' : 'Right';
      addArt([[s * 1.5, -25, -35], [s * 8, -32, -48], [s * 10, -36, -64]], 1.4, sn + ' Vertebral Artery');
      // Internal Carotid Artery (ICA)
      addArt([[s * 12, 0, -34], [s * 11, 2, -24], [s * 10, 4, -15]], 1.8, sn + ' Internal Carotid Artery (ICA)');
      // Anterior Cerebral Artery (ACA -> Pericallosal arch)
      addArt([[s * 10, 4, -15], [s * 4, 14, -13], [s * 3, 30, 4], [s * 3, 24, 24], [s * 3, -4, 34], [s * 3, -34, 32]], 1.25, sn + ' Anterior Cerebral Artery (ACA)');
      // Middle Cerebral Artery (MCA M1 -> Sylvian M2/M3 branches tucked cleanly inside Sylvian fissure)
      addArt([[s * 10, 4, -15], [s * 24, 4, -12], [s * 35, 5, -4], [s * 40, -4, 8], [s * 42, -20, 18]], 1.4, sn + ' Middle Cerebral Artery (MCA)');
      addArt([[s * 35, 5, -4], [s * 36, 14, 10], [s * 34, 20, 20]], 0.95, sn + ' MCA Superior Division');
      // Posterior Communicating (PCom) & Posterior Cerebral Artery (PCA)
      addArt([[s * 10, 4, -15], [s * 6, -9, -15.5], [s * 4, -20, -16]], 0.9, sn + ' Posterior Communicating Artery (PCom)');
      addArt([[0, -22, -16], [s * 8, -24, -16], [s * 16, -34, -12], [s * 14, -56, -4], [s * 10, -82, 2]], 1.25, sn + ' Posterior Cerebral Artery (PCA)');
      // SCA & PICA cerebellar feeders
      addArt([[0, -22, -18], [s * 14, -32, -20], [s * 26, -54, -22]], 0.9, sn + ' Superior Cerebellar Artery (SCA)');
      addArt([[s * 8, -32, -46], [s * 16, -44, -42], [s * 24, -60, -38]], 0.9, sn + ' PICA (Cerebellar Artery)');
    }
    // Anterior Communicating Artery (ACom)
    addArt([[-4, 14, -13], [4, 14, -13]], 0.95, 'Anterior Communicating Artery (ACom)');
  }

  // 3F. ALL 12 BILATERAL CRANIAL NERVES (Exact verified origins — CN IV dorsal midbrain!)
  {
    const cnMat = { color: 0xfde047, roughness: 0.32, emissive: 0x713f12, emissiveIntensity: 0.35 };
    for (const s of [-1, 1]) {
      const sn = s < 0 ? 'Left ' : 'Right ';
      const addCN = (pts, r, idx) => {
        const cn = ATLAS.cranialNerves[idx];
        addTube(gCranial, pts, r, 0xfde047, { segs: 16, radSegs: 8, mat: cnMat },
          { kind: 'cranial', cnIndex: idx, key: 'CranialNerves', label: `${sn}${cn.id} — ${cn.name} Nerve` });
      };
      // CN I Olfactory bulb & tract
      addCN([[s * 10, 50, -19], [s * 9, 32, -19], [s * 8, 16, -17]], 1.4, 0);
      // CN II Optic nerve -> Chiasm -> Optic tract -> LGN
      addCN([[s * 14, 24, -20], [s * 4, 8, -18], [0, 4, -17.5], [s * -10, -8, -14], [s * -20, -22, -6]], 1.65, 1);
      // CN III Oculomotor (ventral midbrain)
      addCN([[s * 3.5, -18, -16], [s * 8, -6, -19], [s * 12, 8, -22]], 1.1, 2);
      // CN IV Trochlear (SOLE DORSAL midbrain exit wrapping anteriorly around cerebral peduncle!)
      addCN([[s * 2.5, -32, -15], [s * 11, -26, -17], [s * 12, -12, -20], [s * 13, 6, -23]], 0.85, 3);
      // CN V Trigeminal (thick root from lateral pons)
      addCN([[s * 13, -24, -28], [s * 22, -14, -30], [s * 28, -2, -32]], 1.85, 4);
      // CN VI Abducens (medial pontomedullary junction)
      addCN([[s * 4, -24, -38], [s * 8, -12, -36], [s * 12, 2, -28]], 0.9, 5);
      // CN VII Facial (CPA)
      addCN([[s * 12, -28, -38], [s * 24, -26, -40], [s * 32, -24, -42]], 1.05, 6);
      // CN VIII Vestibulocochlear (lateral CPA)
      addCN([[s * 15, -30, -39], [s * 26, -30, -41], [s * 34, -29, -43]], 1.15, 7);
      // CN IX Glossopharyngeal
      addCN([[s * 9.5, -33, -44], [s * 22, -34, -48]], 0.9, 8);
      // CN X Vagus
      addCN([[s * 9.5, -34, -48], [s * 20, -36, -54], [s * 22, -36, -64]], 1.1, 9);
      // CN XI Accessory (spinal root ascending)
      addCN([[s * 8, -38, -66], [s * 11, -36, -54], [s * 20, -38, -52]], 0.95, 10);
      // CN XII Hypoglossal (ventral preolivary medulla)
      addCN([[s * 4.5, -30, -50], [s * 14, -24, -56]], 1.0, 11);
    }
  }

  // 3G. 3D DTI WHITE-MATTER TRACTOGRAPHY BUNDLES + ANIMATED NEURAL IMPULSES
  const pulseCurves = [];
  {
    const addTract = (pts, r, hex, tractIdx, name) => {
      const { curve } = addTube(gTracts, pts, r, hex, {
        segs: 34, radSegs: 8,
        mat: { roughness: 0.28, metalness: 0.1, emissive: hex, emissiveIntensity: 0.32, transparent: true, opacity: 0.85 },
      }, { kind: 'tract', tractIdx, key: 'WhiteMatter', label: name });
      pulseCurves.push({ curve, color: hex });
    };

    // Corpus Callosum radiations (Red = Left-Right commissural, tucked cleanly inside subcortical white matter)
    for (const [yOff, zArch, zTip, xSpan] of [[18, 19, 20, 21], [5, 27, 34, 27], [-10, 28, 38, 28], [-25, 22, 29, 27], [-37, 15, 11, 24]]) {
      addTract([[-xSpan, yOff + 1, zTip], [-13, yOff, zArch + 2], [0, yOff, zArch], [13, yOff, zArch + 2], [xSpan, yOff + 1, zTip]], 1.0, 0xef4444, 0, 'Corpus Callosum Forceps / Radiations (L–R)');
    }
    for (const s of [-1, 1]) {
      const sn = s < 0 ? 'Left ' : 'Right ';
      // Corticospinal Tract (Blue = Superior-Inferior projection, terminating beneath M1 ribbon)
      addTract([[s * 24, -18, 45], [s * 21, -16, 27], [s * 16, -14, 6], [s * 10, -20, -16], [s * 6, -26, -34], [s * 3, -34, -54], [s * -3, -37, -65]], 1.25, 0x3b82f6, 1, sn + 'Corticospinal (Pyramidal) Tract (S–I)');
      addTract([[s * 17, -19, 49], [s * 19, -16, 29], [s * 14, -15, 6], [s * 8, -22, -20], [s * 4, -33, -50]], 0.92, 0x60a5fa, 9, sn + 'Corona Radiata / Internal Capsule (S–I)');
      // Arcuate & Superior Longitudinal Fasciculus (Green = A-P association, deep to opercula)
      addTract([[s * 31, 14, 15], [s * 32, -2, 24], [s * 32, -25, 24], [s * 36, -36, 11], [s * 38, -28, -4]], 1.2, 0x22c55e, 2, sn + 'Arcuate / Superior Longitudinal Fasciculus (A–P)');
      // Inferior Longitudinal & Fronto-Occipital Fasciculus (Green)
      addTract([[s * 18, -76, 4], [s * 32, -52, -8], [s * 38, -22, -14], [s * 34, 4, -18]], 1.05, 0x10b981, 3, sn + 'Inferior Longitudinal Fasciculus (A–P)');
      addTract([[s * 16, -74, 8], [s * 28, -38, 0], [s * 28, -2, -4], [s * 22, 34, 6]], 0.95, 0x14b8a6, 3, sn + 'Inferior Fronto-Occipital Fasciculus (A–P)');
      // Uncinate Fasciculus (Hooked limbic-orbitofrontal)
      addTract([[s * 28, 6, -22], [s * 26, 15, -13], [s * 21, 30, -12]], 1.0, 0x34d399, 4, sn + 'Uncinate Fasciculus');
      // Cingulum Bundle (Limbic dorsal arch)
      addTract([[s * 8, 30, 8], [s * 8, 22, 30], [s * 8, -10, 35], [s * 10, -42, 26], [s * 16, -36, 0], [s * 22, -18, -18]], 1.05, 0x4ade80, 5, sn + 'Cingulum Bundle (Papez Circuit)');
      // Optic Radiation / Meyer's Loop (Violet)
      addTract([[s * 21, -24, -4], [s * 34, -14, -12], [s * 32, -44, -6], [s * 18, -70, 0], [s * 10, -80, 4]], 1.05, 0xa855f7, 7, sn + 'Optic Radiation (Meyer\'s Loop → V1)');
    }
  }

  // Animated Action-Potential Pulse Spheres along DTI Tracts
  const pulseAgents = [];
  const pulseGeo = new THREE.SphereGeometry(1.75, 10, 8);
  pulseCurves.forEach((pc, i) => {
    for (let k = 0; k < 2; k++) {
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const glow = new THREE.Mesh(pulseGeo, mat);
      glow.material.color.setHex(pc.color).lerp(new THREE.Color(0xffffff), 0.55);
      gTracts.add(glow);
      pulseAgents.push({
        mesh: glow,
        curve: pc.curve,
        t: (i * 0.13 + k * 0.5) % 1.0,
        speed: 0.16 + (i % 5) * 0.035,
      });
    }
  });

  // 3H. CLICKABLE 3D BRODMANN STEREOTAXIC LANDMARK PINS
  const pinMatDefault = new THREE.MeshStandardMaterial({ color: 0xf5d078, emissive: 0xb45309, emissiveIntensity: 0.55, roughness: 0.25 });
  const pinGeo = new THREE.SphereGeometry(2.6, 14, 12);
  ATLAS.brodmann.forEach((ba, idx) => {
    const m = new THREE.Mesh(pinGeo, pinMatDefault.clone());
    m.position.copy(mniToThree(ba.mni[0], ba.mni[1], ba.mni[2]));
    m.userData = { kind: 'brodmann', baIndex: idx, key: ba.lobe, label: `BA ${ba.ba} — ${ba.region}` };
    gPins.add(m);
    clickableMeshes.push(m);
  });
  gPins.visible = state.layers.pins;

  // 3I. INTERNATIONAL 10-20 EEG & WEARABLE SMART-TEXTILE CAP OVERLAY
  const eegMeshes = [];
  if (ATLAS.eeg1020 && ATLAS.eeg1020.length) {
    const eegPts = {};
    const discGeo = new THREE.CylinderGeometry(3.4, 3.8, 1.8, 20);
    const ringGeo = new THREE.TorusGeometry(4.1, 0.55, 8, 24);
    const eegMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.65, roughness: 0.2, metalness: 0.5 });
    const ringMat = new THREE.MeshStandardMaterial({ color: 0xf5d078, emissive: 0xb45309, emissiveIntensity: 0.45, roughness: 0.25, metalness: 0.7 });
    ATLAS.eeg1020.forEach((el, idx) => {
      const p = mniToThree(el.mni[0], el.mni[1], el.mni[2]);
      eegPts[el.id] = p;
      const node = new THREE.Group();
      node.position.copy(p);
      // Orient flat electrode sensor normal radially outward from brain center
      const outward = p.clone().normalize();
      node.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), outward);
      const disc = new THREE.Mesh(discGeo, eegMat.clone());
      disc.userData = { kind: 'eeg', eegIndex: idx, key: 'Frontal', label: `EEG ${el.id} · ${el.ba}` };
      const rim = new THREE.Mesh(ringGeo, ringMat);
      rim.rotation.x = Math.PI / 2;
      node.add(disc, rim);
      gEegCap.add(node);
      clickableMeshes.push(disc);
      eegMeshes.push(disc);
    });
    // Conductive Smart-Textile Geodesic Straps connecting 10-20 array
    const weavePairs = [
      ['Fp1', 'Fp2'], ['Fp1', 'F7'], ['Fp1', 'F3'], ['Fp2', 'F4'], ['Fp2', 'F8'],
      ['F7', 'F3'], ['F3', 'Fz'], ['Fz', 'F4'], ['F4', 'F8'],
      ['F7', 'T3'], ['F3', 'C3'], ['Fz', 'Cz'], ['F4', 'C4'], ['F8', 'T4'],
      ['T3', 'C3'], ['C3', 'Cz'], ['Cz', 'C4'], ['C4', 'T4'],
      ['T3', 'T5'], ['C3', 'P3'], ['Cz', 'Pz'], ['C4', 'P4'], ['T4', 'T6'],
      ['T5', 'P3'], ['P3', 'Pz'], ['Pz', 'P4'], ['P4', 'T6'],
      ['T5', 'O1'], ['P3', 'O1'], ['Pz', 'O1'], ['Pz', 'O2'], ['P4', 'O2'], ['T6', 'O2'], ['O1', 'O2'],
    ];
    const weaveMat = new THREE.MeshBasicMaterial({ color: 0xf5d078, transparent: true, opacity: 0.42 });
    weavePairs.forEach(([a, b]) => {
      if (!eegPts[a] || !eegPts[b]) return;
      const mid = eegPts[a].clone().add(eegPts[b]).multiplyScalar(0.5);
      // Bow gently outward along scalp envelope
      mid.multiplyScalar(1.045);
      const c = new THREE.QuadraticBezierCurve3(eegPts[a], mid, eegPts[b]);
      gEegCap.add(new THREE.Mesh(new THREE.TubeGeometry(c, 12, 0.45, 6, false), weaveMat));
    });
  }
  gEegCap.visible = state.layers.eegCap;

  // 3J. INTERACTIVE FUNCTIONAL NEURAL CIRCUIT SIMULATOR
  const circuitPulses = [];
  function setFunctionalCircuit(circuitId) {
    // Clear existing circuit meshes
    while (gCircuit.children.length) gCircuit.remove(gCircuit.children[0]);
    circuitPulses.length = 0;
    state.activeCircuit = circuitId || '';
    document.querySelectorAll('[data-circuit]').forEach(b => b.classList.toggle('active', b.dataset.circuit === state.activeCircuit));

    if (!circuitId) {
      gTracts.visible = state.layers.tracts;
      return;
    }
    const circ = (ATLAS.circuits || []).find(c => c.id === circuitId);
    if (!circ) return;
    if (state.activeVasc) {
      state.activeVasc = '';
      document.querySelectorAll('[data-vasc]').forEach(b => b.classList.remove('active'));
    }

    // Switch to Holographic Fresnel Glass X-Ray unless already in X-Ray or Connectome Neon
    if (state.mode !== 'xray' && state.mode !== 'connectome') setRenderMode('xray');
    setCameraPreset(circ.cam || 'hero');
    gTracts.visible = false; // isolate this functional circuit cleanly

    const pts = circ.nodes.map(n => mniToThree(n.mni[0], n.mni[1], n.mni[2]));
    const curve = new THREE.CatmullRomCurve3(pts);
    const colHex = parseInt(circ.color.replace('#', ''), 16);

    // Primary glowing synaptic fiber bundle
    const tubeGeo = new THREE.TubeGeometry(curve, 72, 2.2, 12, false);
    const tubeMat = new THREE.MeshStandardMaterial({
      color: colHex, emissive: colHex, emissiveIntensity: 0.85, roughness: 0.2, transparent: true, opacity: 0.92,
    });
    gCircuit.add(new THREE.Mesh(tubeGeo, tubeMat));

    // Outer halo sheath
    const haloGeo = new THREE.TubeGeometry(curve, 72, 3.8, 12, false);
    const haloMat = new THREE.MeshBasicMaterial({ color: colHex, transparent: true, opacity: 0.18, depthWrite: false });
    gCircuit.add(new THREE.Mesh(haloGeo, haloMat));

    // Relay station glowing spheres + pulsing 3D fMRI BOLD hemodynamic halos
    const nodeGeo = new THREE.SphereGeometry(3.8, 18, 14);
    const boldGeo = new THREE.SphereGeometry(8.5, 16, 12);
    const nodeMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: colHex, emissiveIntensity: 1.0, roughness: 0.15 });
    const boldMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0.16, depthWrite: false });
    pts.forEach(p => {
      const sp = new THREE.Mesh(nodeGeo, nodeMat);
      sp.position.copy(p);
      const bh = new THREE.Mesh(boldGeo, boldMat);
      bh.position.copy(p);
      gCircuit.add(sp, bh);
    });

    // 6 bright traveling action-potential packets along the functional circuit
    const pktGeo = new THREE.SphereGeometry(2.6, 12, 10);
    const pktMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    for (let k = 0; k < 6; k++) {
      const m = new THREE.Mesh(pktGeo, pktMat);
      gCircuit.add(m);
      circuitPulses.push({ mesh: m, curve, t: k / 6 });
    }

    // Refresh vertex colors so fMRI BOLD hotspots illuminate on cortex too
    buildCortexColors(geoL, aalLBytes, lobeLBytes, state.mode, state.tau, selectedAalId);
    buildCortexColors(geoR, aalRBytes, lobeRBytes, state.mode, state.tau, selectedAalId);
    geoL.attributes.color.needsUpdate = true;
    geoR.attributes.color.needsUpdate = true;

    renderInspectorCircuit(circ);
    announce(`Activated functional circuit: ${circ.name}`);
  }

  // 3J-B. INTERACTIVE CEREBROVASCULAR TERRITORY & NEUROREHABILITATION SIMULATOR
  function setVascularTerritory(vascId) {
    state.activeVasc = vascId || '';
    document.querySelectorAll('[data-vasc]').forEach(b => b.classList.toggle('active', b.dataset.vasc === state.activeVasc));

    // Reset cerebellar/brainstem emissive highlight first
    if (meshCerebellum && meshCerebellum.material && meshCerebellum.material.emissive) {
      meshCerebellum.material.emissive.setHex(0x000000);
      meshCerebellum.material.emissiveIntensity = 0;
    }
    gBrainstem.traverse(o => {
      if (o.isMesh && o.material && o.material.emissive) {
        o.material.emissive.setHex(0x000000);
        o.material.emissiveIntensity = 0;
      }
    });

    if (!vascId) {
      buildCortexColors(geoL, aalLBytes, lobeLBytes, state.mode, state.tau, selectedAalId);
      buildCortexColors(geoR, aalRBytes, lobeRBytes, state.mode, state.tau, selectedAalId);
      geoL.attributes.color.needsUpdate = true;
      geoR.attributes.color.needsUpdate = true;
      return;
    }

    const vt = (ATLAS.vascularTerritories || []).find(v => v.id === vascId);
    if (!vt) return;
    if (state.activeCircuit) setFunctionalCircuit('');

    // Show clean SSS Anatomical Tissue (or X-Ray for Basilar/Brainstem)
    if (vascId === 'basilar') {
      setRenderMode('xray');
      setCameraPreset('ventral');
      if (meshCerebellum && meshCerebellum.material && meshCerebellum.material.emissive) {
        meshCerebellum.material.emissive.setHex(0xd97706);
        meshCerebellum.material.emissiveIntensity = 0.52;
      }
      gBrainstem.traverse(o => {
        if (o.isMesh && o.material && o.material.emissive) {
          o.material.emissive.setHex(0xef4444);
          o.material.emissiveIntensity = 0.65;
        }
      });
    } else {
      setRenderMode('tissue');
      setCameraPreset(vt.cam || 'left');
    }

    const sL = buildCortexColors(geoL, aalLBytes, lobeLBytes, state.mode, state.tau, selectedAalId);
    const sR = buildCortexColors(geoR, aalRBytes, lobeRBytes, state.mode, state.tau, selectedAalId);
    geoL.attributes.color.needsUpdate = true;
    geoR.attributes.color.needsUpdate = true;

    const totalVerts = sL.total + sR.total;
    const vascVerts = (sL.vascCount || 0) + (sR.vascCount || 0);
    const affectedPct = vascId === 'basilar' ? 11.4 : ((vascVerts / totalVerts) * 100);
    const reservePct = Math.max(0, 100 - affectedPct);
    setMniCoords(vt.mni[0], vt.mni[1], vt.mni[2]);
    renderInspectorVascular(vt, affectedPct, reservePct);
    announce(`Simulated cerebrovascular territory: ${vt.name}`);
  }

  // 3K. CAD STEREOTAXIC 3D MILLIMETER CALIPER TOOL
  let caliperPts = [];
  function clearCaliper() {
    while (gCaliper.children.length) gCaliper.remove(gCaliper.children[0]);
    caliperPts = [];
    const badge = document.getElementById('caliperBadge');
    if (badge) badge.style.display = 'none';
  }
  function addCaliperPoint(threePt, mniPt, label) {
    if (caliperPts.length >= 2) clearCaliper();
    caliperPts.push({ p: threePt.clone(), mni: mniPt, label });
    const sp = new THREE.Mesh(
      new THREE.SphereGeometry(2.6, 16, 12),
      new THREE.MeshBasicMaterial({ color: caliperPts.length === 1 ? 0x38bdf8 : 0xf5d078, depthTest: false, transparent: true, opacity: 0.96 })
    );
    sp.renderOrder = 999;
    sp.position.copy(threePt);
    gCaliper.add(sp);
    const badge = document.getElementById('caliperBadge');
    if (caliperPts.length === 1) {
      badge.textContent = `CAD Caliper: Point A (${mniPt.map(Math.round).join(', ')} mm) — click Point B to measure`;
      badge.style.display = 'block';
    } else {
      const a = caliperPts[0], b = caliperPts[1];
      const dx = b.mni[0] - a.mni[0], dy = b.mni[1] - a.mni[1], dz = b.mni[2] - a.mni[2];
      const dist = Math.hypot(dx, dy, dz);
      const lineGeo = new THREE.BufferGeometry().setFromPoints([a.p, b.p]);
      const lineObj = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: 0x38bdf8, depthTest: false }));
      lineObj.renderOrder = 998;
      gCaliper.add(lineObj);
      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(new THREE.LineCurve3(a.p, b.p), 4, 0.95, 8, false),
        new THREE.MeshBasicMaterial({ color: 0x38bdf8, depthTest: false, transparent: true, opacity: 0.92 })
      );
      tube.renderOrder = 998;
      gCaliper.add(tube);
      badge.innerHTML = `<strong>CAD Distance: ${dist.toFixed(1)} mm</strong> &nbsp;|&nbsp; ΔX ${dx.toFixed(1)} · ΔY ${dy.toFixed(1)} · ΔZ ${dz.toFixed(1)} mm &nbsp;(${a.label.split(' (')[0]} → ${b.label.split(' (')[0]})`;
      badge.style.display = 'block';
      announce(`Measured stereotaxic distance ${dist.toFixed(1)} millimeters`);
    }
  }

  // Pulsing Selection Beacon + 3D Stereotaxic Crosshair
  const beaconGroup = new THREE.Group();
  const beaconCore = new THREE.Mesh(
    new THREE.SphereGeometry(2.6, 18, 14),
    new THREE.MeshBasicMaterial({ color: 0xf5d078 })
  );
  const beaconRing = new THREE.Mesh(
    new THREE.RingGeometry(4.2, 5.8, 32),
    new THREE.MeshBasicMaterial({ color: 0x38bdf8, side: THREE.DoubleSide, transparent: true, opacity: 0.85 })
  );
  beaconGroup.add(beaconCore, beaconRing);
  beaconGroup.visible = false;
  scene.add(beaconGroup);

  // Subtle 3D crosshair lines (visible when clipping or MRI active)
  const crossMat = new THREE.LineBasicMaterial({ color: 0xf5d078, transparent: true, opacity: 0.45 });
  function makeAxisLine(a, b) {
    const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
    return new THREE.Line(g, crossMat);
  }
  const crossGroup = new THREE.Group();
  const lineX = makeAxisLine([-85, 0, 0], [85, 0, 0]);
  const lineY = makeAxisLine([0, -80, 0], [0, 90, 0]);
  const lineZ = makeAxisLine([0, 0, -115], [0, 0, 85]);
  crossGroup.add(lineX, lineY, lineZ);
  crossGroup.visible = false;
  scene.add(crossGroup);

  // ── CAMERA ORBIT / PAN / ZOOM / SMOOTH FLY-TO CONTROLLER ──────────────────
  const camState = {
    yaw: 0.68,
    pitch: 0.24,
    dist: 245,
    target: new THREE.Vector3(0, 6, -12),
    goalYaw: 0.68,
    goalPitch: 0.24,
    goalDist: 245,
    goalTarget: new THREE.Vector3(0, 6, -12),
    dragging: false,
    panning: false,
    lastX: 0,
    lastY: 0,
    moved: false,
  };

  function updateCameraTransform(snap = false) {
    const k = snap ? 1.0 : 0.14;
    camState.yaw += (camState.goalYaw - camState.yaw) * k;
    camState.pitch += (camState.goalPitch - camState.pitch) * k;
    camState.dist += (camState.goalDist - camState.dist) * k;
    camState.target.lerp(camState.goalTarget, k);

    const cp = Math.cos(camState.pitch);
    camera.position.set(
      camState.target.x + camState.dist * Math.sin(camState.yaw) * cp,
      camState.target.y + camState.dist * Math.sin(camState.pitch),
      camState.target.z + camState.dist * Math.cos(camState.yaw) * cp
    );
    camera.lookAt(camState.target);
    beaconRing.lookAt(camera.position);
  }

  function setCameraPreset(name) {
    hoverTip.style.display = 'none';
    state.autoOrbit = false;
    document.getElementById('btnAutoOrbit').classList.remove('active');
    const presets = {
      hero:      { yaw: 0.68, pitch: 0.24, dist: 245, t: [0, 6, -12] },
      left:      { yaw: Math.PI / 2, pitch: 0.05, dist: 235, t: [0, 6, -14] },
      right:     { yaw: -Math.PI / 2, pitch: 0.05, dist: 235, t: [0, 6, -14] },
      sagittal:  { yaw: Math.PI / 2, pitch: 0.04, dist: 215, t: [0, 4, -14], sagCut: true },
      dorsal:    { yaw: 0.0, pitch: 1.48, dist: 245, t: [0, 6, -14] },
      ventral:   { yaw: 0.0, pitch: -1.48, dist: 235, t: [0, -6, -14] },
      posterior: { yaw: Math.PI, pitch: 0.08, dist: 235, t: [0, 0, -14] },
      deep:      { yaw: 0.55, pitch: 0.18, dist: 145, t: [0, 0, -10], xray: true },
    };
    const aliases = { iso: 'hero', latL: 'left', latR: 'right', medL: 'sagittal' };
    const key = aliases[name] || name;
    const p = presets[key] || presets.hero;
    camState.goalYaw = p.yaw;
    camState.goalPitch = p.pitch;
    camState.goalDist = p.dist;
    camState.goalTarget.set(p.t[0], p.t[1], p.t[2]);
    if (p.sagCut) {
      state.layers.cortexL = false;
      state.layers.cortexR = true;
      document.getElementById('chk-cortexL').checked = false;
      document.getElementById('chk-cortexR').checked = true;
      applyLayerVisibility();
    } else {
      state.layers.cortexL = true;
      state.layers.cortexR = true;
      document.getElementById('chk-cortexL').checked = true;
      document.getElementById('chk-cortexR').checked = true;
      applyLayerVisibility();
    }
    if (p.xray) setRenderMode('xray');
  }

  function flyToMni(mni, label) {
    const v = mniToThree(mni[0], mni[1], mni[2]);
    beaconGroup.position.copy(v);
    beaconGroup.visible = true;
    setMniCoords(mni[0], mni[1], mni[2]);
    // Compute ideal viewing azimuth facing outward from origin toward v
    const ang = Math.atan2(v.x || 1, v.z || 1);
    camState.goalYaw = ang;
    camState.goalPitch = Math.max(-0.85, Math.min(0.85, Math.asin(Math.max(-0.8, Math.min(0.8, v.y / 95)))));
    camState.goalDist = 175;
    camState.goalTarget.copy(v).multiplyScalar(0.35);
    if (label) announce(`Focused on ${label} at MNI ${Math.round(mni[0])}, ${Math.round(mni[1])}, ${Math.round(mni[2])} millimeters`);
  }

  // Pointer, Multi-Touch Pinch-Zoom & Wheel interaction
  const raycaster = new THREE.Raycaster();
  const pointerNDC = new THREE.Vector2();
  const hoverTip = document.getElementById('hoverTip');

  renderer.domElement.style.touchAction = 'none';
  const activePointers = new Map();
  let prevPinchDist = 0;
  let prevPinchMidX = 0;
  let prevPinchMidY = 0;

  function getPinchMetrics() {
    const pts = Array.from(activePointers.values());
    const dx = pts[1].x - pts[0].x;
    const dy = pts[1].y - pts[0].y;
    return {
      dist: Math.hypot(dx, dy),
      midX: (pts[0].x + pts[1].x) * 0.5,
      midY: (pts[0].y + pts[1].y) * 0.5,
    };
  }

  renderer.domElement.addEventListener('pointerdown', (e) => {
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try { renderer.domElement.setPointerCapture(e.pointerId); } catch (_) {}
    if (activePointers.size === 1) {
      camState.dragging = true;
      camState.panning = (e.button === 2 || e.shiftKey);
      camState.lastX = e.clientX;
      camState.lastY = e.clientY;
      camState.moved = false;
    } else if (activePointers.size === 2) {
      camState.dragging = false;
      camState.moved = true;
      const m = getPinchMetrics();
      prevPinchDist = m.dist;
      prevPinchMidX = m.midX;
      prevPinchMidY = m.midY;
    }
  });

  renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());

  renderer.domElement.addEventListener('pointermove', (e) => {
    if (activePointers.has(e.pointerId)) {
      activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    }
    if (activePointers.size === 2) {
      const m = getPinchMetrics();
      if (prevPinchDist > 4 && m.dist > 4) {
        const ratio = prevPinchDist / m.dist;
        camState.goalDist = Math.max(70, Math.min(480, camState.goalDist * ratio));
      }
      const mdx = m.midX - prevPinchMidX;
      const mdy = m.midY - prevPinchMidY;
      const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
      const up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
      const scale = camState.dist * 0.0014;
      camState.goalTarget.addScaledVector(right, -mdx * scale);
      camState.goalTarget.addScaledVector(up, mdy * scale);
      prevPinchDist = m.dist;
      prevPinchMidX = m.midX;
      prevPinchMidY = m.midY;
      hoverTip.style.display = 'none';
      return;
    }
    const rect = renderer.domElement.getBoundingClientRect();
    if (camState.dragging) {
      const dx = e.clientX - camState.lastX;
      const dy = e.clientY - camState.lastY;
      if (Math.abs(dx) + Math.abs(dy) > 4) camState.moved = true;
      camState.lastX = e.clientX;
      camState.lastY = e.clientY;
      if (camState.panning) {
        const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
        const up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
        const scale = camState.dist * 0.0014;
        camState.goalTarget.addScaledVector(right, -dx * scale);
        camState.goalTarget.addScaledVector(up, dy * scale);
      } else {
        camState.goalYaw -= dx * 0.0075;
        camState.goalPitch = Math.max(-1.52, Math.min(1.52, camState.goalPitch + dy * 0.0075));
      }
      hoverTip.style.display = 'none';
      return;
    }
    if (e.pointerType === 'touch') return;

    // Hover raycast tooltip (mouse/stylus)
    pointerNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointerNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    const hit = pickStructure();
    if (hit) {
      hoverTip.style.display = 'block';
      hoverTip.style.left = Math.min(rect.width - 230, e.clientX - rect.left + 14) + 'px';
      hoverTip.style.top = Math.max(10, e.clientY - rect.top - 34) + 'px';
      hoverTip.textContent = `${hit.title} (${hit.mni.map(Math.round).join(', ')} mm)`;
      renderer.domElement.style.cursor = 'pointer';
    } else {
      hoverTip.style.display = 'none';
      renderer.domElement.style.cursor = 'grab';
    }
  });

  function endPointer(e) {
    const wasSingleClick = activePointers.size === 1 && camState.dragging && !camState.moved;
    activePointers.delete(e.pointerId);
    if (activePointers.size < 2) prevPinchDist = 0;
    if (activePointers.size === 0) {
      camState.dragging = false;
      camState.panning = false;
    } else if (activePointers.size === 1) {
      const rem = Array.from(activePointers.values())[0];
      camState.dragging = true;
      camState.panning = false;
      camState.lastX = rem.x;
      camState.lastY = rem.y;
      camState.moved = true;
    }
    if (wasSingleClick) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointerNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointerNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      const hit = pickStructure();
      if (hit) handleStructureSelection(hit);
    }
  }
  renderer.domElement.addEventListener('pointerup', endPointer);
  renderer.domElement.addEventListener('pointercancel', endPointer);

  renderer.domElement.addEventListener('pointerleave', () => {
    hoverTip.style.display = 'none';
  });

  renderer.domElement.addEventListener('wheel', (e) => {
    e.preventDefault();
    camState.goalDist = Math.max(70, Math.min(480, camState.goalDist * (1 + e.deltaY * 0.001)));
  }, { passive: false });

  // Keyboard navigation for accessibility
  document.addEventListener('keydown', (e) => {
    if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
    if (e.key === 'Escape') { closeLightbox(); return; }
    if (state.activeTab !== 'brain3d') return;
    const step = 0.14;
    if (e.key === 'ArrowLeft' || e.key === 'a') camState.goalYaw -= step;
    else if (e.key === 'ArrowRight' || e.key === 'd') camState.goalYaw += step;
    else if (e.key === 'ArrowUp' || e.key === 'w') camState.goalPitch = Math.min(1.5, camState.goalPitch + step);
    else if (e.key === 'ArrowDown' || e.key === 's') camState.goalPitch = Math.max(-1.5, camState.goalPitch - step);
    else if (e.key === '+' || e.key === '=') camState.goalDist = Math.max(70, camState.goalDist - 22);
    else if (e.key === '-' || e.key === '_') camState.goalDist = Math.min(480, camState.goalDist + 22);
    else if (e.key === 'r' || e.key === 'R') setCameraPreset('hero');
  });

  function isObjVisible(o) {
    let cur = o;
    while (cur) { if (!cur.visible) return false; cur = cur.parent; }
    return true;
  }

  function pickStructure() {
    const visibleTargets = clickableMeshes.filter(isObjVisible);
    raycaster.setFromCamera(pointerNDC, camera);
    const rawHits = raycaster.intersectObjects(visibleTargets, false);
    // Filter out clipped hits first
    const unclipped = rawHits.filter(h => {
      if (!state.clipEnabled) return true;
      for (const pl of activeClipPlanes) {
        if (pl.distanceToPoint(h.point) < 0) return false;
      }
      return true;
    });
    // Smart X-Ray picking: when cortex is translucent (<55%), prioritize deep internal structures over outer cortex!
    const isCortexGlass = (state.mode === 'xray' || state.mode === 'connectome' || matCortexL.opacity < 0.55);
    const orderedHits = isCortexGlass
      ? [...unclipped.filter(h => h.object.userData.kind !== 'cortex'), ...unclipped.filter(h => h.object.userData.kind === 'cortex')]
      : [...unclipped.filter(h => h.object.userData.kind === 'eeg' || h.object.userData.kind === 'brodmann'), ...unclipped.filter(h => h.object.userData.kind !== 'eeg' && h.object.userData.kind !== 'brodmann')];

    for (const h of orderedHits) {
      const u = h.object.userData;
      const mni = threeToMni(h.point);
      if (u.kind === 'eeg') {
        return { kind: 'eeg', eegIndex: u.eegIndex, key: 'Frontal', title: u.label, mni, point: h.point };
      }
      if (u.kind === 'cortex') {
        const vIdx = h.face ? h.face.a : 0;
        const aid = u.aalArr[vIdx];
        const lobeId = u.lobeArr[vIdx];
        const lobeName = LOBE_NAMES[lobeId] || 'Frontal';
        const parcel = (MESHES.aalNames[aid] || lobeName).replace(/_/g, ' ');
        return { kind: 'cortex', key: lobeName, aalId: aid, title: `${parcel} (${lobeName} Lobe)`, parcel, mni, point: h.point };
      }
      if (u.kind === 'cit168') {
        const vIdx = h.face ? h.face.a : 0;
        const cid = u.idArr[vIdx];
        const cname = u.labelMap[String(cid)] || 'Subcortical Nucleus';
        return { kind: 'cit168', key: 'BasalGanglia', title: `${cname} (CIT168 #${cid})`, mni, point: h.point };
      }
      if (u.kind === 'cerebellum') {
        const vIdx = h.face ? h.face.a : 0;
        const aid = u.idArr[vIdx];
        const aname = (u.labelMap[aid] || 'Cerebellum').replace(/_/g, ' ');
        return { kind: 'cerebellum', key: 'Cerebellum', title: `${aname} (Cerebellum)`, mni, point: h.point };
      }
      if (u.kind === 'thalamus') {
        const vIdx = h.face ? h.face.a : 0;
        const aid = u.idArr[vIdx];
        return { kind: 'thalamus', key: 'Thalamus', title: (u.labelMap[aid] || 'Thalamus').replace(/_/g, ' '), mni, point: h.point };
      }
      if (u.kind === 'limbic') {
        const vIdx = h.face ? h.face.a : 0;
        const aid = u.idArr[vIdx];
        return { kind: 'limbic', key: 'Limbic', title: (u.labelMap[aid] || 'Limbic Structure').replace(/_/g, ' '), mni, point: h.point };
      }
      if (u.kind === 'brodmann') {
        return { kind: 'brodmann', baIndex: u.baIndex, key: u.key, title: u.label, mni, point: h.point };
      }
      if (u.kind === 'cranial') {
        return { kind: 'cranial', cnIndex: u.cnIndex, key: 'CranialNerves', title: u.label, mni, point: h.point };
      }
      if (u.kind === 'tract') {
        return { kind: 'tract', tractIdx: u.tractIdx, key: 'WhiteMatter', title: u.label, mni, point: h.point };
      }
      return { kind: 'structure', key: u.key || 'Brainstem', title: u.label || u.key, mni, point: h.point };
    }
    return null;
  }

  function handleStructureSelection(hit) {
    if (state.measureMode) {
      addCaliperPoint(hit.point, hit.mni, hit.title);
      return;
    }
    beaconGroup.position.copy(hit.point);
    beaconGroup.visible = true;
    setMniCoords(hit.mni[0], hit.mni[1], hit.mni[2]);
    // Highlight clicked real AAL-116 cortical region directly on the 3D mesh!
    const nextAal = (hit.kind === 'cortex' && hit.aalId) ? hit.aalId : -1;
    if (nextAal !== selectedAalId) {
      selectedAalId = nextAal;
      buildCortexColors(geoL, aalLBytes, lobeLBytes, state.mode, state.tau, selectedAalId);
      buildCortexColors(geoR, aalRBytes, lobeRBytes, state.mode, state.tau, selectedAalId);
      geoL.attributes.color.needsUpdate = true;
      geoR.attributes.color.needsUpdate = true;
    }
    if (hit.kind === 'eeg') {
      renderInspectorEeg(hit.eegIndex);
    } else if (hit.kind === 'brodmann') {
      renderInspectorBrodmann(hit.baIndex);
    } else if (hit.kind === 'cranial') {
      renderInspectorCranial(hit.cnIndex);
    } else if (hit.kind === 'tract') {
      renderInspectorTract(hit.tractIdx);
    } else {
      renderInspectorStructure(hit.key, hit.title, hit.mni);
    }
    announce(`Selected ${hit.title} at MNI ${Math.round(hit.mni[0])}, ${Math.round(hit.mni[1])}, ${Math.round(hit.mni[2])} millimeters`);
  }

  // ── RENDER MODES, LAYERS, EXPLODE & CLIPPING ──────────────────────────────
  function setRenderMode(mode) {
    state.mode = mode;
    document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    if (mode !== 'biomech' && window.__DOROTHY_BIOMECH && window.__DOROTHY_BIOMECH.restoreGeometry) {
      window.__DOROTHY_BIOMECH.restoreGeometry();
    }
    const statL = buildCortexColors(geoL, aalLBytes, lobeLBytes, mode, state.tau, selectedAalId);
    const statR = buildCortexColors(geoR, aalRBytes, lobeRBytes, mode, state.tau, selectedAalId);
    geoL.attributes.color.needsUpdate = true;
    geoR.attributes.color.needsUpdate = true;

    const isWire = (mode === 'cad');
    const isXray = (mode === 'xray');
    const isConn = (mode === 'connectome');
    const isTissue = (mode === 'tissue');
    const targetOp = isXray ? 0.34 : (isConn ? 0.30 : (isWire ? 0.42 : 1.0));
    const isTrans = targetOp < 0.99;

    if (isTissue) {
      meshCortexL.material = matTissueSSS;
      meshCortexR.material = matTissueSSS;
      matTissueSSS.uniforms.uOpacity.value = targetOp;
      matTissueSSS.transparent = isTrans;
      matTissueSSS.depthWrite = !isTrans || targetOp > 0.72;
      matTissueSSS.side = isTrans || state.clipEnabled || !state.layers.cortexL || !state.layers.cortexR ? THREE.DoubleSide : THREE.FrontSide;
      matTissueSSS.clippingPlanes = activeClipPlanes;
      matTissueSSS.needsUpdate = true;
    } else if (isXray) {
      meshCortexL.material = matFresnelXray;
      meshCortexR.material = matFresnelXray;
      matFresnelXray.uniforms.uOpacity.value = targetOp;
      matFresnelXray.clippingPlanes = activeClipPlanes;
    } else if (isConn) {
      meshCortexL.material = matFresnelConn;
      meshCortexR.material = matFresnelConn;
      matFresnelConn.uniforms.uOpacity.value = targetOp;
      matFresnelConn.clippingPlanes = activeClipPlanes;
    } else {
      meshCortexL.material = matCortexL;
      meshCortexR.material = matCortexR;
      [matCortexL, matCortexR].forEach(m => {
        m.wireframe = isWire;
        m.transparent = isTrans;
        m.opacity = targetOp;
        m.depthWrite = !isTrans || targetOp > 0.72;
        m.side = isTrans || state.clipEnabled || !state.layers.cortexL || !state.layers.cortexR ? THREE.DoubleSide : THREE.FrontSide;
        m.roughness = 0.38;
        m.emissive.setHex(0x000000);
        m.emissiveIntensity = 0.0;
        m.clippingPlanes = activeClipPlanes;
        m.needsUpdate = true;
      });
    }
    meshCerebellum.material.wireframe = isWire;
    meshCIT168.material.wireframe = isWire;

    // Show/hide Dorothy Continuum tau bar & Biomechanics Lab box
    const tauBox = document.getElementById('tauBox');
    tauBox.style.display = (mode === 'continuum') ? 'block' : 'none';
    const bmBox = document.getElementById('biomechBox');
    if (bmBox) bmBox.style.display = (mode === 'biomech') ? 'block' : 'none';
    if (mode === 'biomech' && window.__DOROTHY_BIOMECH && window.__DOROTHY_BIOMECH.applyTo3D) {
      window.__DOROTHY_BIOMECH.applyTo3D();
    } else if (mode === 'continuum') {
      const acc = statL.accessibleCount + statR.accessibleCount;
      const tot = statL.total + statR.total;
      const pct = ((acc / tot) * 100).toFixed(1);
      document.getElementById('tauReadout').textContent = `A_tau(p) = ${acc.toLocaleString()} verts (${pct}%)`;
      document.getElementById('hudMeta').textContent = `Dorothy Continuum · τ=${state.tau.toFixed(2)} · A_τ(p)=${pct}%`;
    } else {
      document.getElementById('hudMeta').textContent = `ICBM152 + AAL-116 + CIT168 · ${(MESHES.cortexLH.nf * 2 + MESHES.cerebellum.nf + MESHES.cit168.nf + MESHES.thalamus.nf + MESHES.limbicCore.nf).toLocaleString()} real triangles`;
    }

    document.getElementById('sliderOpacity').value = Math.round(targetOp * 100);
    document.getElementById('lblOpacity').textContent = Math.round(targetOp * 100) + '%';
    updateLegend();
  }

  function updateLegend() {
    const box = document.getElementById('legendBox');
    if (!box) return;
    if (state.mode === 'lobe') {
      box.innerHTML = `<div class="leg-t">Cortical Lobes (AAL-116)</div>
        <div class="leg-row"><span class="dot" style="background:#478ff5"></span>Frontal <span class="dot" style="background:#29c7b8"></span>Parietal <span class="dot" style="background:#f2a638"></span>Temporal</div>
        <div class="leg-row"><span class="dot" style="background:#e057ad"></span>Occipital <span class="dot" style="background:#a36bf5"></span>Insula <span class="dot" style="background:#3dcc7a"></span>Limbic</div>`;
      box.style.display = 'block';
    } else if (state.mode === 'xray' || state.mode === 'connectome') {
      box.innerHTML = `<div class="leg-t">DTI Tracts &amp; Deep Nuclei</div>
        <div class="leg-row"><span class="dot" style="background:#ef4444"></span>L–R Callosal / Arteries <span class="dot" style="background:#22c55e"></span>A–P Assoc. <span class="dot" style="background:#3b82f6"></span>S–I Motor</div>
        <div class="leg-row"><span class="dot" style="background:#38bdf8"></span>Ventricles <span class="dot" style="background:#f2b83d"></span>Thalamus <span class="dot" style="background:#fde047"></span>CN I–XII</div>`;
      box.style.display = 'block';
    } else if (state.mode === 'biomech') {
      box.innerHTML = `<div class="leg-t">Coupled Biomechanics &amp; Continuum Lab</div>
        <div class="leg-bar" style="background:linear-gradient(90deg,#1a243d 0%,#23b3eb 32%,#ebdf2e 68%,#fc195e 100%)"></div>
        <div class="leg-row" style="justify-content:space-between"><span>Low Strain / Contrecoup</span><span>Peak Strain / Coup</span></div>`;
      box.style.display = 'block';
    } else if (state.mode === 'continuum') {
      box.innerHTML = `<div class="leg-t">Dorothy Continuum A_τ(p)</div>
        <div class="leg-bar"></div>
        <div class="leg-row" style="justify-content:space-between"><span>p ≤ τ (quiet)</span><span>p &gt; τ (accessible)</span></div>`;
      box.style.display = 'block';
    } else {
      box.style.display = 'none';
    }
  }

  function syncCortexDoubleSide() {
    const needDouble = matCortexL.transparent || matTissueSSS.transparent || state.clipEnabled || !state.layers.cortexL || !state.layers.cortexR;
    [matCortexL, matCortexR, matTissueSSS].forEach(m => {
      m.side = needDouble ? THREE.DoubleSide : THREE.FrontSide;
      m.needsUpdate = true;
    });
  }

  function applyLayerVisibility() {
    for (const [k, v] of Object.entries(state.layers)) {
      if (groups[k]) groups[k].visible = v;
    }
    syncCortexDoubleSide();
  }

  function applyExplode(val) {
    state.explode = val;
    document.getElementById('sliderExplode').value = Math.round(val * 100);
    document.getElementById('lblExplode').textContent = Math.round(val * 100) + '%';
    for (const g of Object.values(groups)) {
      g.position.copy(g.userData.explode).multiplyScalar(val);
    }
  }

  function applyClipping() {
    activeClipPlanes.length = 0;
    frameSag.visible = false;
    frameCor.visible = false;
    frameAx.visible = false;
    if (state.clipEnabled) {
      const sx = parseFloat(document.getElementById('clipX').value);
      const cy = parseFloat(document.getElementById('clipY').value);
      const az = parseFloat(document.getElementById('clipZ').value);
      clipSag.constant = -sx;
      clipCor.constant = cy;
      clipAx.constant  = az;
      if (sx > -72) {
        activeClipPlanes.push(clipSag);
        frameSag.position.set(-sx - 0.15, 0, 0);
        frameSag.visible = true;
      }
      if (cy < 72) {
        activeClipPlanes.push(clipCor);
        frameCor.position.set(0, 0, cy - 0.15);
        frameCor.visible = true;
      }
      if (az < 82) {
        activeClipPlanes.push(clipAx);
        frameAx.position.set(0, az - 0.15, 0);
        frameAx.visible = true;
      }
      crossGroup.visible = true;
    } else {
      crossGroup.visible = false;
    }
    brainRoot.traverse(obj => {
      if (obj.isMesh && obj.material) {
        obj.material.clippingPlanes = activeClipPlanes;
        obj.material.needsUpdate = true;
      }
    });
    [matTissueSSS, matFresnelXray, matFresnelConn].forEach(m => {
      m.clippingPlanes = activeClipPlanes;
      m.needsUpdate = true;
    });
    // Mutually clip each 3D MRI texture plane by the OTHER active clipping planes so multi-plane cuts form a crisp 3D surgical corner!
    const clipFor = (selfPlane) => activeClipPlanes.filter(p => p !== selfPlane);
    [
      [frameSag, clipSag],
      [frameCor, clipCor],
      [frameAx,  clipAx],
    ].forEach(([fr, selfP]) => {
      const others = clipFor(selfP);
      fr.userData.mesh.material.clippingPlanes = others;
      fr.userData.mesh.material.needsUpdate = true;
      if (fr.userData.border) {
        fr.userData.border.material.clippingPlanes = others;
        fr.userData.border.material.needsUpdate = true;
      }
    });
    syncCortexDoubleSide();
    update3dMriTextures();
  }

  // 1-Click MRI Slice Presets
  function setSlicePreset(which) {
    const cx = document.getElementById('clipX');
    const cy = document.getElementById('clipY');
    const cz = document.getElementById('clipZ');
    const chk = document.getElementById('chkClip');
    if (which === 'reset' || which === 'none') {
      cx.value = -72; cy.value = 72; cz.value = 82;
      chk.checked = false; state.clipEnabled = false;
    } else {
      cx.value = which === 'sag' ? 0 : -72;
      cy.value = which === 'cor' ? -14 : 72;
      cz.value = which === 'ax' ? 6 : 82;
      chk.checked = true; state.clipEnabled = true;
      setMniCoords(which === 'sag' ? 0 : state.mni[0], which === 'cor' ? -14 : state.mni[1], which === 'ax' ? 6 : state.mni[2]);
    }
    document.getElementById('lbl-clipX').textContent = `${cx.value} mm`;
    document.getElementById('lbl-clipY').textContent = `${cy.value} mm`;
    document.getElementById('lbl-clipZ').textContent = `${cz.value} mm`;
    applyClipping();
  }

  // ── REAL MNI152 TRI-PLANAR T1-MRI SYNCHRONIZED VIEWER ─────────────────────
  const mriImgs = { axial: new Image(), coronal: new Image(), sagittal: new Image() };
  let mriReady = 0;
  function onMriLoad() { mriReady++; if (mriReady >= 3) { drawAllMri(); update3dMriTextures(); } }
  mriImgs.axial.onload = onMriLoad;
  mriImgs.coronal.onload = onMriLoad;
  mriImgs.sagittal.onload = onMriLoad;
  mriImgs.axial.src = 'mri_slices/axial_sheet.jpg';
  mriImgs.coronal.src = 'mri_slices/coronal_sheet.jpg';
  mriImgs.sagittal.src = 'mri_slices/sagittal_sheet.jpg';

  function nearestSliceIdx(arr, val) {
    let best = 0, bestD = 1e9;
    for (let i = 0; i < arr.length; i++) {
      const d = Math.abs(arr[i] - val);
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  function setMniCoords(x, y, z) {
    const b = MESHES.mriMeta.bounds_mm;
    state.mni = [
      Math.max(b.x[0], Math.min(b.x[1], x)),
      Math.max(b.y[0], Math.min(b.y[1], y)),
      Math.max(b.z[0], Math.min(b.z[1], z)),
    ];
    document.getElementById('hudMni').textContent =
      `MNI (${Math.round(state.mni[0])}, ${Math.round(state.mni[1])}, ${Math.round(state.mni[2])}) mm`;
    const p = mniToThree(state.mni[0], state.mni[1], state.mni[2]);
    lineX.position.set(0, p.y, p.z);
    lineY.position.set(p.x, 0, p.z);
    lineZ.position.set(p.x, p.y, 0);
    drawAllMri();
  }

  // Radiology Colormaps (T1 Gray, Synthetic T2-Invert, fMRI Hot-Metal, Viridis)
  function applyMriColormap(imgData, cmap, transparentAir) {
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
      const raw = d[i]; // grayscale T1 luminance 0..255
      if (transparentAir) {
        if (raw < 14) { d[i + 3] = 0; continue; }
        d[i + 3] = raw < 28 ? Math.round(((raw - 14) / 14) * 238) : 240;
      }
      if (cmap === 't1') continue;
      const t = raw / 255.0;
      let r = raw, g = raw, b = raw;
      if (cmap === 't2') {
        // Synthetic T2-contrast visualization: bright CSF/ventricles inside skull, darker WM
        if (raw < 16) { r = 0; g = 0; b = 0; }
        else {
          const inv = Math.max(0, Math.min(1, 1.08 - t * 0.96));
          r = Math.round(inv * 225);
          g = Math.round(inv * 242);
          b = Math.round(Math.min(255, inv * 255 + 14));
        }
      } else if (cmap === 'hot') {
        r = Math.round(Math.min(1, t * 2.6) * 255);
        g = Math.round(Math.max(0, Math.min(1, (t - 0.36) * 2.5)) * 255);
        b = Math.round(Math.max(0, Math.min(1, (t - 0.72) * 3.6)) * 255);
      } else if (cmap === 'viridis') {
        if (raw < 12) { r = 6; g = 4; b = 18; }
        else if (t < 0.33) {
          const u = t / 0.33;
          r = Math.round(68 * (1 - u) + 49 * u);
          g = Math.round(1 * (1 - u) + 104 * u);
          b = Math.round(84 * (1 - u) + 142 * u);
        } else if (t < 0.66) {
          const u = (t - 0.33) / 0.33;
          r = Math.round(49 * (1 - u) + 53 * u);
          g = Math.round(104 * (1 - u) + 183 * u);
          b = Math.round(142 * (1 - u) + 121 * u);
        } else {
          const u = (t - 0.66) / 0.34;
          r = Math.round(53 * (1 - u) + 253 * u);
          g = Math.round(183 * (1 - u) + 231 * u);
          b = Math.round(121 * (1 - u) + 37 * u);
        }
      }
      d[i] = r; d[i + 1] = g; d[i + 2] = b;
    }
  }

  function update3dMriTextures() {
    if (mriReady < 3) return;
    const grid = MESHES.mriMeta.grid;
    const cell = MESHES.mriMeta.cell;
    const sx = parseFloat(document.getElementById('clipX').value);
    const cy = parseFloat(document.getElementById('clipY').value);
    const az = parseFloat(document.getElementById('clipZ').value);
    const specs = [
      { frame: frameSag, img: mriImgs.sagittal, vals: MESHES.mriMeta.sagittal_x, val: sx },
      { frame: frameCor, img: mriImgs.coronal,  vals: MESHES.mriMeta.coronal_y,  val: cy },
      { frame: frameAx,  img: mriImgs.axial,    vals: MESHES.mriMeta.axial_z,    val: az },
    ];
    for (const sp of specs) {
      if (!sp.frame.visible || !sp.img.complete || sp.img.naturalWidth === 0) continue;
      const cvs = sp.frame.userData.cvs;
      const ctx = cvs.getContext('2d');
      const idx = nearestSliceIdx(sp.vals, sp.val);
      const r = Math.floor(idx / grid), c = idx % grid;
      ctx.clearRect(0, 0, cvs.width, cvs.height);
      ctx.drawImage(sp.img, c * cell, r * cell, cell, cell, 0, 0, cvs.width, cvs.height);
      const idata = ctx.getImageData(0, 0, cvs.width, cvs.height);
      applyMriColormap(idata, state.mriCmap, true);
      ctx.putImageData(idata, 0, 0);
      sp.frame.userData.tex.needsUpdate = true;
    }
  }

  function setMriColormap(cmap) {
    state.mriCmap = cmap || 't1';
    document.querySelectorAll('[data-mricmap]').forEach(b => b.classList.toggle('active', b.dataset.mricmap === state.mriCmap));
    drawAllMri();
    update3dMriTextures();
  }

  function drawMriPlane(canvasId, img, vals, val, cxFrac, cyFrac, labelText) {
    const cvs = document.getElementById(canvasId);
    if (!cvs || !img.complete || img.naturalWidth === 0) return;
    const ctx = cvs.getContext('2d');
    const W = cvs.width, H = cvs.height;
    const idx = nearestSliceIdx(vals, val);
    const grid = MESHES.mriMeta.grid;
    const cell = MESHES.mriMeta.cell;
    const r = Math.floor(idx / grid), c = idx % grid;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    ctx.drawImage(img, c * cell, r * cell, cell, cell, 0, 0, W, H);
    if (state.mriCmap !== 't1') {
      const idata = ctx.getImageData(0, 0, W, H);
      applyMriColormap(idata, state.mriCmap, false);
      ctx.putImageData(idata, 0, 0);
    }

    // Crosshairs
    const px = Math.max(0, Math.min(W, cxFrac * W));
    const py = Math.max(0, Math.min(H, cyFrac * H));
    ctx.strokeStyle = 'rgba(245, 208, 120, 0.85)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(px, 0); ctx.lineTo(px, H);
    ctx.moveTo(0, py); ctx.lineTo(W, py);
    ctx.stroke();

    ctx.fillStyle = 'rgba(7, 11, 18, 0.72)';
    ctx.fillRect(0, 0, W, 18);
    ctx.fillStyle = '#f5d078';
    ctx.font = 'bold 11px system-ui, sans-serif';
    ctx.fillText(labelText, 6, 13);
  }

  function drawAllMri() {
    const b = MESHES.mriMeta.bounds_mm;
    const [mx, my, mz] = state.mni;
    const fx = (mx - b.x[0]) / (b.x[1] - b.x[0]);
    const fy = (my - b.y[0]) / (b.y[1] - b.y[0]);
    const fz = (mz - b.z[0]) / (b.z[1] - b.z[0]);
    drawMriPlane('mriAxial',    mriImgs.axial,    MESHES.mriMeta.axial_z,    mz, fx, 1 - fy, `AXIAL  Z = ${Math.round(mz)} mm`);
    drawMriPlane('mriCoronal',  mriImgs.coronal,  MESHES.mriMeta.coronal_y,  my, fx, 1 - fz, `CORONAL  Y = ${Math.round(my)} mm`);
    drawMriPlane('mriSagittal', mriImgs.sagittal, MESHES.mriMeta.sagittal_x, mx, fy, 1 - fz, `SAGITTAL  X = ${Math.round(mx)} mm`);
  }

  // Click directly on any real MRI slice to move 3D crosshair & beacon!
  function bindMriClick(canvasId, axis) {
    const cvs = document.getElementById(canvasId);
    cvs.addEventListener('click', (e) => {
      const rect = cvs.getBoundingClientRect();
      const u = (e.clientX - rect.left) / rect.width;
      const v = (e.clientY - rect.top) / rect.height;
      const b = MESHES.mriMeta.bounds_mm;
      let [mx, my, mz] = state.mni;
      if (axis === 'axial') {
        mx = b.x[0] + u * (b.x[1] - b.x[0]);
        my = b.y[0] + (1 - v) * (b.y[1] - b.y[0]);
      } else if (axis === 'coronal') {
        mx = b.x[0] + u * (b.x[1] - b.x[0]);
        mz = b.z[0] + (1 - v) * (b.z[1] - b.z[0]);
      } else {
        my = b.y[0] + u * (b.y[1] - b.y[0]);
        mz = b.z[0] + (1 - v) * (b.z[1] - b.z[0]);
      }
      setMniCoords(mx, my, mz);
      beaconGroup.position.copy(mniToThree(mx, my, mz));
      beaconGroup.visible = true;
    });
  }
  bindMriClick('mriAxial', 'axial');
  bindMriClick('mriCoronal', 'coronal');
  bindMriClick('mriSagittal', 'sagittal');

  // ── RIGHT INSPECTOR RENDERERS (LINKING 3D + PLATES + DOROTHY BOOKS!) ──────
  const bookByIsbn = {};
  VAULT.books.forEach(b => { bookByIsbn[b.isbn] = b; });
  const plateByFile = {};
  ATLAS.plates.forEach(p => { plateByFile[p.file] = p; });

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function renderLinkedPlates(fileList) {
    if (!fileList || !fileList.length) return '';
    return `<div class="insp-block"><h4>Verified Anatomical Plates</h4><div class="mini-plates">` +
      fileList.map(fn => {
        const p = plateByFile[fn];
        if (!p) return '';
        return `<button type="button" class="mini-plate" data-lb-src="plates/${esc(fn)}" data-lb-title="${esc(p.title)}" data-lb-desc="${esc(p.desc)}">
          <img src="plates/${esc(fn)}" alt="${esc(p.title)}" loading="lazy"/>
          <span>${esc(p.title)}</span>
        </button>`;
      }).join('') + `</div></div>`;
  }

  function renderLinkedBooks(isbns) {
    if (!isbns || !isbns.length) return '';
    const cards = isbns.map(id => bookByIsbn[id]).filter(Boolean);
    if (!cards.length) return '';
    return `<div class="insp-block"><h4>Related Dorothy Library Textbooks</h4><div class="mini-books">` +
      cards.map(b => `
        <div class="mini-book">
          <strong>${esc(b.title)}</strong>
          <div class="meta">${esc(b.pub)} · ${esc(b.year)} · ${b.ch} ch · ${b.img} imgs</div>
          ${b.href ? `<a href="${esc(b.href)}" target="_blank" rel="noopener">Open book chapters</a>` : `<span class="meta">Queued in manifest</span>`}
        </div>`).join('') + `</div></div>`;
  }

  function renderInspectorStructure(key, overrideTitle, mni) {
    state.selectedKey = key;
    const info = ATLAS.structures[key] || ATLAS.structures.Frontal;
    const coords = mni || info.mni;
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge">${esc(info.sys)}</div>
      <h3 class="insp-title">${esc(overrideTitle || info.title)}</h3>
      <div class="insp-mni">Stereotaxic MNI152: <code>X=${Math.round(coords[0])}, Y=${Math.round(coords[1])}, Z=${Math.round(coords[2])} mm</code></div>
      <p class="insp-desc">${esc(info.summary)}</p>
      <div class="insp-kv"><strong>Vascular Supply:</strong> ${esc(info.vascular)}</div>
      ${renderLinkedPlates(info.plates)}
      ${renderLinkedBooks(info.books)}
    `;
  }

  function renderInspectorBrodmann(idx) {
    const ba = ATLAS.brodmann[idx];
    if (!ba) return;
    const lobeInfo = ATLAS.structures[ba.lobe] || ATLAS.structures.Frontal;
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge">Brodmann Cytoarchitecture · ${esc(ba.lobe)} Lobe</div>
      <h3 class="insp-title">BA ${esc(ba.ba)} — ${esc(ba.region)}</h3>
      <div class="insp-mni">Stereotaxic MNI152: <code>X=${ba.mni[0]}, Y=${ba.mni[1]}, Z=${ba.mni[2]} mm</code></div>
      <p class="insp-desc">${esc(ba.desc)}</p>
      <div class="insp-kv"><strong>Vascular Territory:</strong> ${esc(lobeInfo.vascular)}</div>
      ${renderLinkedPlates(ba.plates || lobeInfo.plates)}
      ${renderLinkedBooks(lobeInfo.books)}
    `;
  }

  function renderInspectorCranial(idx) {
    const cn = ATLAS.cranialNerves[idx];
    if (!cn) return;
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge">${esc(cn.modality)}</div>
      <h3 class="insp-title">${esc(cn.id)} — ${esc(cn.name)} Nerve</h3>
      <div class="insp-mni">Origin MNI152: <code>X=${cn.mni[0]}, Y=${cn.mni[1]}, Z=${cn.mni[2]} mm</code></div>
      <div class="insp-kv"><strong>Anatomical Origin:</strong> ${esc(cn.origin)}</div>
      <div class="insp-kv"><strong>Skull Exit Foramen:</strong> ${esc(cn.foramen)}</div>
      <p class="insp-desc">${esc(cn.fn)}</p>
      ${renderLinkedPlates(['04_inferior_cranial_nerves.png', '04b_openstax_cranial_nerves.jpg', '07b_cranial_nerves_dti.png'])}
      ${renderLinkedBooks(['9780323957311', '9780124158733'])}
    `;
  }

  function renderInspectorTract(idx) {
    const tr = ATLAS.tracts[idx];
    if (!tr) return;
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge">DTI White Matter · ${esc(tr.cls)} (${esc(tr.dir)})</div>
      <h3 class="insp-title">${esc(tr.name)}</h3>
      <div class="insp-kv"><strong>Pathway Connections:</strong> ${esc(tr.connects)}</div>
      <p class="insp-desc">${esc(tr.fn)}</p>
      ${renderLinkedPlates(['07a_dti_tractography.png', '07c_white_matter_grays.png'])}
      ${renderLinkedBooks(['9780128234020', '9780124158733', '9780136117308'])}
    `;
  }

  let oscSeed = 1;
  function renderInspectorEeg(idx) {
    const el = ATLAS.eeg1020[idx];
    if (!el) return;
    oscSeed = idx + 1;
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge">10–20 EEG &amp; Smart-Textile Sensor Cap</div>
      <h3 class="insp-title">Electrode ${esc(el.id)} — ${esc(el.ba)}</h3>
      <div class="insp-mni">Stereotaxic MNI152: <code>X=${el.mni[0]}, Y=${el.mni[1]}, Z=${el.mni[2]} mm</code></div>
      <div class="insp-kv"><strong>Dominant Rhythm:</strong> ${esc(el.band)}</div>
      <canvas id="eegOsc" width="290" height="72" style="width:100%;height:72px;background:#060c16;border:1px solid #223049;border-radius:7px;margin:6px 0 10px;"></canvas>
      <p class="insp-desc">${esc(el.fn)}</p>
      ${renderLinkedPlates(['03a_brodmann_lateral.png', '03c_brodmann_3d.png'])}
      ${renderLinkedBooks(['9780323914123', '9781119857204', '9780128192474', '9781119460220'])}
    `;
  }

  function renderInspectorCircuit(circ) {
    oscSeed = 20;
    const stepsHtml = circ.nodes.map((n, i) => `<li><strong>${i + 1}. ${esc(n.name)}</strong> <code style="color:#34d399;font-size:0.7rem;">(${n.mni.join(', ')})</code></li>`).join('');
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge" style="border-color:${circ.color};color:${circ.color};">Live Functional Circuit Simulator</div>
      <h3 class="insp-title">${esc(circ.name)}</h3>
      <div class="insp-kv"><strong>Neural Oscillation Band:</strong> ${esc(circ.band)}</div>
      <canvas id="eegOsc" width="290" height="72" style="width:100%;height:72px;background:#060c16;border:1px solid #223049;border-radius:7px;margin:6px 0 10px;"></canvas>
      <p class="insp-desc">${esc(circ.summary)}</p>
      <div class="insp-block"><h4>Synaptic Relay Sequence</h4><ol style="margin:0;padding-left:18px;font-size:0.78rem;color:#d5dfec;">${stepsHtml}</ol></div>
      ${renderLinkedPlates(circ.plates)}
      ${renderLinkedBooks(circ.books)}
    `;
  }

  function renderInspectorVascular(vt, affectedPct, reservePct) {
    document.getElementById('inspectorBody').innerHTML = `
      <div class="insp-badge" style="border-color:${vt.color};color:${vt.color};">Cerebrovascular Territory Simulator (Educational Template)</div>
      <h3 class="insp-title">${esc(vt.name)}</h3>
      <div class="insp-mni">Affected Cortex: <code>${affectedPct.toFixed(1)}%</code> · Kloster A_τ(p) Reserve: <code>${reservePct.toFixed(1)}%</code></div>
      <div class="insp-kv"><strong>Primary Vessel:</strong> ${esc(vt.artery)}</div>
      <div class="insp-kv"><strong>Regions &amp; Brodmann Areas:</strong> ${esc(vt.brodmann)}</div>
      <p class="insp-desc"><strong>Classical Functional Deficit Profile:</strong> ${esc(vt.deficit)}</p>
      <p class="insp-desc"><strong>Neurorehabilitation &amp; Plasticity:</strong> ${esc(vt.rehab)}</p>
      <div class="insp-kv" style="font-size:0.72rem;color:#93a4be;"><strong>Scope Notice:</strong> Educational macroanatomical arterial territory model on standard ICBM152/MNI152 template only — not clinical stroke diagnosis or medical guidance.</div>
      ${renderLinkedPlates(vt.plates)}
      ${renderLinkedBooks(vt.books)}
    `;
  }

  // Expose fly-to helpers for tables & search
  window.flyToBrodmann = (idx) => {
    switchTab('brain3d');
    const ba = ATLAS.brodmann[idx];
    state.layers.pins = true;
    document.getElementById('chk-pins').checked = true;
    applyLayerVisibility();
    flyToMni(ba.mni, `Brodmann Area ${ba.ba} ${ba.region}`);
    renderInspectorBrodmann(idx);
  };
  window.flyToCranial = (idx) => {
    switchTab('brain3d');
    const cn = ATLAS.cranialNerves[idx];
    setRenderMode('xray');
    flyToMni(cn.mni, `${cn.id} ${cn.name} nerve`);
    renderInspectorCranial(idx);
  };
  window.flyToStructure = (key) => {
    switchTab('brain3d');
    const info = ATLAS.structures[key];
    if (!info) return;
    if (['Thalamus', 'BasalGanglia', 'Ventricles', 'CorpusCallosum', 'Vascular', 'WhiteMatter', 'Limbic'].includes(key)) {
      setRenderMode('xray');
    }
    flyToMni(info.mni, info.title);
    renderInspectorStructure(key, info.title, info.mni);
  };

  // ── POPULATE ALL UI CONTROLS, TABLES, PLATES & 13,665-IMAGE VAULT ─────────
  function announce(msg) {
    const el = document.getElementById('srLive');
    if (el) el.textContent = msg;
  }

  function switchTab(tabId) {
    state.activeTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(b => {
      const on = b.dataset.tab === tabId;
      b.classList.toggle('active', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.querySelectorAll('.tab-panel').forEach(p => {
      p.classList.toggle('active', p.id === 'panel-' + tabId);
    });
    if (tabId === 'brain3d') resize3D();
    if (tabId === 'vault' && !vaultInitialized) initVaultTab();
    if (tabId === 'biomechanics' && window.__DOROTHY_BIOMECH && window.__DOROTHY_BIOMECH.initTab) window.__DOROTHY_BIOMECH.initTab();
  }
  window.switchTab = switchTab;

  // Bind top tabs
  document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

  // Bind 3D controls
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => setRenderMode(b.dataset.mode)));
  document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => setCameraPreset(b.dataset.preset)));

  document.getElementById('btnAutoOrbit').addEventListener('click', (e) => {
    state.autoOrbit = !state.autoOrbit;
    e.currentTarget.classList.toggle('active', state.autoOrbit);
  });

  document.getElementById('sliderOpacity').addEventListener('input', (e) => {
    const v = parseInt(e.target.value, 10) / 100;
    state.cortexOpacity = v;
    document.getElementById('lblOpacity').textContent = e.target.value + '%';
    if (state.mode === 'tissue') {
      const isTrans = v < 0.99;
      matTissueSSS.uniforms.uOpacity.value = v;
      matTissueSSS.transparent = isTrans;
      matTissueSSS.depthWrite = !isTrans || v > 0.72;
      matTissueSSS.side = isTrans || state.clipEnabled || !state.layers.cortexL || !state.layers.cortexR ? THREE.DoubleSide : THREE.FrontSide;
      matTissueSSS.needsUpdate = true;
      return;
    }
    if (state.mode === 'xray') {
      matFresnelXray.uniforms.uOpacity.value = Math.max(0.05, v);
      return;
    }
    if (state.mode === 'connectome') {
      matFresnelConn.uniforms.uOpacity.value = Math.max(0.05, v);
      return;
    }
    const isTrans = v < 0.99;
    [matCortexL, matCortexR].forEach(m => {
      m.transparent = isTrans;
      m.opacity = v;
      m.depthWrite = !isTrans || v > 0.72;
      m.side = isTrans || state.clipEnabled ? THREE.DoubleSide : THREE.FrontSide;
      m.needsUpdate = true;
    });
  });

  document.getElementById('sliderExplode').addEventListener('input', (e) => {
    const v = parseInt(e.target.value, 10) / 100;
    document.getElementById('lblExplode').textContent = e.target.value + '%';
    applyExplode(v);
  });

  document.getElementById('sliderTau').addEventListener('input', (e) => {
    state.tau = parseInt(e.target.value, 10) / 100;
    document.getElementById('lblTau').textContent = state.tau.toFixed(2);
    if (state.mode === 'continuum') setRenderMode('continuum');
  });

  document.getElementById('chkClip').addEventListener('change', (e) => {
    state.clipEnabled = e.target.checked;
    applyClipping();
  });
  ['clipX', 'clipY', 'clipZ'].forEach((id, i) => {
    document.getElementById(id).addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      document.getElementById('lbl-' + id).textContent = `${val} mm`;
      const m = [...state.mni];
      m[i] = val;
      setMniCoords(m[0], m[1], m[2]);
      if (!state.clipEnabled) {
        state.clipEnabled = true;
        document.getElementById('chkClip').checked = true;
      }
      applyClipping();
    });
  });

  document.getElementById('chkPulses').addEventListener('change', (e) => {
    state.pulsesOn = e.target.checked;
    pulseAgents.forEach(p => { p.mesh.visible = state.pulsesOn; });
  });

  Object.keys(state.layers).forEach(k => {
    const el = document.getElementById('chk-' + k);
    if (el) el.addEventListener('change', () => {
      state.layers[k] = el.checked;
      applyLayerVisibility();
    });
  });

  document.getElementById('btnToggleMri').addEventListener('click', (e) => {
    const strip = document.getElementById('mriStrip');
    const hidden = strip.classList.toggle('collapsed');
    e.currentTarget.textContent = hidden ? 'Show Real MNI152 MRI' : 'Hide MRI Strip';
  });

  // Quick-jump structure pills in right inspector
  const quickKeys = ['Frontal', 'Parietal', 'Temporal', 'Occipital', 'Insula', 'Limbic', 'Cerebellum', 'Brainstem', 'Thalamus', 'BasalGanglia', 'CorpusCallosum', 'Ventricles', 'Vascular', 'CranialNerves', 'WhiteMatter'];
  document.getElementById('quickPills').innerHTML = quickKeys.map(k =>
    `<button type="button" class="qpill" onclick="window.flyToStructure('${k}')">${esc(ATLAS.structures[k].title.split(' (')[0])}</button>`
  ).join('');

  // Quick Brodmann dropdown
  const baSel = document.getElementById('baQuickSelect');
  baSel.innerHTML = '<option value="">Jump to any of 52 Brodmann Areas...</option>' +
    ATLAS.brodmann.map((b, i) => `<option value="${i}">BA ${esc(b.ba)} — ${esc(b.region)}</option>`).join('');
  baSel.addEventListener('change', () => {
    if (baSel.value !== '') window.flyToBrodmann(parseInt(baSel.value, 10));
  });

  // ── TAB 2: VERIFIED PLATES & ULTRA-HD POSTER ──────────────────────────────
  const platesGrid = document.getElementById('platesGrid');
  platesGrid.innerHTML = ATLAS.plates.map(p => `
    <article class="plate-card" data-search="${esc((p.title + ' ' + p.cat + ' ' + p.desc).toLowerCase())}">
      <div class="plate-img-wrap" data-lb-src="plates/${esc(p.file)}" data-lb-title="${esc(p.title)}" data-lb-desc="${esc(p.desc)}">
        <img src="plates/${esc(p.file)}" alt="${esc(p.title)}" loading="lazy"/>
      </div>
      <div class="plate-meta">
        <span class="pill-cat">${esc(p.cat)}</span>
        <h3>${esc(p.title)}</h3>
        <p>${esc(p.desc)}</p>
        <div class="credit">${esc(p.credit)}</div>
      </div>
    </article>`).join('');

  // ── TAB 3: COMPLETE NEUROANATOMY ENCYCLOPEDIA ─────────────────────────────
  document.getElementById('tblBrodmann').innerHTML = ATLAS.brodmann.map((b, i) => `
    <tr data-search="${esc(('ba ' + b.ba + ' ' + b.lobe + ' ' + b.region + ' ' + b.desc).toLowerCase())}">
      <td><strong>BA ${esc(b.ba)}</strong></td>
      <td>${esc(b.lobe)}</td>
      <td>${esc(b.region)}</td>
      <td><code>${b.mni.join(', ')}</code></td>
      <td>${esc(b.desc)}</td>
      <td><button type="button" class="btn-sm" onclick="window.flyToBrodmann(${i})">Fly to 3D</button></td>
    </tr>`).join('');

  document.getElementById('tblCranial').innerHTML = ATLAS.cranialNerves.map((c, i) => `
    <tr data-search="${esc((c.id + ' ' + c.name + ' ' + c.modality + ' ' + c.origin + ' ' + c.foramen + ' ' + c.fn).toLowerCase())}">
      <td><strong>${esc(c.id)}</strong></td>
      <td>${esc(c.name)}</td>
      <td>${esc(c.modality)}</td>
      <td>${esc(c.origin)}</td>
      <td>${esc(c.foramen)}</td>
      <td>${esc(c.fn)}</td>
      <td><button type="button" class="btn-sm" onclick="window.flyToCranial(${i})">Fly to 3D</button></td>
    </tr>`).join('');

  document.getElementById('tblTracts').innerHTML = ATLAS.tracts.map(t => `
    <tr data-search="${esc((t.name + ' ' + t.cls + ' ' + t.connects + ' ' + t.fn).toLowerCase())}">
      <td><span class="swatch" style="background:${t.color}"></span><strong>${esc(t.name)}</strong></td>
      <td>${esc(t.cls)} · ${esc(t.dir)}</td>
      <td>${esc(t.connects)}</td>
      <td>${esc(t.fn)}</td>
    </tr>`).join('');

  document.getElementById('tblVascular').innerHTML = ATLAS.vascular.map(v => `
    <tr><td><strong>${esc(v.name)}</strong></td><td>${esc(v.src)}</td><td>${esc(v.territory)}</td><td>${esc(v.clinical)}</td></tr>`).join('');

  document.getElementById('tblModulators').innerHTML = ATLAS.neuromodulators.map(n => `
    <tr><td><strong>${esc(n.name)}</strong></td><td>${esc(n.origins)}</td><td>${esc(n.pathways)}</td></tr>`).join('');

  document.getElementById('tblLayers').innerHTML = ATLAS.corticalLayers.map(l => `
    <tr><td><strong>Layer ${esc(l.layer)}</strong></td><td>${esc(l.name)}</td><td>${esc(l.cells)}</td><td>${esc(l.io)}</td></tr>`).join('');

  // ── TAB 4: DOROTHY LIBRARY + 13,665-IMAGE VIRTUAL VAULT + CAD EXPORTS ─────
  let vaultInitialized = false;
  let vaultFiltered = [];
  let vaultPage = 0;
  const PAGE_SIZE = 48;

  function initVaultTab() {
    vaultInitialized = true;
    if (!document.getElementById('cadGrid')) return;
    // CAD 3D model export cards (.OBJ + .PLY + .STL + Blender 5 Python importer!)
    document.getElementById('cadGrid').innerHTML = ATLAS.cadModels.map(m => `
      <div class="cad-card">
        <strong>${esc(m.name)}</strong>
        <div class="meta">${m.verts.toLocaleString()} vertices · ${m.faces.toLocaleString()} faces (MNI152 mm)</div>
        <div class="cad-links">
          <a href="${esc(m.file)}" download>.OBJ</a>
          <a href="${esc(m.ply)}" download>.PLY</a>
          ${m.stl ? `<a href="${esc(m.stl)}" download>.STL (3D Print)</a>` : ''}
        </div>
      </div>`).join('') + (ATLAS.blenderScript ? `
      <div class="cad-card" style="border-color:#f5d078;">
        <strong>Blender 4 / 5 Auto-Importer Script</strong>
        <div class="meta">Loads all 5 MNI152 anatomical meshes with PBR materials at true mm scale</div>
        <div class="cad-links"><a href="${esc(ATLAS.blenderScript)}" download>Download import_dorothy_brain.py</a></div>
      </div>` : '');

    // Books table
    const doneBooks = VAULT.books.filter(b => b.ch > 0);
    document.getElementById('vaultBookCount').textContent = `${doneBooks.length} downloaded / ${VAULT.books.length} total`;
    document.getElementById('tblBooks').innerHTML = VAULT.books.map(b => `
      <tr data-pillar="${esc(b.pillar)}" data-search="${esc((b.title + ' ' + b.pub + ' ' + b.isbn + ' ' + b.pillar + ' ' + b.status).toLowerCase())}">
        <td><code>${esc(b.pillar)}</code></td>
        <td><strong>${esc(b.title)}</strong></td>
        <td>${esc(b.year)}</td>
        <td>${esc(b.pub)}</td>
        <td>${b.ch}</td>
        <td>${b.img}</td>
        <td><span class="st st-${b.status}">${esc(b.status)}</span></td>
        <td>${b.href ? `<a href="${esc(b.href)}" target="_blank" rel="noopener">Open</a>` : '—'}</td>
      </tr>`).join('');

    // NIRMT PDFs list
    document.getElementById('nirmtCount').textContent = `${VAULT.nirmtPdfs.length} verified PDFs`;
    document.getElementById('nirmtGrid').innerHTML = VAULT.nirmtPdfs.map(p => `
      <a class="pdf-chip" href="${encodeURI(p.file)}" target="_blank" rel="noopener">
        <span>${esc(p.label)}</span><small>${p.mb} MB</small>
      </a>`).join('');

    // Pillar select for Figure Vault
    const sel = document.getElementById('vaultPillar');
    sel.innerHTML = `<option value="-1">All 6 Pillars (${VAULT.images.length.toLocaleString()} figures)</option>` +
      VAULT.pillars.map((p, i) => {
        const cnt = VAULT.images.filter(x => x[0] === i).length;
        return `<option value="${i}">${esc(VAULT.pillarLabels[p])} (${cnt.toLocaleString()})</option>`;
      }).join('');

    document.getElementById('vaultPillar').addEventListener('change', () => { vaultPage = 0; filterVaultImages(); });
    document.getElementById('vaultImgSearch').addEventListener('input', () => { vaultPage = 0; filterVaultImages(); });
    document.getElementById('btnVaultPrev').addEventListener('click', () => { if (vaultPage > 0) { vaultPage--; renderVaultPage(); } });
    document.getElementById('btnVaultNext').addEventListener('click', () => { if ((vaultPage + 1) * PAGE_SIZE < vaultFiltered.length) { vaultPage++; renderVaultPage(); } });
    document.getElementById('bookSearch').addEventListener('input', filterBooks);
    document.getElementById('bookPillar').addEventListener('change', filterBooks);

    // Local 5,951-chapter search across all 135 books (Desktop full edition only)
    const chSec = document.getElementById('chapterSearchSec');
    const CHAPS = window.DOROTHY_CHAPTERS || [];
    if (chSec && CHAPS.length && !VAULT.publicEdition) {
      chSec.style.display = 'block';
      document.getElementById('chapterCount').textContent = `${CHAPS.length.toLocaleString()} indexed chapters across ${VAULT.books.length} books`;
      const renderChaps = (q) => {
        const resEl = document.getElementById('chapterResults');
        const ql = (q || '').trim().toLowerCase();
        if (!ql) {
          resEl.innerHTML = '<div style="grid-column:1/-1;color:#93a4be;font-size:0.82rem;">Type any topic above (e.g. <code>fresnel</code>, <code>papez</code>, <code>broca</code>, <code>elastography</code>, <code>blender</code>, <code>autocad</code>, <code>textile</code>) to search all 5,951 local textbook chapters.</div>';
          return;
        }
        const matches = [];
        for (let i = 0; i < CHAPS.length && matches.length < 36; i++) {
          const c = CHAPS[i];
          const b = VAULT.books[c[0]];
          if (c[1].toLowerCase().includes(ql) || (b && b.title.toLowerCase().includes(ql))) {
            matches.push({ title: c[1], book: b ? b.title : '', href: c[2] });
          }
        }
        resEl.innerHTML = matches.length
          ? matches.map(m => `<a class="pdf-chip" href="${encodeURI(m.href)}" target="_blank" rel="noopener"><span><strong>${esc(m.title)}</strong><br/><span style="color:#93a4be;font-size:0.72rem;">${esc(m.book)}</span></span><small>Open</small></a>`).join('')
          : '<div style="grid-column:1/-1;color:#93a4be;font-size:0.82rem;">No matching chapters found.</div>';
      };
      renderChaps('');
      document.getElementById('chapterSearch').addEventListener('input', (e) => renderChaps(e.target.value));
    }

    filterVaultImages();
  }

  function filterBooks() {
    const q = document.getElementById('bookSearch').value.trim().toLowerCase();
    const p = document.getElementById('bookPillar').value;
    document.querySelectorAll('#tblBooks tr').forEach(tr => {
      const ok = (!q || tr.dataset.search.includes(q)) && (!p || tr.dataset.pillar === p);
      tr.style.display = ok ? '' : 'none';
    });
  }

  function filterVaultImages() {
    const pIdx = parseInt(document.getElementById('vaultPillar').value, 10);
    const q = document.getElementById('vaultImgSearch').value.trim().toLowerCase();
    vaultFiltered = VAULT.images.filter(rec => {
      if (pIdx >= 0 && rec[0] !== pIdx) return false;
      if (!q) return true;
      const slug = VAULT.slugs[rec[1]];
      return slug.includes(q) || rec[2].toLowerCase().includes(q);
    });
    renderVaultPage();
  }

  function renderVaultPage() {
    const start = vaultPage * PAGE_SIZE;
    const slice = vaultFiltered.slice(start, start + PAGE_SIZE);
    const totalPages = Math.max(1, Math.ceil(vaultFiltered.length / PAGE_SIZE));
    document.getElementById('vaultPageInfo').textContent =
      `Showing ${vaultFiltered.length ? start + 1 : 0}–${Math.min(start + PAGE_SIZE, vaultFiltered.length)} of ${vaultFiltered.length.toLocaleString()} figures (Page ${vaultPage + 1} / ${totalPages})`;
    if (VAULT.publicEdition && !vaultFiltered.length) {
      document.getElementById('vaultPageInfo').textContent = 'Public repository edition (licensed publisher figures stay local only)';
      document.getElementById('vaultGrid').innerHTML = '<div style="grid-column:1/-1;background:#101b2d;border:1px solid #223049;border-radius:10px;padding:16px;color:#93a4be;font-size:0.86rem;"><strong style="color:#f5d078;display:block;margin-bottom:4px;">Public Open-Source Edition</strong>Third-party copyrighted O\'Reilly book figures and PDFs are intentionally excluded from this public GitHub repository. All 25 open-license anatomical plates, the 4800×3200 wall-chart poster, real MNI152 T1-MRI slices, all 15 MNI152/AAL-116/CIT168 .OBJ/.PLY/.STL 3D-print meshes, and the Blender 4/5 auto-importer script are included directly in this repo, and the bibliographic reading list below links straight to official publisher pages.</div>';
      return;
    }
    document.getElementById('vaultGrid').innerHTML = slice.map(rec => {
      const pName = VAULT.pillars[rec[0]];
      const slug = VAULT.slugs[rec[1]];
      const orig = rec[2];
      const src = `library_images/${pName}/${slug}__${orig}`;
      const niceBook = slug.replace(/-\d{10,13}$/, '').replace(/-/g, ' ');
      return `<button type="button" class="fig-tile" data-lb-src="${esc(src)}" data-lb-title="${esc(niceBook)}" data-lb-desc="${esc(VAULT.pillarLabels[pName])} · ${esc(orig)}">
        <img src="${esc(src)}" alt="${esc(niceBook + ' figure ' + orig)}" loading="lazy"/>
        <span>${esc(niceBook)}</span>
      </button>`;
    }).join('');
  }

  // ── GLOBAL HEADER SEARCH ──────────────────────────────────────────────────
  const gSearch = document.getElementById('globalSearch');
  const gDrop = document.getElementById('globalResults');
  gSearch.addEventListener('input', () => {
    const q = gSearch.value.trim().toLowerCase();
    if (!q) { gDrop.style.display = 'none'; return; }
    const hits = [];
    ATLAS.brodmann.forEach((b, i) => {
      if ((`ba ${b.ba} ${b.region} ${b.lobe} ${b.desc}`).toLowerCase().includes(q)) {
        hits.push({ label: `BA ${b.ba}: ${b.region}`, sub: `${b.lobe} Lobe · Fly to 3D`, fn: () => window.flyToBrodmann(i) });
      }
    });
    ATLAS.cranialNerves.forEach((c, i) => {
      if ((`${c.id} ${c.name} ${c.origin} ${c.fn}`).toLowerCase().includes(q)) {
        hits.push({ label: `${c.id}: ${c.name} Nerve`, sub: `${c.modality} · Fly to 3D`, fn: () => window.flyToCranial(i) });
      }
    });
    Object.entries(ATLAS.structures).forEach(([k, s]) => {
      if ((`${s.title} ${s.sys} ${s.summary}`).toLowerCase().includes(q)) {
        hits.push({ label: s.title, sub: `${s.sys} · Fly to 3D`, fn: () => window.flyToStructure(k) });
      }
    });
    VAULT.books.forEach(b => {
      if (b.ch > 0 && (`${b.title} ${b.pub}`).toLowerCase().includes(q)) {
        hits.push({ label: b.title, sub: `Dorothy Library (${b.img} imgs)`, fn: () => { switchTab('vault'); document.getElementById('bookSearch').value = b.title.slice(0, 24); filterBooks(); } });
      }
    });
    if (!hits.length) {
      gDrop.innerHTML = '<div class="g-empty">No matching structures or books</div>';
    } else {
      gDrop.innerHTML = hits.slice(0, 10).map((h, idx) =>
        `<button type="button" class="g-item" data-hi="${idx}"><strong>${esc(h.label)}</strong><span>${esc(h.sub)}</span></button>`
      ).join('');
      gDrop.querySelectorAll('.g-item').forEach(btn => {
        btn.addEventListener('click', () => {
          hits[parseInt(btn.dataset.hi, 10)].fn();
          gDrop.style.display = 'none';
          gSearch.value = '';
        });
      });
    }
    gDrop.style.display = 'block';
  });
  document.addEventListener('click', (e) => {
    if (!gDrop.contains(e.target) && e.target !== gSearch) gDrop.style.display = 'none';
  });

  // ── ACCESSIBLE LIGHTBOX (with keyboard focus restoration) ─────────────────
  let lastFocusedEl = null;
  window.openLightbox = (src, title, desc) => {
    lastFocusedEl = document.activeElement;
    const lb = document.getElementById('lightbox');
    const img = document.getElementById('lb-img');
    img.src = src;
    img.alt = title + ': ' + desc;
    document.getElementById('lb-title').textContent = title;
    document.getElementById('lb-desc').textContent = desc;
    lb.setAttribute('aria-hidden', 'false');
    lb.classList.add('open');
    document.getElementById('lb-close').focus();
  };
  window.closeLightbox = () => {
    const lb = document.getElementById('lightbox');
    if (!lb.classList.contains('open')) return;
    lb.classList.remove('open');
    lb.setAttribute('aria-hidden', 'true');
    document.getElementById('lb-img').removeAttribute('src');
    if (lastFocusedEl && typeof lastFocusedEl.focus === 'function') lastFocusedEl.focus();
  };
  document.getElementById('lightbox').addEventListener('click', e => { if (e.target.id === 'lightbox') window.closeLightbox(); });
  document.addEventListener('click', (e) => {
    const el = e.target && e.target.closest ? e.target.closest('[data-lb-src]') : null;
    if (el) {
      window.openLightbox(el.dataset.lbSrc, el.dataset.lbTitle || '', el.dataset.lbDesc || '');
    }
  });

  // ── FLOATING 3D CALLOUT LABELS + GUIDED TOUR + PNG SNAPSHOT ───────────────
  const CALLOUT_DEFS = [
    { key: 'Frontal',        label: 'Frontal Lobe',    group: 'cortexL',    mni: [-44, 42, 32] },
    { key: 'Parietal',       label: 'Parietal Lobe',   group: 'cortexL',    mni: [-44, -50, 56] },
    { key: 'Temporal',       label: 'Temporal Lobe',   group: 'cortexL',    mni: [-62, -22, -14] },
    { key: 'Occipital',      label: 'Occipital Lobe',  group: 'cortexR',    mni: [26, -96, 8] },
    { key: 'Cerebellum',     label: 'Cerebellum',      group: 'cerebellum', mni: [0, -70, -34] },
    { key: 'Brainstem',      label: 'Brainstem',       group: 'brainstem',  mni: [0, -26, -46] },
    { key: 'CorpusCallosum', label: 'Corpus Callosum', group: 'callosum',   mni: [0, 6, 30] },
    { key: 'Thalamus',       label: 'Thalamus',        group: 'thalamus',   mni: [-14, -20, 8] },
    { key: 'BasalGanglia',   label: 'Basal Ganglia',   group: 'cit168',     mni: [24, 2, 0] },
    { key: 'Limbic',         label: 'Hippocampus',     group: 'limbic',     mni: [-28, -24, -14] },
    { key: 'Ventricles',     label: 'Ventricles',      group: 'ventricles', mni: [14, -10, 22] },
    { key: 'Vascular',       label: 'Circle of Willis',group: 'vascular',   mni: [0, 4, -18] },
    { key: 'CranialNerves',  label: 'Cranial Nerves',  group: 'cranial',    mni: [-18, -22, -32] },
  ];
  let showCallouts = false;
  const calloutLayer = document.getElementById('calloutLayer');
  const calloutNodes = CALLOUT_DEFS.map(def => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'callout-pill';
    btn.textContent = def.label;
    btn.addEventListener('click', () => window.flyToStructure(def.key));
    calloutLayer.appendChild(btn);
    return { def, el: btn, basePos: mniToThree(def.mni[0], def.mni[1], def.mni[2]), tmp: new THREE.Vector3() };
  });

  function updateCallouts() {
    if (!showCallouts || state.activeTab !== 'brain3d') {
      calloutLayer.style.display = 'none';
      return;
    }
    calloutLayer.style.display = 'block';
    const w = container.clientWidth || 900;
    const h = container.clientHeight || 600;
    for (const c of calloutNodes) {
      const grp = groups[c.def.group];
      if (!grp || !grp.visible) { c.el.style.display = 'none'; continue; }
      c.tmp.copy(c.basePos).add(grp.position);
      c.tmp.project(camera);
      if (c.tmp.z > 1.0 || c.tmp.x < -0.96 || c.tmp.x > 0.96 || c.tmp.y < -0.92 || c.tmp.y > 0.92) {
        c.el.style.display = 'none';
        continue;
      }
      c.el.style.display = 'block';
      c.el.style.transform = `translate(${((c.tmp.x * 0.5 + 0.5) * w).toFixed(1)}px, ${((-c.tmp.y * 0.5 + 0.5) * h).toFixed(1)}px) translate(-50%, -50%)`;
    }
  }

  document.getElementById('btnLabels3D').addEventListener('click', (e) => {
    showCallouts = !showCallouts;
    e.currentTarget.classList.toggle('active', showCallouts);
    updateCallouts();
  });

  document.querySelectorAll('[data-slice]').forEach(b => b.addEventListener('click', () => setSlicePreset(b.dataset.slice)));
  document.querySelectorAll('[data-circuit]').forEach(b => b.addEventListener('click', () => {
    const cid = b.dataset.circuit;
    setFunctionalCircuit(state.activeCircuit === cid ? '' : cid);
  }));
  document.querySelectorAll('[data-vasc]').forEach(b => b.addEventListener('click', () => {
    const vid = b.dataset.vasc;
    setVascularTerritory(state.activeVasc === vid ? '' : vid);
  }));
  document.querySelectorAll('[data-mricmap]').forEach(b => b.addEventListener('click', () => setMriColormap(b.dataset.mricmap)));
  const btnMeas = document.getElementById('btnMeasure');
  if (btnMeas) btnMeas.addEventListener('click', (e) => {
    state.measureMode = !state.measureMode;
    e.currentTarget.classList.toggle('active', state.measureMode);
    if (!state.measureMode) clearCaliper();
    else {
      const badge = document.getElementById('caliperBadge');
      if (badge) {
        badge.textContent = 'CAD Stereotaxic Caliper ON — click any 2 points on the 3D brain to measure mm';
        badge.style.display = 'block';
      }
    }
  });

  // 1-Click PNG Snapshot Download
  const btnSnap = document.getElementById('btnSnapshot');
  if (btnSnap) btnSnap.addEventListener('click', () => {
    renderer.render(scene, camera);
    const a = document.createElement('a');
    a.download = `dorothy-brain-${state.mode}.png`;
    a.href = renderer.domElement.toDataURL('image/png');
    a.click();
    announce('Saved 3D brain snapshot PNG');
  });

  // 1-Click Guided 6-Stop Brain Tour
  const TOUR_STOPS = [
    { title: '1/6 · ICBM152 Cerebral Cortex', note: 'Real human gyri & sulci with authentic FreeSurfer curvature shading.', run: () => { setSlicePreset('reset'); applyExplode(0); setRenderMode('tissue'); setCameraPreset('hero'); renderInspectorStructure('Frontal'); } },
    { title: '2/6 · Cortical Lobe Atlas', note: 'AAL-116 functional lobes: Frontal, Parietal, Temporal, Occipital, Insula & Limbic.', run: () => { setRenderMode('lobe'); setCameraPreset('left'); renderInspectorStructure('Parietal'); } },
    { title: '3/6 · Glass X-Ray Deep Subcortical Nuclei', note: 'Real Pauli CIT168 nuclei, AAL Thalamus, Ventricles, Circle of Willis & streaming DTI tracts.', run: () => { setRenderMode('xray'); setCameraPreset('deep'); renderInspectorStructure('BasalGanglia'); } },
    { title: '4/6 · Exploded Anatomical Dissection', note: 'All 12 neural subsystems cleanly separated in stereotaxic 3D space.', run: () => { setCameraPreset('hero'); setRenderMode('lobe'); applyExplode(0.65); showCallouts = true; document.getElementById('btnLabels3D').classList.add('active'); renderInspectorStructure('CorpusCallosum'); } },
    { title: '5/6 · Ventral Cranial Nerves I–XII & Circle of Willis', note: 'All 12 cranial nerve roots (CN IV dorsal exit) and the cerebral arterial ring.', run: () => { applyExplode(0); showCallouts = false; document.getElementById('btnLabels3D').classList.remove('active'); setRenderMode('xray'); setCameraPreset('ventral'); renderInspectorStructure('CranialNerves'); } },
    { title: '6/6 · Midsagittal Dorothy Continuum A_tau(p)', note: 'Operational Metacognition confidence map over the exposed medial hemisphere, pons, medulla & cerebellum.', run: () => { setRenderMode('continuum'); setCameraPreset('sagittal'); renderInspectorStructure('Cerebellum'); } },
  ];
  let tourIdx = -1;
  let tourTimer = null;
  const tourBanner = document.getElementById('tourBanner');

  function runTourStep(idx) {
    tourIdx = idx % TOUR_STOPS.length;
    const stop = TOUR_STOPS[tourIdx];
    stop.run();
    document.getElementById('tourTitle').textContent = stop.title;
    document.getElementById('tourNote').textContent = stop.note;
    tourBanner.style.display = 'flex';
    announce(stop.title + '. ' + stop.note);
  }
  function stopTour() {
    if (tourTimer) { clearInterval(tourTimer); tourTimer = null; }
    tourIdx = -1;
    tourBanner.style.display = 'none';
    document.getElementById('btnTour').classList.remove('active');
    document.getElementById('btnTour').textContent = 'Guided Tour';
  }
  document.getElementById('btnTour').addEventListener('click', (e) => {
    if (tourTimer) { stopTour(); return; }
    e.currentTarget.classList.add('active');
    e.currentTarget.textContent = 'Stop Tour';
    runTourStep(0);
    tourTimer = setInterval(() => runTourStep(tourIdx + 1), 5200);
  });
  document.getElementById('btnTourNext').addEventListener('click', () => {
    if (tourTimer) { clearInterval(tourTimer); tourTimer = setInterval(() => runTourStep(tourIdx + 1), 5200); }
    runTourStep(tourIdx + 1);
  });
  document.getElementById('btnTourStop').addEventListener('click', stopTour);

  // ── RESIZE & ANIMATION LOOP ───────────────────────────────────────────────
  function resize3D() {
    const w = container.clientWidth || 900;
    const h = container.clientHeight || 620;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener('resize', resize3D);

  const clock = new THREE.Clock();
  function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    if (state.autoOrbit && !camState.dragging) {
      camState.goalYaw += dt * 0.28;
    }
    updateCameraTransform(false);

    // Subtle pulsing on arterial network & selection beacon
    if (beaconGroup.visible) {
      const s = 1.0 + 0.22 * Math.sin(t * 5.0);
      beaconRing.scale.set(s, s, 1);
    }
    if (state.pulsesOn && gTracts.visible) {
      for (const p of pulseAgents) {
        p.t = (p.t + dt * p.speed * state.pulseSpeed) % 1.0;
        p.curve.getPointAt(p.t, p.mesh.position);
      }
    }
    if (gVascular.visible) {
      const pulse = 0.35 + 0.22 * Math.sin(t * 4.2);
      for (const am of arteryMeshes) am.material.emissiveIntensity = pulse;
    }
    if (circuitPulses.length) {
      for (const cp of circuitPulses) {
        cp.t = (cp.t + dt * 0.22) % 1.0;
        cp.curve.getPointAt(cp.t, cp.mesh.position);
      }
    }
    // Live synthetic EEG / neural oscillation trace when an EEG sensor or Circuit is inspected
    const oscCvs = document.getElementById('eegOsc');
    if (oscCvs) {
      const octx = oscCvs.getContext('2d');
      const W = oscCvs.width, H = oscCvs.height;
      octx.fillStyle = '#060c16'; octx.fillRect(0, 0, W, H);
      octx.strokeStyle = '#182438'; octx.lineWidth = 1;
      octx.beginPath(); octx.moveTo(0, H/2); octx.lineTo(W, H/2); octx.stroke();
      octx.strokeStyle = '#38bdf8'; octx.lineWidth = 1.6;
      octx.beginPath();
      for (let x = 0; x < W; x++) {
        const ph = (x * 0.065) - t * 4.2 + oscSeed;
        const y = H/2 + Math.sin(ph) * 14 + Math.sin(ph * 2.7 + oscSeed) * 8 + Math.sin(ph * 6.3) * 4;
        if (x === 0) octx.moveTo(x, y); else octx.lineTo(x, y);
      }
      octx.stroke();
    }

    if (window.__DOROTHY_BIOMECH && window.__DOROTHY_BIOMECH.tick) {
      window.__DOROTHY_BIOMECH.tick(dt, t);
    }

    renderer.render(scene, camera);
    updateCallouts();
    drawCompass();
  }

  // Live 3D Anatomical Orientation Compass (A/P/L/R/S/I)
  const compassCvs = document.getElementById('compass3d');
  const compassAxes = [
    { v: new THREE.Vector3(0, 0, 1),  lbl: 'A', col: '#f5d078' },  // Anterior (+Z)
    { v: new THREE.Vector3(0, 0, -1), lbl: 'P', col: '#94a3b8' },  // Posterior (-Z)
    { v: new THREE.Vector3(1, 0, 0),  lbl: 'L', col: '#38bdf8' },  // Left (+X)
    { v: new THREE.Vector3(-1, 0, 0), lbl: 'R', col: '#fb7185' },  // Right (-X)
    { v: new THREE.Vector3(0, 1, 0),  lbl: 'S', col: '#34d399' },  // Superior (+Y)
    { v: new THREE.Vector3(0, -1, 0), lbl: 'I', col: '#64748b' },  // Inferior (-Y)
  ];
  const invQuat = new THREE.Quaternion();
  const tmpAxis = new THREE.Vector3();
  function drawCompass() {
    if (!compassCvs || state.activeTab !== 'brain3d') return;
    const ctx = compassCvs.getContext('2d');
    const W = compassCvs.width, H = compassCvs.height, cx = W / 2, cy = H / 2, R = 24;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(7,11,18,0.72)';
    ctx.beginPath(); ctx.arc(cx, cy, 34, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(56,189,248,0.28)'; ctx.lineWidth = 1; ctx.stroke();
    invQuat.copy(camera.quaternion).invert();
    const pts = compassAxes.map(a => {
      tmpAxis.copy(a.v).applyQuaternion(invQuat);
      return { x: cx + tmpAxis.x * R, y: cy - tmpAxis.y * R, z: tmpAxis.z, lbl: a.lbl, col: a.col };
    }).sort((a, b) => a.z - b.z);
    for (const p of pts) {
      ctx.strokeStyle = p.col; ctx.globalAlpha = p.z < 0 ? 0.45 : 0.95; ctx.lineWidth = p.z < 0 ? 1.2 : 2;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(p.x, p.y); ctx.stroke();
      ctx.fillStyle = p.col; ctx.font = 'bold 10px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(p.lbl, cx + (p.x - cx) * 1.28, cy + (p.y - cy) * 1.28);
    }
    ctx.globalAlpha = 1;
  }

  // Live sync dynamic figure counts in header & vault headings
  {
    const figCnt = (VAULT.images || []).length;
    const brandSub = document.getElementById('brandSub');
    if (brandSub) {
      brandSub.textContent = VAULT.publicEdition
        ? 'MNI152 3D Brain · Real T1-MRI · 10–20 EEG Cap · 5 Circuits · .STL/Blender 5 · Dorothy A_tau(p)'
        : `MNI152 3D Brain · Real T1-MRI · 25 Verified Plates · ${figCnt.toLocaleString()} Research Figures`;
    }
    const vaultTitle = document.getElementById('vaultTitle');
    if (vaultTitle) {
      vaultTitle.textContent = VAULT.publicEdition
        ? 'Dorothy Brain Library, CAD / 3D-Print Exports & Open-Source Catalog'
        : `Dorothy Brain Library, CAD / 3D-Print Exports & ${figCnt.toLocaleString()}-Figure Vault`;
    }
    const vaultFigH = document.getElementById('vaultFiguresHeading');
    if (vaultFigH) {
      vaultFigH.textContent = VAULT.publicEdition
        ? 'Research Figure Vault & Bibliographic Catalog'
        : `Searchable ${figCnt.toLocaleString()}-Figure Research Image Vault`;
    }
    const vaultSearch = document.getElementById('vaultImgSearch');
    if (vaultSearch && !VAULT.publicEdition) {
      vaultSearch.placeholder = `Search ${figCnt.toLocaleString()} figures by book title (e.g. cerebellum, vulkan, autocad, blender, mri, textile)...`;
    }
  }

  // Initial boot
  resize3D();
  updateCameraTransform(true);
  setMniCoords(0, -14, 6);
  renderInspectorStructure('Frontal');
  setRenderMode('tissue');
  animate();

  // Expose verification & biomechanics extension API on window
  window.__DOROTHY_API = { setRenderMode, setCameraPreset, applyExplode, setSlicePreset, setFunctionalCircuit, setVascularTerritory, setMriColormap, switchTab, updateCameraTransform, setCallouts: (v) => { showCallouts = !!v; document.getElementById('btnLabels3D').classList.toggle('active', showCallouts); updateCallouts(); }, setEegCap: (v) => { state.layers.eegCap = !!v; document.getElementById('chk-eegCap').checked = !!v; applyLayerVisibility(); }, flyToBrodmann: window.flyToBrodmann, flyToStructure: window.flyToStructure, state, geoL, geoR, meshCortexL, meshCortexR, matCortexL, matCortexR, curvBytes, aalLBytes, lobeLBytes, aalRBytes, lobeRBytes, brainRoot, activeClipPlanes, applyClipping, setMniCoords, mniToThree };
})();
