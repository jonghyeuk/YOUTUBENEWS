import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar } from 'recharts';
import * as THREE from 'three';

// ============================================================
// SiliconEtchingSimulator Component (Three.js 3D Simulator)
// ============================================================


const SiliconEtchingSimulator = () => {
  const [gasType, setGasType] = useState('fluorine');
  const [isRunning, setIsRunning] = useState(false);
  const [etchDepth, setEtchDepth] = useState(0);
  const [particleCount, setParticleCount] = useState(0);
  const [dissociationCount, setDissociationCount] = useState(0);
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const frameId = useRef(null);
  const gasMoleculesRef = useRef([]);
  const radicalsRef = useRef([]);
  const byproductsRef = useRef([]);
  const siliconRef = useRef(null);
  const plasmaZoneRef = useRef(null);
  const timeRef = useRef(0);
  const isRunningRef = useRef(false);
  const dissociatingMoleculesRef = useRef([]); // 분해 중인 분자들
  const gasTypeRef = useRef(gasType); // gasType을 ref로도 추적
  const siAtomsRef = useRef([]); // Si 원자 배열 추적

  const gasProperties = {
    fluorine: {
      name: 'SF₆ (육불화황)',
      moleculeColor: 0x99cc66, // 황록색
      radicalColor: 0x66ff66, // 밝은 녹색 라디칼
      radical: 'F*',
      radicalCount: 6, // SF6 → 6F
      speed: 0.12,
      reactivity: 0.9,
      isotropic: true,
      byproduct: 'SiF₄',
      byproductColor: 0x88ffcc,
      dissociationFormula: 'SF₆ → S + 6F*',
      reactionFormula: 'Si(s) + 4F* → SiF₄(g)',
      description: '빠른 등방성 식각, 높은 휘발성',
      structure: 'octahedral' // SF6는 팔면체 구조
    },
    cf4: {
      name: 'CF₄ (사불화탄소)',
      moleculeColor: 0x555555, // 어두운 회색 (탄소)
      radicalColor: 0x66ff66, // 밝은 녹색 라디칼
      radical: 'F*',
      radicalCount: 4, // CF4 → 4F
      speed: 0.10,
      reactivity: 0.75,
      isotropic: true,
      byproduct: 'SiF₄',
      byproductColor: 0x88ffcc,
      dissociationFormula: 'CF₄ → C + 4F*',
      reactionFormula: 'Si(s) + 4F* → SiF₄(g)',
      description: '중간 속도 등방성 식각, 안정적',
      structure: 'tetrahedral' // CF4는 사면체 구조
    },
    chlorine: {
      name: 'Cl₂ (염소)',
      moleculeColor: 0x44dd44, // 녹색 (염소)
      radicalColor: 0x66ff66, // 밝은 녹색 라디칼
      radical: 'Cl*',
      radicalCount: 2, // Cl2 → 2Cl
      speed: 0.06,
      reactivity: 0.6,
      isotropic: false,
      byproduct: 'SiCl₄',
      byproductColor: 0xaaffaa,
      dissociationFormula: 'Cl₂ → 2Cl*',
      reactionFormula: 'Si(s) + 4Cl* → SiCl₄(g)',
      description: '느린 이방성 식각, 수직 방향성',
      structure: 'diatomic' // Cl2는 2원자 분자
    },
    bromine: {
      name: 'HBr (브롬화수소)',
      moleculeColor: 0x8b4513, // 밤색 (브롬)
      radicalColor: 0xaa6633, // 밝은 밤색 라디칼
      radical: 'Br*',
      radicalCount: 1, // HBr → H + Br
      speed: 0.08,
      reactivity: 0.7,
      isotropic: false,
      byproduct: 'SiBr₄',
      byproductColor: 0xddaa77,
      dissociationFormula: 'HBr → H + Br*',
      reactionFormula: 'Si(s) + 4Br* → SiBr₄(g)',
      description: '중간 속도, 깊은 트렌치 식각',
      structure: 'diatomic' // HBr은 2원자 분자
    }
  };

  const initializeScene = () => {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);

    const camera = new THREE.PerspectiveCamera(
      60,
      mountRef.current.clientWidth / mountRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(18, 12, 18);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    mountRef.current.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.3);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.7);
    directionalLight.position.set(10, 15, 5);
    scene.add(directionalLight);

    // Plasma zone (glowing area where dissociation happens)
    const plasmaGeometry = new THREE.CylinderGeometry(5, 5, 3.5, 32); // 웨이퍼보다 약간 작게
    const plasmaMaterial = new THREE.MeshPhongMaterial({
      color: 0x6644ff,
      transparent: true,
      opacity: 0.12, // 투명도 감소
      emissive: 0x6644ff,
      emissiveIntensity: 0.2
    });
    const plasmaZone = new THREE.Mesh(plasmaGeometry, plasmaMaterial);
    plasmaZone.position.y = 4;
    scene.add(plasmaZone);
    plasmaZoneRef.current = plasmaZone;

    // Add plasma glow effect
    const glowGeometry = new THREE.SphereGeometry(6, 32, 32); // 크기 조정
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: 0x8866ff,
      transparent: true,
      opacity: 0.03 // 투명도 감소: 0.05 -> 0.03
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    glow.position.y = 4;
    scene.add(glow);

    // Silicon wafer (원형 웨이퍼)
    const siliconGeometry = new THREE.CylinderGeometry(6, 6, 0.3, 64);
    const siliconMaterial = new THREE.MeshPhongMaterial({
      color: 0x505050,
      shininess: 120,
      specular: 0x888888,
      metalness: 0.3
    });
    const silicon = new THREE.Mesh(siliconGeometry, siliconMaterial);
    silicon.position.y = 0;
    scene.add(silicon);
    siliconRef.current = silicon;

    // Si 원자 격자 배열 (웨이퍼 표면) - 원자들이 서로 붙어있음
    const atomSize = 0.09; // 크기 줄임: 화면 비율 맞추기
    const spacing = 0.18; // 간격: 원자 지름(0.18)과 같게 -> 딱 붙어있음
    const gridSize = 64; // 더 많은 원자로 빽빽하게
    const atomGeometry = new THREE.SphereGeometry(atomSize, 10, 10); // 폴리곤 줄임
    const atomMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888, // 밝은 은색
      emissive: 0x555555,
      emissiveIntensity: 0.2,
      metalness: 0.5,
      shininess: 60
    });

    const atomsGroup = new THREE.Group();
    const siAtoms = []; // Si 원자들을 배열에 저장

    for (let i = -gridSize/2; i <= gridSize/2; i++) {
      for (let j = -gridSize/2; j <= gridSize/2; j++) {
        const x = i * spacing;
        const z = j * spacing;
        const distFromCenter = Math.sqrt(x * x + z * z);

        // 원형 웨이퍼 내부에만 배치
        if (distFromCenter <= 5.8) {
          const atom = new THREE.Mesh(atomGeometry, atomMaterial);
          atom.position.set(x, 0.15, z);
          atom.userData = {
            type: 'siAtom',
            active: true,
            worldPosition: new THREE.Vector3() // 월드 좌표 저장용
          };
          atomsGroup.add(atom);
          siAtoms.push(atom); // 배열에 추가
        }
      }
    }
    silicon.add(atomsGroup);
    siAtomsRef.current = siAtoms; // ref에 저장

    // "Si wafer" 라벨을 위한 스프라이트
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 128;

    // 배경 박스
    context.fillStyle = 'rgba(40, 40, 60, 0.85)';
    context.fillRect(10, 10, 492, 108);

    // 테두리
    context.strokeStyle = 'rgba(100, 150, 255, 0.9)';
    context.lineWidth = 4;
    context.strokeRect(10, 10, 492, 108);

    // 텍스트
    context.fillStyle = '#ffffff';
    context.font = 'Bold 64px Arial';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText('Si wafer', 256, 64);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.position.set(8.5, 0, 0);
    sprite.scale.set(4, 1, 1);
    scene.add(sprite);

    // Chamber walls (transparent)
    const chamberGeometry = new THREE.CylinderGeometry(7, 7, 25, 32, 1, true);
    const chamberMaterial = new THREE.MeshPhongMaterial({
      color: 0x2244aa,
      transparent: true,
      opacity: 0.08,
      side: THREE.DoubleSide
    });
    const chamber = new THREE.Mesh(chamberGeometry, chamberMaterial);
    chamber.position.y = 5;
    scene.add(chamber);

    // Grid helper
    const gridHelper = new THREE.GridHelper(25, 25, 0x333333, 0x1a1a1a);
    gridHelper.position.y = -5;
    scene.add(gridHelper);

    sceneRef.current = scene;
    rendererRef.current = renderer;
    cameraRef.current = camera;

    // Animation loop
    const animate = () => {
      frameId.current = requestAnimationFrame(animate);

      if (isRunningRef.current) {
        updateParticles();
        timeRef.current += 0.016;

        // Rotate silicon wafer
        if (siliconRef.current) {
          siliconRef.current.rotation.y += 0.006; // 원형 웨이퍼에 맞게 약간 느리게
        }

        // Pulse plasma zone
        if (plasmaZoneRef.current) {
          const pulse = Math.sin(timeRef.current * 3) * 0.03 + 0.12; // 펄스 감소
          plasmaZoneRef.current.material.opacity = pulse;
        }
      }

      // Rotate camera
      const time = Date.now() * 0.0001;
      camera.position.x = Math.cos(time) * 18;
      camera.position.z = Math.sin(time) * 18;
      camera.lookAt(0, 2, 0);

      renderer.render(scene, camera);
    };
    animate();
  };

  // Create gas molecule with proper molecular structure
  const createGasMolecule = () => {
    const currentGasType = gasTypeRef.current; // ref에서 최신 값 가져오기
    const props = gasProperties[currentGasType];
    const moleculeGroup = new THREE.Group();

    if (props.structure === 'octahedral') {
      // SF6: 중심에 S(황), 주변에 F(불소) 6개
      // 중심 황 원자 (노란색)
      const sGeometry = new THREE.SphereGeometry(0.20, 16, 16);
      const sMaterial = new THREE.MeshPhongMaterial({
        color: 0xffdd00,
        emissive: 0xccaa00,
        emissiveIntensity: 0.3
      });
      const sulfur = new THREE.Mesh(sGeometry, sMaterial);
      moleculeGroup.add(sulfur);

      // 6개의 불소 원자 (팔면체 꼭짓점) - 밝은 녹색
      const fPositions = [
        [0.4, 0, 0], [-0.4, 0, 0],
        [0, 0.4, 0], [0, -0.4, 0],
        [0, 0, 0.4], [0, 0, -0.4]
      ];

      fPositions.forEach(pos => {
        const fGeometry = new THREE.SphereGeometry(0.12, 12, 12);
        const fMaterial = new THREE.MeshPhongMaterial({
          color: 0x66ff66,
          emissive: 0x44dd44,
          emissiveIntensity: 0.4
        });
        const fluorine = new THREE.Mesh(fGeometry, fMaterial);
        fluorine.position.set(...pos);

        // 결합선
        const bondGeometry = new THREE.CylinderGeometry(0.03, 0.03, 0.4, 8);
        const bondMaterial = new THREE.MeshPhongMaterial({ color: 0xaaaaaa });
        const bond = new THREE.Mesh(bondGeometry, bondMaterial);
        bond.position.set(pos[0]/2, pos[1]/2, pos[2]/2);

        if (pos[0] !== 0) bond.rotation.z = Math.PI / 2;
        if (pos[2] !== 0) bond.rotation.x = Math.PI / 2;

        moleculeGroup.add(fluorine);
        moleculeGroup.add(bond);
      });

    } else if (props.structure === 'tetrahedral') {
      // CF4: 중심에 C(탄소), 주변에 F(불소) 4개 (사면체)
      // 중심 탄소 원자 (어두운 회색/검은색)
      const cGeometry = new THREE.SphereGeometry(0.16, 16, 16);
      const cMaterial = new THREE.MeshPhongMaterial({
        color: 0x2a2a2a, // 어두운 회색
        emissive: 0x1a1a1a,
        emissiveIntensity: 0.2
      });
      const carbon = new THREE.Mesh(cGeometry, cMaterial);
      moleculeGroup.add(carbon);

      // 4개의 불소 원자 (사면체 꼭짓점) - 밝은 녹색
      const fPositions = [
        [0.3, 0.3, 0.3],
        [-0.3, -0.3, 0.3],
        [-0.3, 0.3, -0.3],
        [0.3, -0.3, -0.3]
      ];

      fPositions.forEach(pos => {
        const fGeometry = new THREE.SphereGeometry(0.12, 12, 12);
        const fMaterial = new THREE.MeshPhongMaterial({
          color: 0x66ff66,
          emissive: 0x44dd44,
          emissiveIntensity: 0.4
        });
        const fluorine = new THREE.Mesh(fGeometry, fMaterial);
        fluorine.position.set(...pos);

        // 결합선
        const bondGeometry = new THREE.CylinderGeometry(0.03, 0.03, 0.3, 8);
        const bondMaterial = new THREE.MeshPhongMaterial({ color: 0xaaaaaa });
        const bond = new THREE.Mesh(bondGeometry, bondMaterial);
        bond.position.set(pos[0]/2, pos[1]/2, pos[2]/2);

        // 결합선 방향 조정
        const direction = new THREE.Vector3(...pos).normalize();
        const axis = new THREE.Vector3(0, 1, 0);
        const quaternion = new THREE.Quaternion();
        quaternion.setFromUnitVectors(axis, direction);
        bond.quaternion.copy(quaternion);

        moleculeGroup.add(fluorine);
        moleculeGroup.add(bond);
      });

    } else if (props.structure === 'diatomic') {
      // Cl2 또는 HBr: 2원자 분자

      if (currentGasType === 'chlorine') {
        // Cl2: 두 개의 동일한 녹색 Cl 원자
        const clSize = 0.18;
        const clColor = 0x44dd44; // 녹색

        // 첫 번째 Cl 원자
        const cl1Geometry = new THREE.SphereGeometry(clSize, 16, 16);
        const cl1Material = new THREE.MeshPhongMaterial({
          color: clColor,
          emissive: clColor,
          emissiveIntensity: 0.4
        });
        const cl1 = new THREE.Mesh(cl1Geometry, cl1Material);
        cl1.position.set(-0.25, 0, 0);
        moleculeGroup.add(cl1);

        // 두 번째 Cl 원자
        const cl2Geometry = new THREE.SphereGeometry(clSize, 16, 16);
        const cl2Material = new THREE.MeshPhongMaterial({
          color: clColor,
          emissive: clColor,
          emissiveIntensity: 0.4
        });
        const cl2 = new THREE.Mesh(cl2Geometry, cl2Material);
        cl2.position.set(0.25, 0, 0);
        moleculeGroup.add(cl2);

        // 결합선
        const bondGeometry = new THREE.CylinderGeometry(0.04, 0.04, 0.5, 8);
        const bondMaterial = new THREE.MeshPhongMaterial({ color: 0xcccccc });
        const bond = new THREE.Mesh(bondGeometry, bondMaterial);
        bond.rotation.z = Math.PI / 2;
        moleculeGroup.add(bond);

      } else if (currentGasType === 'bromine') {
        // HBr: H (작고 흰색) + Br (크고 밤색)

        // 수소 원자 (작고 밝은 흰색)
        const hGeometry = new THREE.SphereGeometry(0.10, 16, 16);
        const hMaterial = new THREE.MeshPhongMaterial({
          color: 0xffffff,
          emissive: 0xeeeeee,
          emissiveIntensity: 0.4
        });
        const hydrogen = new THREE.Mesh(hGeometry, hMaterial);
        hydrogen.position.set(-0.22, 0, 0);
        moleculeGroup.add(hydrogen);

        // 브롬 원자 (크고 밤색)
        const brGeometry = new THREE.SphereGeometry(0.18, 16, 16);
        const brMaterial = new THREE.MeshPhongMaterial({
          color: 0x8b4513, // 밤색
          emissive: 0x6b3410,
          emissiveIntensity: 0.3
        });
        const bromine = new THREE.Mesh(brGeometry, brMaterial);
        bromine.position.set(0.22, 0, 0);
        moleculeGroup.add(bromine);

        // 결합선
        const bondGeometry = new THREE.CylinderGeometry(0.03, 0.03, 0.44, 8);
        const bondMaterial = new THREE.MeshPhongMaterial({ color: 0xcccccc });
        const bond = new THREE.Mesh(bondGeometry, bondMaterial);
        bond.rotation.z = Math.PI / 2;
        moleculeGroup.add(bond);
      }
    }

    // Random position above silicon (원형 영역 내)
    const angle = Math.random() * Math.PI * 2;
    const radius = Math.random() * 2.5; // 웨이퍼 반지름보다 작게
    moleculeGroup.position.x = Math.cos(angle) * radius;
    moleculeGroup.position.y = 12 + Math.random() * 3;
    moleculeGroup.position.z = Math.sin(angle) * radius;

    moleculeGroup.userData = {
      velocity: new THREE.Vector3(0, -0.05, 0), // 속도 감소: 0.08 -> 0.05
      type: 'molecule',
      active: true,
      rotationSpeed: {
        x: (Math.random() - 0.5) * 0.03,
        y: (Math.random() - 0.5) * 0.03,
        z: (Math.random() - 0.5) * 0.03
      }
    };

    sceneRef.current.add(moleculeGroup);
    gasMoleculesRef.current.push(moleculeGroup);
  };

  // Dissociate molecule into radicals in plasma zone - with animation
  const startDissociation = (molecule) => {
    const currentGasType = gasTypeRef.current; // ref에서 최신 값 가져오기
    const props = gasProperties[currentGasType];

    molecule.userData.dissociating = true;
    molecule.userData.dissociationProgress = 0;
    molecule.userData.dissociationType = props.structure;
    molecule.userData.gasType = currentGasType; // 분자에 가스 타입 저장

    dissociatingMoleculesRef.current.push(molecule);
  };

  // Complete dissociation and create radicals
  const completeDissociation = (molecule) => {
    const currentGasType = molecule.userData.gasType || gasTypeRef.current; // 저장된 타입 사용
    const props = gasProperties[currentGasType];
    const position = molecule.position.clone();

    if (props.structure === 'octahedral') {
      // SF6 → S + 6F*
      // 1. Create S atom (sulfur byproduct - moves away slowly)
      const sGeometry = new THREE.SphereGeometry(0.14, 16, 16);
      const sMaterial = new THREE.MeshPhongMaterial({
        color: 0xffdd00,
        emissive: 0xccaa00,
        emissiveIntensity: 0.3,
        transparent: true,
        opacity: 0.8
      });
      const sulfur = new THREE.Mesh(sGeometry, sMaterial);
      sulfur.position.copy(position);
      sulfur.userData = {
        velocity: new THREE.Vector3(
          (Math.random() - 0.5) * 0.04, // 수평 움직임
          0.03, // 위로 천천히 배출
          (Math.random() - 0.5) * 0.04
        ),
        type: 'byproduct',
        lifetime: 120 // 더 오래 보임
      };
      sceneRef.current.add(sulfur);
      byproductsRef.current.push(sulfur);

      // 2. Create 6 F* radicals (spread in octahedral directions)
      const fDirections = [
        [1, 0, 0], [-1, 0, 0],
        [0, 1, 0], [0, -1, 0],
        [0, 0, 1], [0, 0, -1]
      ];

      fDirections.forEach((dir, i) => {
        const geometry = new THREE.SphereGeometry(0.10, 12, 12);
        const material = new THREE.MeshPhongMaterial({
          color: props.radicalColor,
          emissive: props.radicalColor,
          emissiveIntensity: 0.7
        });
        const radical = new THREE.Mesh(geometry, material);

        radical.position.copy(position);
        radical.position.x += dir[0] * 0.3;
        radical.position.y += dir[1] * 0.3;
        radical.position.z += dir[2] * 0.3;

        // F* radicals - 초기에 퍼지다가 주로 아래로
        radical.userData = {
          velocity: new THREE.Vector3(
            dir[0] * 0.03, // 수평 퍼짐 감소
            -0.06 + dir[1] * 0.01, // 주로 아래로
            dir[2] * 0.03
          ),
          type: 'radical',
          active: true,
          lifetime: 200
        };

        sceneRef.current.add(radical);
        radicalsRef.current.push(radical);
      });

    } else if (props.structure === 'tetrahedral') {
      // CF4 → C + 4F*
      // 1. Create C atom (carbon byproduct - moves away slowly)
      const cGeometry = new THREE.SphereGeometry(0.12, 16, 16);
      const cMaterial = new THREE.MeshPhongMaterial({
        color: 0x2a2a2a, // 어두운 회색
        emissive: 0x1a1a1a,
        emissiveIntensity: 0.2,
        transparent: true,
        opacity: 0.8
      });
      const carbon = new THREE.Mesh(cGeometry, cMaterial);
      carbon.position.copy(position);
      carbon.userData = {
        velocity: new THREE.Vector3(
          (Math.random() - 0.5) * 0.04, // 수평 움직임
          0.03, // 위로 천천히 배출
          (Math.random() - 0.5) * 0.04
        ),
        type: 'byproduct',
        lifetime: 120 // 더 오래 보임
      };
      sceneRef.current.add(carbon);
      byproductsRef.current.push(carbon);

      // 2. Create 4 F* radicals (spread in tetrahedral directions)
      const fDirections = [
        [1, 1, 1], [-1, -1, 1],
        [-1, 1, -1], [1, -1, -1]
      ];

      fDirections.forEach((dir, i) => {
        const geometry = new THREE.SphereGeometry(0.10, 12, 12);
        const material = new THREE.MeshPhongMaterial({
          color: props.radicalColor,
          emissive: props.radicalColor,
          emissiveIntensity: 0.7
        });
        const radical = new THREE.Mesh(geometry, material);

        // 방향 정규화
        const dirLength = Math.sqrt(dir[0]**2 + dir[1]**2 + dir[2]**2);
        const normDir = dir.map(d => d / dirLength);

        radical.position.copy(position);
        radical.position.x += normDir[0] * 0.3;
        radical.position.y += normDir[1] * 0.3;
        radical.position.z += normDir[2] * 0.3;

        // F* radicals - 초기에 퍼지다가 주로 아래로
        radical.userData = {
          velocity: new THREE.Vector3(
            normDir[0] * 0.03, // 수평 퍼짐
            -0.06 + normDir[1] * 0.01, // 주로 아래로
            normDir[2] * 0.03
          ),
          type: 'radical',
          active: true,
          lifetime: 200
        };

        sceneRef.current.add(radical);
        radicalsRef.current.push(radical);
      });

    } else if (props.structure === 'diatomic') {
      if (currentGasType === 'chlorine') {
        // Cl2 → 2Cl* (녹색 두 개가 각각 분리되어 바닥으로)
        for (let i = 0; i < 2; i++) {
          const geometry = new THREE.SphereGeometry(0.13, 12, 12);
          const material = new THREE.MeshPhongMaterial({
            color: props.radicalColor,
            emissive: props.radicalColor,
            emissiveIntensity: 0.7
          });
          const radical = new THREE.Mesh(geometry, material);

          const direction = i === 0 ? -1 : 1;
          radical.position.copy(position);
          radical.position.x += direction * 0.3;

          // 라디칼이 아래로 떨어짐
          radical.userData = {
            velocity: new THREE.Vector3(
              direction * 0.03, // 약간의 수평 퍼짐
              -0.06, // 주로 아래로
              (Math.random() - 0.5) * 0.02
            ),
            type: 'radical',
            active: true,
            lifetime: 200
          };

          sceneRef.current.add(radical);
          radicalsRef.current.push(radical);
        }

      } else if (currentGasType === 'bromine') {
        // HBr → H + Br* (흰색 H는 배출, 밤색 Br은 아래로)

        // 1. Create H atom (hydrogen - moves away)
        const hGeometry = new THREE.SphereGeometry(0.07, 12, 12);
        const hMaterial = new THREE.MeshPhongMaterial({
          color: 0xffffff,
          emissive: 0xdddddd,
          emissiveIntensity: 0.4,
          transparent: true,
          opacity: 0.85
        });
        const hydrogen = new THREE.Mesh(hGeometry, hMaterial);
        hydrogen.position.copy(position);
        hydrogen.position.x -= 0.25;
        hydrogen.userData = {
          velocity: new THREE.Vector3(
            -0.12, // 왼쪽으로 빠르게 배출
            0.05, // 약간 위로
            (Math.random() - 0.5) * 0.08
          ),
          type: 'byproduct',
          lifetime: 90
        };
        sceneRef.current.add(hydrogen);
        byproductsRef.current.push(hydrogen);

        // 2. Create Br* radical (밤색, 아래로 떨어짐)
        const geometry = new THREE.SphereGeometry(0.13, 12, 12);
        const material = new THREE.MeshPhongMaterial({
          color: props.radicalColor,
          emissive: props.radicalColor,
          emissiveIntensity: 0.7
        });
        const radical = new THREE.Mesh(geometry, material);

        radical.position.copy(position);
        radical.position.x += 0.25;

        // 라디칼이 아래로 떨어짐
        radical.userData = {
          velocity: new THREE.Vector3(
            0.02, // 약간 오른쪽
            -0.06, // 주로 아래로
            (Math.random() - 0.5) * 0.02
          ),
          type: 'radical',
          active: true,
          lifetime: 200
        };

        sceneRef.current.add(radical);
        radicalsRef.current.push(radical);
      }
    }

    setDissociationCount(prev => prev + 1);
  };

  // 가장 가까운 Si 원자 찾기
  const findNearestSiAtom = (position) => {
    let nearestAtom = null;
    let minDistance = Infinity;

    for (const atom of siAtomsRef.current) {
      if (!atom.userData.active) continue; // 이미 제거된 원자는 건너뛰기

      // 월드 좌표 업데이트
      atom.getWorldPosition(atom.userData.worldPosition);
      const worldPos = atom.userData.worldPosition;

      // 2D 거리로 계산 (x, z 평면)
      const distance = Math.sqrt(
        (worldPos.x - position.x) ** 2 +
        (worldPos.z - position.z) ** 2
      );

      if (distance < minDistance) {
        minDistance = distance;
        nearestAtom = atom;
      }
    }

    // 너무 멀면 null 반환 (식각 범위 내에 있어야 함)
    if (minDistance > 0.3) return null;

    return nearestAtom;
  };

  // Create byproduct (SiF4, SiCl4, SiBr4) from surface reaction - Si 원자 제거
  const createByproduct = (position, siAtom = null) => {
    const currentGasType = gasTypeRef.current;
    const props = gasProperties[currentGasType];

    // Si 원자가 지정되면 그 위치에서, 아니면 주어진 위치에서 생성
    let byproductPosition = position.clone();
    if (siAtom && siAtom.userData.active) {
      siAtom.getWorldPosition(siAtom.userData.worldPosition);
      byproductPosition = siAtom.userData.worldPosition.clone();

      // Si 원자 제거 (식각!)
      siAtom.userData.active = false;
      siAtom.visible = false;
    }

    // 부산물 분자 그룹 생성 (중심에 Si, 주변에 4개의 F/Cl/Br)
    const byproductGroup = new THREE.Group();

    // 중심 Si 원자 (진한 회색)
    const siGeometry = new THREE.SphereGeometry(0.09, 12, 12);
    const siMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888, // 밝은 은색
      emissive: 0x555555,
      emissiveIntensity: 0.3
    });
    const siCenter = new THREE.Mesh(siGeometry, siMaterial);
    byproductGroup.add(siCenter);

    // 4개의 F/Cl/Br 원자 (사면체 구조)
    const radicalPositions = [
      [0.15, 0.15, 0.15],
      [-0.15, -0.15, 0.15],
      [-0.15, 0.15, -0.15],
      [0.15, -0.15, -0.15]
    ];

    // 라디칼 색상 결정
    let radicalColor = props.radicalColor;
    if (currentGasType === 'bromine') {
      radicalColor = 0xaa6633; // 밤색 Br
    } else if (currentGasType === 'chlorine') {
      radicalColor = 0x66ff66; // 녹색 Cl
    } else {
      radicalColor = 0x66ff66; // 녹색 F
    }

    radicalPositions.forEach(pos => {
      const radicalGeometry = new THREE.SphereGeometry(0.07, 10, 10);
      const radicalMaterial = new THREE.MeshPhongMaterial({
        color: radicalColor,
        emissive: radicalColor,
        emissiveIntensity: 0.4
      });
      const radical = new THREE.Mesh(radicalGeometry, radicalMaterial);
      radical.position.set(...pos);

      // 결합선
      const bondGeometry = new THREE.CylinderGeometry(0.02, 0.02, 0.15, 6);
      const bondMaterial = new THREE.MeshPhongMaterial({
        color: 0xaaaaaa,
        transparent: true,
        opacity: 0.6
      });
      const bond = new THREE.Mesh(bondGeometry, bondMaterial);
      bond.position.set(pos[0]/2, pos[1]/2, pos[2]/2);

      // 결합선 방향 조정
      const direction = new THREE.Vector3(...pos).normalize();
      const axis = new THREE.Vector3(0, 1, 0);
      const quaternion = new THREE.Quaternion();
      quaternion.setFromUnitVectors(axis, direction);
      bond.quaternion.copy(quaternion);

      byproductGroup.add(radical);
      byproductGroup.add(bond);
    });

    byproductGroup.position.copy(byproductPosition);
    byproductGroup.position.y = Math.max(byproductPosition.y, 0.4);

    byproductGroup.userData = {
      velocity: new THREE.Vector3(
        (Math.random() - 0.5) * 0.05,
        0.10 + Math.random() * 0.05,
        (Math.random() - 0.5) * 0.05
      ),
      rotation: new THREE.Vector3(
        (Math.random() - 0.5) * 0.08,
        (Math.random() - 0.5) * 0.08,
        (Math.random() - 0.5) * 0.08
      ),
      lifetime: 150,
      type: 'byproduct'
    };

    sceneRef.current.add(byproductGroup);
    byproductsRef.current.push(byproductGroup);
    setParticleCount(prev => prev + 1);

    // Create small flash effect at reaction site (Si 원자 위치)
    const flashGeometry = new THREE.SphereGeometry(0.15, 8, 8);
    const flashMaterial = new THREE.MeshBasicMaterial({
      color: 0xffff88,
      transparent: true,
      opacity: 0.5
    });
    const flash = new THREE.Mesh(flashGeometry, flashMaterial);
    flash.position.copy(byproductPosition);
    flash.position.y = Math.max(byproductPosition.y, 0.25);
    sceneRef.current.add(flash);

    // Animate and remove flash
    let flashLife = 10;
    const flashInterval = setInterval(() => {
      flashLife--;
      flash.scale.multiplyScalar(1.2);
      flash.material.opacity = flashLife / 10;
      if (flashLife <= 0) {
        sceneRef.current.remove(flash);
        flash.geometry.dispose();
        flash.material.dispose();
        clearInterval(flashInterval);
      }
    }, 30);
  };

  const updateParticles = () => {
    const currentGasType = gasTypeRef.current; // ref에서 최신 값 가져오기
    const props = gasProperties[currentGasType];

    // Update dissociating molecules (animation)
    for (let i = dissociatingMoleculesRef.current.length - 1; i >= 0; i--) {
      const molecule = dissociatingMoleculesRef.current[i];

      if (!molecule.userData.dissociating) continue;

      molecule.userData.dissociationProgress += 0.018; // 분해 속도 조금 빠르게
      const progress = molecule.userData.dissociationProgress;

      // Animate the dissociation based on gas type
      if (molecule.userData.dissociationType === 'octahedral') {
        // SF6: 불소들이 황에서 멀어지며 아래로
        molecule.children.forEach((child, idx) => {
          if (child.isMesh && idx > 0 && idx % 2 === 1) { // 불소 원자들
            const scale = 1 + progress * 2.5; // 더 멀리 퍼짐
            const originalPos = child.userData.originalPos || child.position.clone();
            if (!child.userData.originalPos) child.userData.originalPos = originalPos.clone();

            child.position.x = originalPos.x * scale;
            child.position.y = originalPos.y * scale - progress * 0.4; // 아래로도 이동
            child.position.z = originalPos.z * scale;
          }
        });

      } else if (molecule.userData.dissociationType === 'tetrahedral') {
        // CF4: 불소들이 탄소에서 멀어지며 아래로 (사면체)
        molecule.children.forEach((child, idx) => {
          if (child.isMesh && idx > 0 && idx % 2 === 1) { // 불소 원자들
            const scale = 1 + progress * 2.5; // 더 멀리 퍼짐
            const originalPos = child.userData.originalPos || child.position.clone();
            if (!child.userData.originalPos) child.userData.originalPos = originalPos.clone();

            child.position.x = originalPos.x * scale;
            child.position.y = originalPos.y * scale - progress * 0.4; // 아래로도 이동
            child.position.z = originalPos.z * scale;
          }
        });

      } else if (molecule.userData.dissociationType === 'diatomic') {
        // Cl2 or HBr: 두 원자가 좌우로 멀어짐
        molecule.children.forEach((child, idx) => {
          if (child.isMesh && idx < 2) { // 두 원자
            const originalPos = child.userData.originalPos || child.position.clone();
            if (!child.userData.originalPos) child.userData.originalPos = originalPos.clone();

            const direction = originalPos.x > 0 ? 1 : -1;
            child.position.x = originalPos.x + direction * progress * 0.8; // 더 멀리 분리
            child.position.y = originalPos.y - progress * 0.3; // 약간 아래로
          }
        });
      }

      // 결합선 페이드 아웃
      molecule.children.forEach((child) => {
        if (child.isMesh && child.geometry.type === 'CylinderGeometry') {
          child.material.opacity = Math.max(0, 1 - progress * 2);
          child.material.transparent = true;
        }
      });

      // 분해 완료
      if (progress >= 1.0) {
        completeDissociation(molecule);

        // Remove from scene
        sceneRef.current.remove(molecule);
        const molIdx = gasMoleculesRef.current.indexOf(molecule);
        if (molIdx > -1) gasMoleculesRef.current.splice(molIdx, 1);

        molecule.traverse((child) => {
          if (child.geometry) child.geometry.dispose();
          if (child.material) child.material.dispose();
        });

        dissociatingMoleculesRef.current.splice(i, 1);
      }
    }

    // Update gas molecules
    for (let i = gasMoleculesRef.current.length - 1; i >= 0; i--) {
      const molecule = gasMoleculesRef.current[i];

      if (!molecule.userData.active) continue;

      // Slow down when dissociating
      if (molecule.userData.dissociating) {
        molecule.userData.velocity.y *= 0.95; // 분해 중에는 천천히
      }

      molecule.position.add(molecule.userData.velocity);

      // Rotate molecule
      if (molecule.userData.rotationSpeed && !molecule.userData.dissociating) {
        molecule.rotation.x += molecule.userData.rotationSpeed.x;
        molecule.rotation.y += molecule.userData.rotationSpeed.y;
        molecule.rotation.z += molecule.userData.rotationSpeed.z;
      }

      // Check if in plasma zone (y between 2 and 6)
      if (molecule.position.y <= 6 && molecule.position.y >= 2 && molecule.userData.active) {
        const distFromCenter = Math.sqrt(
          molecule.position.x ** 2 + molecule.position.z ** 2
        );

        if (distFromCenter < 5) { // 플라즈마 영역 반지름
          // Start dissociation animation
          if (!molecule.userData.dissociating) {
            startDissociation(molecule);
          }
        }
      }

      // Remove if goes too low without dissociating
      if (molecule.position.y < 0) {
        sceneRef.current.remove(molecule);
        gasMoleculesRef.current.splice(i, 1);

        molecule.traverse((child) => {
          if (child.geometry) child.geometry.dispose();
          if (child.material) child.material.dispose();
        });
      }
    }

    // Update radicals
    for (let i = radicalsRef.current.length - 1; i >= 0; i--) {
      const radical = radicalsRef.current[i];

      if (!radical.userData.active) continue;

      // Gradually direct radicals toward silicon surface
      radical.userData.velocity.y -= 0.001; // 중력 더 감소 - 이미 초기 속도가 아래로 향함
      radical.position.add(radical.userData.velocity);
      radical.userData.lifetime--;

      // Check collision with silicon surface
      if (radical.position.y <= 0.3) {
        const distFromCenter = Math.sqrt(
          radical.position.x ** 2 + radical.position.z ** 2
        );

        if (distFromCenter < 6) { // 원형 웨이퍼 반지름
          // Reaction occurs based on reactivity
          if (Math.random() < props.reactivity) {
            // 가장 가까운 Si 원자 찾기
            const nearestSiAtom = findNearestSiAtom(radical.position);

            if (nearestSiAtom) {
              // Si 원자를 뜯어내서 부산물 생성 (실제 식각!)
              createByproduct(radical.position.clone(), nearestSiAtom);

              // Etching effect
              const etchAmount = props.isotropic ? 0.003 : 0.002;
              setEtchDepth(prev => prev + etchAmount);
            }
          }

          radical.userData.active = false;
          sceneRef.current.remove(radical);
          radicalsRef.current.splice(i, 1);
          radical.geometry.dispose();
          radical.material.dispose();
        }
      }

      // Remove old radicals
      if (radical.userData.lifetime <= 0 || radical.position.y < -2) {
        sceneRef.current.remove(radical);
        radicalsRef.current.splice(i, 1);
        radical.geometry.dispose();
        radical.material.dispose();
      }
    }

    // Update byproducts (volatile, moving upward or away)
    for (let i = byproductsRef.current.length - 1; i >= 0; i--) {
      const byproduct = byproductsRef.current[i];

      byproduct.position.add(byproduct.userData.velocity);

      // Rotate the entire byproduct group
      if (byproduct.userData.rotation) {
        byproduct.rotation.x += byproduct.userData.rotation.x;
        byproduct.rotation.y += byproduct.userData.rotation.y;
        byproduct.rotation.z += byproduct.userData.rotation.z;
      }

      byproduct.userData.lifetime--;

      // Fade out - Group의 모든 children에 적용
      const opacity = byproduct.userData.lifetime / 150;
      byproduct.traverse((child) => {
        if (child.material) {
          child.material.transparent = true;
          child.material.opacity = opacity;
        }
      });

      // Remove when far away or lifetime expired
      if (byproduct.userData.lifetime <= 0 || byproduct.position.y > 20 || byproduct.position.y < -5) {
        sceneRef.current.remove(byproduct);
        byproductsRef.current.splice(i, 1);

        // Dispose all geometries and materials in the group
        byproduct.traverse((child) => {
          if (child.geometry) child.geometry.dispose();
          if (child.material) child.material.dispose();
        });
      }
    }

    // Update silicon appearance based on etch depth
    if (siliconRef.current) {
      const scale = 1 - Math.min(etchDepth * 0.3, 0.5);
      siliconRef.current.scale.set(1, scale, 1); // 수평은 유지, 수직만 축소

      // Change color slightly (darker as etching progresses)
      const colorIntensity = Math.max(0.2, 1 - etchDepth * 0.5);
      siliconRef.current.material.color.setRGB(
        colorIntensity * 0.314,
        colorIntensity * 0.314,
        colorIntensity * 0.314
      );
    }

    // Spawn new gas molecules
    if (isRunningRef.current && Math.random() < 0.12) { // 생성 빈도 더 감소: 0.15 -> 0.12
      createGasMolecule();
    }
  };

  const handleStart = () => {
    setIsRunning(true);
    isRunningRef.current = true;
  };

  const handleStop = () => {
    setIsRunning(false);
    isRunningRef.current = false;
  };

  const handleReset = () => {
    setIsRunning(false);
    isRunningRef.current = false;
    setEtchDepth(0);
    setParticleCount(0);
    setDissociationCount(0);
    timeRef.current = 0;

    // Clear all particles
    [...gasMoleculesRef.current, ...radicalsRef.current, ...byproductsRef.current, ...dissociatingMoleculesRef.current].forEach(p => {
      sceneRef.current.remove(p);
      p.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
    });

    gasMoleculesRef.current = [];
    radicalsRef.current = [];
    byproductsRef.current = [];
    dissociatingMoleculesRef.current = [];

    // Si 원자 복원
    siAtomsRef.current.forEach(atom => {
      atom.userData.active = true;
      atom.visible = true;
    });

    // Reset silicon
    if (siliconRef.current) {
      siliconRef.current.scale.set(1, 1, 1);
      siliconRef.current.position.y = 0;
      siliconRef.current.material.color.setRGB(0.314, 0.314, 0.314);
    }
  };

  const handleGasChange = (newGasType) => {
    handleReset();
    setGasType(newGasType);
    gasTypeRef.current = newGasType; // ref도 즉시 업데이트

    // Si 원자 복원
    siAtomsRef.current.forEach(atom => {
      atom.userData.active = true;
      atom.visible = true;
    });
  };

  useEffect(() => {
    initializeScene();

    return () => {
      if (frameId.current) {
        cancelAnimationFrame(frameId.current);
      }
      if (rendererRef.current && mountRef.current) {
        mountRef.current.removeChild(rendererRef.current.domElement);
      }
    };
  }, []);

  useEffect(() => {
    gasTypeRef.current = gasType;
  }, [gasType]);

  useEffect(() => {
    const handleResize = () => {
      if (rendererRef.current && cameraRef.current && mountRef.current) {
        const width = mountRef.current.clientWidth;
        const height = mountRef.current.clientHeight;

        rendererRef.current.setSize(width, height);
        cameraRef.current.aspect = width / height;
        cameraRef.current.updateProjectionMatrix();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const currentProps = gasProperties[gasType];

  return (
    <div className="w-full h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <h1 className="text-2xl font-bold text-white mb-2">🔬 실리콘 플라즈마 식각 공정 시뮬레이터</h1>
        <p className="text-gray-400 text-sm">가스 분해 → 라디칼 반응 → 휘발성 부산물 생성 과정의 실시간 시각화</p>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* 3D Viewer */}
        <div className="flex-1 relative">
          <div ref={mountRef} className="w-full h-full" />

          {/* Process Flow Info */}
          <div className="absolute top-4 left-4 bg-gray-800 bg-opacity-95 rounded-lg p-4 text-white max-w-md">
            <h3 className="font-bold text-lg mb-3">{currentProps.name}</h3>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-blue-400 font-semibold">① 플라즈마 분해:</span>
                <div className="font-mono text-xs mt-1 bg-gray-900 p-2 rounded">
                  {currentProps.dissociationFormula}
                </div>
                {gasType === 'fluorine' && (
                  <div className="text-xs text-gray-400 mt-1">→ 황(S) 원자는 배출, 6개 F* 라디칼은 식각</div>
                )}
                {gasType === 'cf4' && (
                  <div className="text-xs text-gray-400 mt-1">→ 탄소(C) 원자는 배출, 4개 F* 라디칼은 식각</div>
                )}
                {gasType === 'chlorine' && (
                  <div className="text-xs text-gray-400 mt-1">→ 2개 Cl* 라디칼로 분리</div>
                )}
                {gasType === 'bromine' && (
                  <div className="text-xs text-gray-400 mt-1">→ 수소(H)는 배출, Br* 라디칼은 식각</div>
                )}
              </div>
              <div>
                <span className="text-green-400 font-semibold">② 표면 반응:</span>
                <div className="font-mono text-xs mt-1 bg-gray-900 p-2 rounded">
                  {currentProps.reactionFormula}
                </div>
                <div className="text-xs text-gray-400 mt-1">→ Si 원자가 웨이퍼에서 제거됨 (식각!)</div>
              </div>
              <div>
                <span className="text-purple-400 font-semibold">③ 부산물:</span>
                <span className="ml-2 font-mono">{currentProps.byproduct}</span>
                <span className="text-gray-400 text-xs ml-2">(휘발성, 위로 배출)</span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="absolute top-4 right-4 bg-gray-800 bg-opacity-95 rounded-lg p-4 text-white min-w-52">
            <h3 className="font-bold mb-3">📊 공정 통계</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">가스 분해:</span>
                <span className="font-mono text-blue-400">{dissociationCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">부산물 생성:</span>
                <span className="font-mono text-green-400">{particleCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">식각 깊이:</span>
                <span className="font-mono text-yellow-400">{(etchDepth * 100).toFixed(1)} nm</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">식각률:</span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  currentProps.isotropic ? 'bg-yellow-600' : 'bg-blue-600'
                }`}>
                  {currentProps.isotropic ? '등방성' : '이방성'}
                </span>
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="absolute bottom-4 left-4 bg-gray-800 bg-opacity-95 rounded-lg p-4 text-white">
            <h3 className="font-bold mb-3 text-sm">🎨 범례</h3>
            <div className="space-y-2 text-xs">
              {gasType === 'fluorine' && (
                <>
                  <div className="flex items-center gap-2">
                    <div className="relative w-10 h-6 flex items-center justify-center">
                      <div className="absolute w-5 h-5 rounded-full bg-yellow-400"></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{left: '0px', top: '50%', transform: 'translateY(-50%)'}}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{right: '0px', top: '50%', transform: 'translateY(-50%)'}}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{left: '50%', top: '0px', transform: 'translateX(-50%)'}}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{left: '50%', bottom: '0px', transform: 'translateX(-50%)'}}></div>
                    </div>
                    <span>SF₆ 분자 (황 중심 + 6개 불소)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-yellow-400"></div>
                    <span>황(S) 원자 → 배출</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-green-400"></div>
                    <span>불소(F*) 라디칼 → 식각</span>
                  </div>
                </>
              )}
              {gasType === 'cf4' && (
                <>
                  <div className="flex items-center gap-2">
                    <div className="relative w-10 h-6 flex items-center justify-center">
                      <div className="absolute w-4 h-4 rounded-full" style={{ backgroundColor: '#2a2a2a' }}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{left: '2px', top: '2px'}}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{right: '2px', top: '2px'}}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{left: '2px', bottom: '2px'}}></div>
                      <div className="absolute w-2 h-2 rounded-full bg-green-400" style={{right: '2px', bottom: '2px'}}></div>
                    </div>
                    <span>CF₄ 분자 (탄소 중심 + 4개 불소)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#2a2a2a' }}></div>
                    <span>탄소(C) 원자 → 배출</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-green-400"></div>
                    <span>불소(F*) 라디칼 → 식각</span>
                  </div>
                </>
              )}
              {gasType === 'chlorine' && (
                <>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                      <div className="w-5 h-5 rounded-full bg-green-500"></div>
                      <div className="w-1 h-0.5 bg-gray-400"></div>
                      <div className="w-5 h-5 rounded-full bg-green-500"></div>
                    </div>
                    <span>Cl₂ 분자 (2개 녹색 염소)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-green-400"></div>
                    <span>염소(Cl*) 라디칼 → 식각</span>
                  </div>
                </>
              )}
              {gasType === 'bromine' && (
                <>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                      <div className="w-3 h-3 rounded-full bg-white"></div>
                      <div className="w-1 h-0.5 bg-gray-400"></div>
                      <div className="w-5 h-5 rounded-full" style={{ backgroundColor: '#8b4513' }}></div>
                    </div>
                    <span>HBr 분자 (흰색 H + 밤색 Br)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-white"></div>
                    <span>수소(H) 원자 → 배출</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#aa6633' }}></div>
                    <span>브롬(Br*) 라디칼 → 식각</span>
                  </div>
                </>
              )}
              <div className="flex items-center gap-2 pt-1 border-t border-gray-600">
                <div className="w-4 h-4 bg-gradient-to-br from-purple-400 to-blue-600 rounded"></div>
                <span>플라즈마 영역 (분해 구역)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-2 bg-gray-600 rounded-full"></div>
                <span>Si 웨이퍼 (원형, 회전 중)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#888888' }}></div>
                <span>Si 원자 (식각되며 제거됨)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-0.5">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#888888' }}></div>
                  {gasType === 'bromine' ? (
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#aa6633' }}></div>
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                  )}
                </div>
                <span>{currentProps.byproduct} (Si + {gasType === 'fluorine' || gasType === 'cf4' ? 'F' : gasType === 'chlorine' ? 'Cl' : 'Br'})</span>
              </div>
            </div>
          </div>

          {/* Process Steps Indicator */}
          <div className="absolute bottom-4 right-4 bg-gray-800 bg-opacity-95 rounded-lg p-3 text-white">
            <h3 className="font-bold mb-2 text-xs">⚙️ 공정 단계</h3>
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-blue-400">▼</span>
                <span>가스 분자 주입</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-purple-400">⚡</span>
                <span>플라즈마 분해</span>
              </div>
              {gasType === 'fluorine' && (
                <div className="flex items-center gap-2">
                  <span className="text-yellow-400">◉</span>
                  <span>S 원자 배출</span>
                </div>
              )}
              {gasType === 'cf4' && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">◉</span>
                  <span>C 원자 배출</span>
                </div>
              )}
              {gasType === 'bromine' && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-300">◉</span>
                  <span>H 원자 배출</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <span className="text-green-400">→</span>
                <span>라디칼 확산</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-yellow-400">✱</span>
                <span>Si 원자 제거 (식각!)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-cyan-400">▲</span>
                <span>{currentProps.byproduct} 배출</span>
              </div>
            </div>
          </div>
        </div>

        {/* Control Panel */}
        <div className="w-80 bg-gray-800 border-l border-gray-700 p-6 overflow-y-auto">
          <h2 className="text-xl font-bold text-white mb-4">🎛️ 제어 패널</h2>

          {/* Gas Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-300 mb-3">
              식각 가스 선택
            </label>
            <div className="space-y-2">
              {Object.entries(gasProperties).map(([key, props]) => (
                <button
                  key={key}
                  onClick={() => handleGasChange(key)}
                  className={`w-full text-left p-3 rounded-lg transition-all ${
                    gasType === key
                      ? 'bg-blue-600 text-white shadow-lg ring-2 ring-blue-400'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  <div className="font-semibold">{props.name}</div>
                  <div className="text-xs mt-1 opacity-80">
                    {props.radical} → {props.byproduct}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Controls */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-300 mb-3">
              공정 제어
            </label>
            <div className="space-y-2">
              <button
                onClick={handleStart}
                disabled={isRunning}
                className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-semibold shadow-lg"
              >
                ▶ 식각 시작
              </button>
              <button
                onClick={handleStop}
                disabled={!isRunning}
                className="w-full px-4 py-3 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-semibold"
              >
                ⏸ 일시 정지
              </button>
              <button
                onClick={handleReset}
                className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-semibold"
              >
                ⟳ 리셋
              </button>
            </div>
          </div>

          {/* Process Characteristics */}
          <div className="bg-gray-700 rounded-lg p-4 mb-4">
            <h3 className="text-sm font-semibold text-white mb-3">📈 공정 특성</h3>
            <div className="space-y-3 text-xs text-gray-300">
              <div>
                <div className="flex justify-between mb-1">
                  <span>반응성</span>
                  <span>{(currentProps.reactivity * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-gray-600 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${currentProps.reactivity * 100}%` }}
                  ></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span>라디칼 생성</span>
                  <span>×{currentProps.radicalCount}</span>
                </div>
                <div className="w-full bg-gray-600 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all"
                    style={{ width: `${(currentProps.radicalCount / 6) * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>

          {/* Reaction Mechanism */}
          <div className="bg-gray-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-white mb-2">⚗️ 반응 메커니즘</h3>
            <div className="text-xs text-gray-300 space-y-2">
              <div className="flex items-start gap-2">
                <span className="text-blue-400 font-bold">1.</span>
                <span>가스 분자가 플라즈마 영역 진입</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-purple-400 font-bold">2.</span>
                {gasType === 'fluorine' && <span>SF₆ → S + 6F* (황과 불소 분리)</span>}
                {gasType === 'cf4' && <span>CF₄ → C + 4F* (탄소와 불소 분리)</span>}
                {gasType === 'chlorine' && <span>Cl₂ → 2Cl* (염소 분자 분리)</span>}
                {gasType === 'bromine' && <span>HBr → H + Br* (수소와 브롬 분리)</span>}
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400 font-bold">3.</span>
                <span>{currentProps.radical} 라디칼이 실리콘으로 확산</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-yellow-400 font-bold">4.</span>
                <span>Si 원자가 표면에서 제거됨 (식각!)</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-cyan-400 font-bold">5.</span>
                <span>{currentProps.byproduct} 부산물이 위로 배출</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// EtchSimulator Main Component
// ============================================================

const EtchSimulator = () => {
  // 탭 상태 관리
  const [activeTab, setActiveTab] = useState('overview');

  // 기본 공정 파라미터 상태들 (실제 식각 파라미터)
  const [pressure, setPressure] = useState(100); // mTorr
  const [power, setPower] = useState(300); // W
  const [time, setTime] = useState(60); // sec
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationProgress, setSimulationProgress] = useState(0);

  // 식각 타겟 선택
  const [etchTarget, setEtchTarget] = useState('Si');

  // 가스 플로우 상태들 (실제 식각 가스)
  const [gasFlows, setGasFlows] = useState({
    Cl2: 30, // Silicon etch
    HBr: 15, // Selectivity improvement
    CF4: 0,  // Oxide etch
    CHF3: 0, // Oxide etch
    O2: 0,   // Polymer removal
    Ar: 90   // Carrier gas
  });

  // 공정 모드 및 장비 상태
  const [processMode, setProcessMode] = useState('standby');
  const [equipmentLoaded, setEquipmentLoaded] = useState(false);
  const [powerOn, setPowerOn] = useState(false);

  // 시뮬레이션 결과 상태들 (실제 식각 결과)
  const [etchRate, setEtchRate] = useState(0); // nm/min
  const [selectivity, setSelectivity] = useState(0); // 선택비
  const [uniformity, setUniformity] = useState(0); // 균일성 %
  const [profile, setProfile] = useState('anisotropic'); // 식각 프로파일
  const [endpointDetected, setEndpointDetected] = useState(false);

  // 애니메이션 상태들
  const [animatedValue, setAnimatedValue] = useState(10);
  const [blinkState, setBlinkState] = useState(true);
  const [etchDepth, setEtchDepth] = useState(0);

  // 퀴즈 상태들
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [score, setScore] = useState(0);
  const [showResults, setShowResults] = useState(false);

  // 분석 탭용 시뮬레이션 파라미터들
  const [analysisPressure, setAnalysisPressure] = useState(100);
  const [analysisPower, setAnalysisPower] = useState(300);
  const [analysisGasRatio, setAnalysisGasRatio] = useState(50);
  const [showAnalysisResult, setShowAnalysisResult] = useState(false);

  // Overview 탭 애니메이션 상태들
  const [isAnimationPlaying, setIsAnimationPlaying] = useState(false);
  const [activeElementIndex, setActiveElementIndex] = useState(-1);
  const [typingText, setTypingText] = useState('');
  const [fullText, setFullText] = useState('');

  // 5대 요소 설명 데이터
  const elementsData = [
    {
      name: '식각률 (Etch Rate)',
      description: '단위 시간당 식각되는 물질의 두께를 나타내는 핵심 지표입니다. 식각률은 E/R = 식각 깊이(Å) / 식각 시간(min) 공식으로 계산되며, 일반적으로 Å/min 또는 nm/min 단위를 사용합니다. 높은 식각률은 공정 시간을 단축시켜 생산성을 향상시키지만, 너무 빠른 식각은 정밀한 제어가 어렵고 플라즈마 데미지를 유발할 수 있습니다. RF 파워, 압력, 가스 유량, 온도 등이 주요 영향 인자이며, 물질마다 최적의 식각률이 다릅니다. 예를 들어, ICP 장비로 Si를 식각할 경우 100-300 nm/min, SiO₂는 50-150 nm/min 정도의 식각률을 나타냅니다.',
      position: { cx: 200, cy: 80 }
    },
    {
      name: '선택성 (Selectivity)',
      description: '타겟 물질과 다른 물질(마스크, 하부층) 사이의 식각률 비율을 나타냅니다. Selectivity = 타겟 물질 식각률 / 기준 물질 식각률로 계산되며, 높은 선택비는 마스크나 하부층을 보호하면서 타겟만 선택적으로 식각할 수 있게 합니다. 예를 들어 Si:SiO₂ = 20:1의 선택비는 Si가 SiO₂보다 20배 빠르게 식각됨을 의미합니다. 선택비는 공정 마진을 증가시키고 End-point 검출에 여유를 주며, 측벽 손상을 최소화합니다. HBr 첨가(Si 식각 시), 폴리머 형성, 저온 공정 등으로 선택비를 향상시킬 수 있으며, 실제 공정에서는 10:1 이상의 선택비를 목표로 합니다.',
      position: { cx: 310, cy: 140 }
    },
    {
      name: '균일성 (Uniformity)',
      description: '웨이퍼 전체 영역에서 식각 깊이와 프로파일이 얼마나 일관적인지를 나타내는 지표입니다. Uniformity(%) = ±[(Max-Min)/(2×Average)]×100 공식으로 계산하며, ±3% 이내를 목표로 합니다(선단 공정에서는 ±2% 이내). 불균일성은 플라즈마 밀도 분포, 가스 흐름, 웨이퍼 온도 분포, RF 전력 분포 등이 원인이 됩니다. 균일성이 좋지 않으면 웨이퍼의 어떤 부분은 과도하게 식각되고(over-etch) 다른 부분은 부족하게 식각되어(under-etch) 수율이 크게 감소합니다. 압력 최적화, 다중 가스 주입구, ESC 온도 제어, 웨이퍼 회전 등으로 균일성을 개선할 수 있습니다.',
      position: { cx: 310, cy: 260 }
    },
    {
      name: '이방도 (Anisotropy)',
      description: '식각이 수직 방향으로 진행되는 정도를 나타내며, 마스크 패턴을 얼마나 충실하게 전사하는지의 지표입니다. Anisotropy = 1 - (수평 식각률/수직 식각률)로 계산되며, A=1은 완전 이방성(수직 식각), A=0은 완전 등방성(모든 방향 균일)을 의미합니다. 미세 패턴 형성을 위해서는 높은 이방성이 필수적이며, 특히 Gate, Contact/Via, MEMS, TSV 등에서 중요합니다. 저압력(10-50 mTorr), 고 바이어스 전압, 방향성 이온 충격을 통해 이방성을 높일 수 있습니다. 반대로 고압력, 저 바이어스에서는 화학적 반응이 우세하여 등방성 식각이 일어나며, Spacer 형성이나 Recess 식각에 활용됩니다.',
      position: { cx: 90, cy: 260 }
    },
    {
      name: 'Loading Effect (로딩 효과)',
      description: '패턴 밀도(open area ratio)에 따라 식각 속도가 달라지는 현상으로, 대면적 소자에서 심각한 문제가 됩니다. 식각되는 면적이 클수록 반응 가스가 빠르게 소모되고 부산물이 축적되어 식각률이 감소합니다. Macro Loading(웨이퍼 간/내 대면적 차이), Micro Loading(미세 패턴 간 밀도 차이), ARDE(Aspect Ratio Dependent Etch) 효과로 구분됩니다. 예를 들어 DRAM의 Cell Array(고밀도)와 Periphery(저밀도) 사이에 20-30%의 식각률 차이가 발생할 수 있습니다. 가스 유량 증가, Dummy Pattern 삽입, 다단계 식각(main+soft), OPC 적용 등으로 보상할 수 있으며, 설계 단계부터 패턴 밀도를 균일화하는 것이 중요합니다.',
      position: { cx: 90, cy: 140 }
    }
  ];

  // 탭 정의
  const tabs = [
    { id: 'overview', name: '식각 공정 개요', icon: '📋' },
    { id: 'etch-elements', name: '식각 요소', icon: '🔬' },
    { id: 'process', name: '식각 원리', icon: '🧪' },
    { id: 'analysis', name: 'Si식각메커니즘', icon: '📊' },
    { id: 'quiz', name: '식각 평가', icon: '📝' }
  ];

  // 식각 계산 함수들
  const calculateEtchRate = (material, gasFlow, power, pressure) => {
    let baseRate = 100; // nm/min

    switch(material) {
      case 'Si':
        baseRate = (gasFlow.Cl2 / 30) * (power / 300) * (pressure / 100) * 100;
        break;
      case 'SiO2':
        baseRate = (gasFlow.CF4 / 30) * (power / 600) * (pressure / 30) * 50;
        break;
      case 'Si3N4':
        baseRate = (gasFlow.CHF3 / 25) * (power / 600) * (pressure / 30) * 40;
        break;
      default:
        baseRate = 50;
    }

    return Math.max(0, baseRate * (0.8 + Math.random() * 0.4));
  };

  const calculateSelectivity = (target, gasFlow) => {
    if (target === 'Si' && gasFlow.HBr > 0) {
      return 10 + (gasFlow.HBr / 15) * 20; // HBr improves selectivity
    }
    if (target === 'SiO2' && gasFlow.CF4 > 0) {
      return 15 + (gasFlow.CF4 / 30) * 10;
    }
    return 5 + Math.random() * 10;
  };

  const calculateUniformity = (pressure, power) => {
    const pressureEffect = Math.max(0, 100 - Math.abs(pressure - 100) / 2);
    const powerEffect = Math.max(0, 100 - Math.abs(power - 300) / 5);
    return (pressureEffect + powerEffect) / 2;
  };

  const calculatePressureEffect = (pressure) => {
    // 압력이 높을수록 등방성 식각 증가
    return Math.min(2.0, 0.5 + (pressure / 100));
  };

  const calculatePowerEffect = (power) => {
    // 파워가 높을수록 식각속도 증가
    return Math.min(3.0, 0.5 + (power / 200));
  };

  const calculateGasRatioEffect = (ratio) => {
    // 가스 비율에 따른 선택비 변화
    return Math.min(2.0, 0.8 + (ratio / 50));
  };

  const runEtchSimulation = () => {
    setIsSimulating(true);
    setSimulationProgress(0);
    setEtchDepth(0);

    const interval = setInterval(() => {
      setSimulationProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsSimulating(false);
          setEndpointDetected(true);

          // 최종 결과 계산
          const finalEtchRate = calculateEtchRate(etchTarget, gasFlows, power, pressure);
          const finalSelectivity = calculateSelectivity(etchTarget, gasFlows);
          const finalUniformity = calculateUniformity(pressure, power);

          setEtchRate(finalEtchRate);
          setSelectivity(finalSelectivity);
          setUniformity(finalUniformity);

          return 100;
        }

        // 실시간 식각 깊이 업데이트
        setEtchDepth(prev => prev + 2);

        return prev + 2;
      });
    }, 100);
  };

  const generateTimeSeriesData = () => {
    const data = [];
    for (let i = 0; i <= 60; i += 5) {
      data.push({
        time: i,
        etchRate: calculateEtchRate(etchTarget, gasFlows, power, pressure) * (0.9 + Math.random() * 0.2),
        pressure: pressure + (Math.random() - 0.5) * 5,
        power: power + (Math.random() - 0.5) * 10
      });
    }
    return data;
  };

  const generateAnalysisData = () => {
    const data = [];
    for (let i = 50; i <= 200; i += 10) {
      data.push({
        pressure: i,
        etchRate: calculateEtchRate(etchTarget, gasFlows, power, i),
        uniformity: calculateUniformity(i, power)
      });
    }
    return data;
  };

  // 식각 관련 퀴즈 문제들
  const quizQuestions = [
    {
      question: "실리콘(Si) 식각에 주로 사용되는 가스는?",
      options: ["Cl2 (염소)", "CF4 (사불화탄소)", "CHF3 (삼불화메탄)", "O2 (산소)"],
      correct: 0,
      explanation: "실리콘 식각에는 Cl2 가스가 주로 사용되며, 화학적 반응을 통해 SiCl4를 형성하여 식각됩니다."
    },
    {
      question: "HBr 가스를 첨가하는 주된 목적은?",
      options: ["식각속도 증가", "산화막과의 선택비 개선", "균일성 향상", "플라즈마 안정화"],
      correct: 1,
      explanation: "HBr 가스는 옥사이드와의 선택비를 증가시키는 목적으로 사용됩니다."
    },
    {
      question: "Deep Si 식각에서 발생할 수 있는 문제는?",
      options: ["식각속도 감소", "언더컷 발생", "선택비 증가", "균일성 향상"],
      correct: 1,
      explanation: "미세패턴이나 종횡비가 높은 구조에서는 마스크 아래 부분의 언더컷이 발생할 수 있습니다."
    },
    {
      question: "Bosch 공정의 특징은?",
      options: ["연속적인 식각", "식각과 보호막 형성의 반복", "높은 온도 사용", "습식 식각"],
      correct: 1,
      explanation: "Bosch 공정은 식각가스와 보호막 가스를 번갈아 사용하여 높은 종횡비 구조를 형성합니다."
    },
    {
      question: "PR Ashing에 사용되는 가스는?",
      options: ["Cl2", "CF4", "O2", "HBr"],
      correct: 2,
      explanation: "PR Ashing은 산소 플라즈마를 이용하여 포토레지스트를 제거하는 공정입니다."
    }
  ];

  // 애니메이션 효과들
  useEffect(() => {
    const animationInterval = setInterval(() => {
      setAnimatedValue(prev => {
        const newValue = prev + 1;
        return newValue > 50 ? 10 : newValue;
      });
    }, 200);
    return () => clearInterval(animationInterval);
  }, []);

  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setBlinkState(prev => !prev);
    }, 1000);
    return () => clearInterval(blinkInterval);
  }, []);

  const submitAnswer = () => {
    if (selectedAnswer === quizQuestions[currentQuestion].correct.toString()) {
      setScore(score + 1);
    }

    if (currentQuestion < quizQuestions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setSelectedAnswer('');
    } else {
      setShowResults(true);
    }
  };

  const resetQuiz = () => {
    setCurrentQuestion(0);
    setSelectedAnswer('');
    setScore(0);
    setShowResults(false);
  };

  // Overview 애니메이션 제어 - 다음 요소로 진행
  const proceedToNextElement = () => {
    if (activeElementIndex === -1) {
      // 첫 시작
      setIsAnimationPlaying(true);
      setActiveElementIndex(0);
      setFullText(elementsData[0].description);
      setTypingText('');
    } else if (activeElementIndex < elementsData.length - 1) {
      // 다음 요소로
      const nextIndex = activeElementIndex + 1;
      setActiveElementIndex(nextIndex);
      setFullText(elementsData[nextIndex].description);
      setTypingText('');
    } else {
      // 마지막 요소 완료 - 처음으로
      setActiveElementIndex(0);
      setFullText(elementsData[0].description);
      setTypingText('');
    }
  };

  // 애니메이션 정지
  const stopAnimation = () => {
    setIsAnimationPlaying(false);
    setActiveElementIndex(-1);
    setTypingText('');
  };

  // 타이핑 효과
  useEffect(() => {
    if (!isAnimationPlaying || activeElementIndex === -1) return;

    let currentIndex = 0;
    const text = fullText;
    setTypingText('');

    const typingInterval = setInterval(() => {
      if (currentIndex < text.length) {
        setTypingText(text.substring(0, currentIndex + 1));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
      }
    }, 30); // 30ms마다 한 글자씩

    return () => clearInterval(typingInterval);
  }, [fullText, isAnimationPlaying, activeElementIndex]);

  // 가스 조합 프리셋
  const gasPresets = {
    'Si': { Cl2: 30, HBr: 15, CF4: 0, CHF3: 0, O2: 0, Ar: 90 },
    'SiO2': { Cl2: 0, HBr: 0, CF4: 5, CHF3: 30, O2: 0, Ar: 90 },
    'Si3N4': { Cl2: 0, HBr: 0, CF4: 0, CHF3: 25, O2: 5, Ar: 70 },
    'PR': { Cl2: 0, HBr: 0, CF4: 0, CHF3: 0, O2: 100, Ar: 0 }
  };

  // 탭별 컨텐츠 렌더링
  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 rounded-lg">
              <h3 className="text-xl font-bold text-blue-800 mb-4">📋 반도체 식각(Etch) 공정 개요</h3>
              <p className="text-gray-700 leading-relaxed mb-4">
                식각(Etching)은 반도체 공정에서 사진공정으로 형성된 패턴을 실제 기판으로 옮기는 핵심 공정입니다.
                플라즈마를 이용한 건식식각이 주로 사용되며, 다음 5가지 핵심 요소를 고려해야 합니다.
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <div className="flex justify-between items-center mb-4">
                <h4 className="text-lg font-semibold">식각 공정 관리 5대 핵심 요소</h4>
                <div className="flex gap-2">
                  {isAnimationPlaying && (
                    <button
                      onClick={stopAnimation}
                      className="px-6 py-2 rounded-lg font-semibold transition-all bg-red-500 hover:bg-red-600 text-white"
                    >
                      ⏸ 정지
                    </button>
                  )}
                  <button
                    onClick={proceedToNextElement}
                    className="px-6 py-2 rounded-lg font-semibold transition-all bg-blue-500 hover:bg-blue-600 text-white"
                  >
                    {activeElementIndex === -1 ? '▶ 재생' :
                     activeElementIndex === elementsData.length - 1 ? '🔄 처음부터' : '▶ 계속 재생'}
                  </button>
                </div>
              </div>

              {/* 다이어그램과 설명 영역 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 중앙의 순환 다이어그램 */}
                <div className="flex justify-center items-center">
                  <svg width="400" height="400" viewBox="0 0 400 400">
                    {/* 중앙 원 */}
                    <circle cx="200" cy="200" r="50" fill="#e0f2fe" stroke="#0284c7" strokeWidth="3"/>
                    <text x="200" y="195" textAnchor="middle" className="text-sm font-bold" fill="#0284c7">식각</text>
                    <text x="200" y="210" textAnchor="middle" className="text-sm font-bold" fill="#0284c7">공정</text>

                    {/* 5개 요소 원들 - 애니메이션 적용 */}
                    <g>
                      {/* 1. 식각률 (12시) */}
                      <g>
                        {/* 외곽 강조 링 (활성화 시) */}
                        {activeElementIndex === 0 && (
                          <>
                            <circle cx="200" cy="80" r="48" fill="none" stroke="#f59e0b" strokeWidth="3" opacity="0.6">
                              <animate attributeName="r" values="48;52;48" dur="1.5s" repeatCount="indefinite"/>
                              <animate attributeName="opacity" values="0.6;0.3;0.6" dur="1.5s" repeatCount="indefinite"/>
                            </circle>
                            <circle cx="200" cy="80" r="45" fill="none" stroke="#f59e0b" strokeWidth="2" opacity="0.4"/>
                          </>
                        )}
                        {/* 기본 원 */}
                        <circle cx="200" cy="80" r="40" fill="#fef3c7" stroke="#f59e0b" strokeWidth="2"/>
                        <text x="200" y="75" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 0 ? "bold" : "600"}>Etch Rate</text>
                        <text x="200" y="88" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 0 ? "bold" : "normal"}>식각률</text>
                      </g>
                      <line x1="200" y1="150" x2="200" y2="120" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                      {/* 2. 선택성 (2시) */}
                      <g>
                        {/* 외곽 강조 링 (활성화 시) */}
                        {activeElementIndex === 1 && (
                          <>
                            <circle cx="310" cy="140" r="48" fill="none" stroke="#22c55e" strokeWidth="3" opacity="0.6">
                              <animate attributeName="r" values="48;52;48" dur="1.5s" repeatCount="indefinite"/>
                              <animate attributeName="opacity" values="0.6;0.3;0.6" dur="1.5s" repeatCount="indefinite"/>
                            </circle>
                            <circle cx="310" cy="140" r="45" fill="none" stroke="#22c55e" strokeWidth="2" opacity="0.4"/>
                          </>
                        )}
                        {/* 기본 원 */}
                        <circle cx="310" cy="140" r="40" fill="#dcfce7" stroke="#22c55e" strokeWidth="2"/>
                        <text x="310" y="135" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 1 ? "bold" : "600"}>Selectivity</text>
                        <text x="310" y="148" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 1 ? "bold" : "normal"}>선택성</text>
                      </g>
                      <line x1="245" y1="165" x2="275" y2="155" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                      {/* 3. 균일성 (4시) */}
                      <g>
                        {/* 외곽 강조 링 (활성화 시) */}
                        {activeElementIndex === 2 && (
                          <>
                            <circle cx="310" cy="260" r="48" fill="none" stroke="#6366f1" strokeWidth="3" opacity="0.6">
                              <animate attributeName="r" values="48;52;48" dur="1.5s" repeatCount="indefinite"/>
                              <animate attributeName="opacity" values="0.6;0.3;0.6" dur="1.5s" repeatCount="indefinite"/>
                            </circle>
                            <circle cx="310" cy="260" r="45" fill="none" stroke="#6366f1" strokeWidth="2" opacity="0.4"/>
                          </>
                        )}
                        {/* 기본 원 */}
                        <circle cx="310" cy="260" r="40" fill="#e0e7ff" stroke="#6366f1" strokeWidth="2"/>
                        <text x="310" y="255" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 2 ? "bold" : "600"}>Uniformity</text>
                        <text x="310" y="268" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 2 ? "bold" : "normal"}>균일성</text>
                      </g>
                      <line x1="245" y1="235" x2="275" y2="245" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                      {/* 4. 이방도 (8시) */}
                      <g>
                        {/* 외곽 강조 링 (활성화 시) */}
                        {activeElementIndex === 3 && (
                          <>
                            <circle cx="90" cy="260" r="48" fill="none" stroke="#ec4899" strokeWidth="3" opacity="0.6">
                              <animate attributeName="r" values="48;52;48" dur="1.5s" repeatCount="indefinite"/>
                              <animate attributeName="opacity" values="0.6;0.3;0.6" dur="1.5s" repeatCount="indefinite"/>
                            </circle>
                            <circle cx="90" cy="260" r="45" fill="none" stroke="#ec4899" strokeWidth="2" opacity="0.4"/>
                          </>
                        )}
                        {/* 기본 원 */}
                        <circle cx="90" cy="260" r="40" fill="#fce7f3" stroke="#ec4899" strokeWidth="2"/>
                        <text x="90" y="255" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 3 ? "bold" : "600"}>Anisotropy</text>
                        <text x="90" y="268" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 3 ? "bold" : "normal"}>이방도</text>
                      </g>
                      <line x1="155" y1="235" x2="125" y2="245" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                      {/* 5. Loading Effect (10시) */}
                      <g>
                        {/* 외곽 강조 링 (활성화 시) */}
                        {activeElementIndex === 4 && (
                          <>
                            <circle cx="90" cy="140" r="48" fill="none" stroke="#a855f7" strokeWidth="3" opacity="0.6">
                              <animate attributeName="r" values="48;52;48" dur="1.5s" repeatCount="indefinite"/>
                              <animate attributeName="opacity" values="0.6;0.3;0.6" dur="1.5s" repeatCount="indefinite"/>
                            </circle>
                            <circle cx="90" cy="140" r="45" fill="none" stroke="#a855f7" strokeWidth="2" opacity="0.4"/>
                          </>
                        )}
                        {/* 기본 원 */}
                        <circle cx="90" cy="140" r="40" fill="#f3e8ff" stroke="#a855f7" strokeWidth="2"/>
                        <text x="90" y="135" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 4 ? "bold" : "600"}>Loading</text>
                        <text x="90" y="148" textAnchor="middle" className="text-xs" fontWeight={activeElementIndex === 4 ? "bold" : "normal"}>로딩효과</text>
                      </g>
                      <line x1="155" y1="165" x2="125" y2="155" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>
                    </g>

                    {/* 화살표 마커 정의 */}
                    <defs>
                      <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#64748b"/>
                      </marker>
                    </defs>
                  </svg>
                </div>

                {/* 설명 영역 */}
                <div className="flex items-center">
                  {activeElementIndex >= 0 ? (
                    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 p-6 rounded-lg border-2 border-indigo-200 shadow-lg min-h-[300px]">
                      <h5 className="text-xl font-bold text-indigo-900 mb-4">
                        {elementsData[activeElementIndex].name}
                      </h5>
                      <p className="text-gray-700 leading-relaxed text-lg">
                        {typingText}
                        <span className="inline-block w-0.5 h-5 bg-indigo-600 ml-1 animate-pulse"></span>
                      </p>
                    </div>
                  ) : (
                    <div className="bg-gray-50 p-6 rounded-lg border-2 border-gray-200 min-h-[300px] flex items-center justify-center">
                      <p className="text-gray-500 text-center">
                        ▶ 재생 버튼을 눌러<br />
                        5대 핵심 요소를<br />
                        자세히 알아보세요
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-400">
                  <h5 className="font-semibold text-yellow-800 mb-2">⚡ 식각률 (Etch Rate)</h5>
                  <p className="text-sm text-gray-700">단위시간당 식각되는 물질의 양</p>
                  <p className="text-xs text-gray-600 mt-1">E/R = x/t (Å/min)</p>
                </div>

                <div className="bg-green-50 p-4 rounded-lg border-l-4 border-green-400">
                  <h5 className="font-semibold text-green-800 mb-2">🎯 선택성 (Selectivity)</h5>
                  <p className="text-sm text-gray-700">서로 다른 물질의 식각률 비율</p>
                  <p className="text-xs text-gray-600 mt-1">S = EA/EB</p>
                </div>

                <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-400">
                  <h5 className="font-semibold text-blue-800 mb-2">⚖️ 균일성 (Uniformity)</h5>
                  <p className="text-sm text-gray-700">웨이퍼 전체의 식각 특성 일관성</p>
                  <p className="text-xs text-gray-600 mt-1">±(Max-Min)/(2×Avg)×100%</p>
                </div>

                <div className="bg-pink-50 p-4 rounded-lg border-l-4 border-pink-400">
                  <h5 className="font-semibold text-pink-800 mb-2">📐 이방도 (Anisotropy)</h5>
                  <p className="text-sm text-gray-700">마스크 패턴 충실도 구현 정도</p>
                  <p className="text-xs text-gray-600 mt-1">A = 1 - (RL/RV)</p>
                </div>

                <div className="bg-purple-50 p-4 rounded-lg border-l-4 border-purple-400">
                  <h5 className="font-semibold text-purple-800 mb-2">🔄 Loading Effect</h5>
                  <p className="text-sm text-gray-700">패턴 밀도에 따른 식각속도 변화</p>
                  <p className="text-xs text-gray-600 mt-1">Etchant 소모와 부산물 축적</p>
                </div>

                <div className="bg-indigo-50 p-4 rounded-lg border-l-4 border-indigo-400">
                  <h5 className="font-semibold text-indigo-800 mb-2">🔬 식각원리</h5>
                  <p className="text-sm text-gray-700">물리적+화학적 복합 반응</p>
                  <p className="text-xs text-gray-600 mt-1">플라즈마 활성종 생성</p>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 p-6 rounded-lg border-l-4 border-yellow-400">
              <h4 className="text-lg font-semibold text-yellow-800 mb-4">💡 학습 가이드</h4>
              <div className="space-y-2 text-gray-700">
                <p>• <strong>식각 요소</strong> 탭에서 5가지 핵심 요소(식각률, 선택성, 균일성, 이방도, 로딩효과)를 자세히 학습하세요</p>
                <p>• <strong>식각 원리</strong> 탭에서 실제 공정 조건을 조절하며 화학 반응과 물리적 메커니즘을 체험하세요</p>
                <p>• <strong>영향 인자 분석</strong> 탭에서 파라미터 변화가 식각 결과에 미치는 영향을 확인하세요</p>
                <p>• <strong>식각 평가</strong> 탭에서 학습한 내용을 퀴즈로 점검해보세요</p>
              </div>
            </div>
          </div>
        );

      case 'etch-elements':
        return (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 p-6 rounded-lg">
              <h3 className="text-xl font-bold text-indigo-800 mb-4">🔬 식각 공정 5대 핵심 요소</h3>
              <p className="text-gray-700 leading-relaxed">
                반도체 식각 공정을 정확하게 제어하고 평가하기 위해서는 5가지 핵심 요소를 이해하고 관리해야 합니다.
                각 요소는 서로 밀접하게 연관되어 있으며, 최적의 식각 결과를 얻기 위해서는 이들 간의 균형을 맞추는 것이 중요합니다.
              </p>
            </div>

            {/* 1. 식각률 (Etch Rate) */}
            <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-yellow-400">
              <h4 className="text-2xl font-bold text-yellow-800 mb-4">⚡ 1. 식각률 (Etch Rate)</h4>

              <div className="space-y-4">
                <div className="bg-yellow-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-yellow-900 mb-2">정의</h5>
                  <p className="text-gray-700">단위 시간당 식각되는 물질의 두께 또는 깊이를 나타내는 지표</p>
                  <div className="mt-3 p-3 bg-white rounded border-2 border-yellow-300">
                    <p className="font-mono text-center text-lg">E/R = 식각 깊이(Å) / 식각 시간(min)</p>
                    <p className="text-sm text-gray-600 text-center mt-2">단위: Å/min 또는 nm/min</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-blue-800 mb-3">영향 인자</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• <strong>RF 파워:</strong> 파워 ↑ → 식각률 ↑</li>
                      <li>• <strong>압력:</strong> 최적 압력 존재 (물질마다 다름)</li>
                      <li>• <strong>가스 유량:</strong> 반응 가스 ↑ → 식각률 ↑</li>
                      <li>• <strong>온도:</strong> 온도 ↑ → 화학 반응 ↑</li>
                      <li>• <strong>바이어스:</strong> 이온 에너지 ↑ → 식각률 ↑</li>
                    </ul>
                  </div>

                  <div className="bg-red-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-red-800 mb-3">공정 고려사항</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• 생산성: 높은 식각률 → 짧은 공정 시간</li>
                      <li>• 제어성: 너무 빠르면 정밀 제어 어려움</li>
                      <li>• 손상: 과도한 식각률 → 플라즈마 데미지</li>
                      <li>• 균일성: 식각률과 균일성은 trade-off</li>
                      <li>• 선택비: 식각률 증가 시 선택비 감소 가능</li>
                    </ul>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">식각률 개념도</h5>
                  <div className="flex justify-center mb-4">
                    <svg width="300" height="200" viewBox="0 0 300 200">
                      {/* 기판 (맨 아래 패턴) */}
                      <defs>
                        <pattern id="substrate_etch_rate" patternUnits="userSpaceOnUse" width="8" height="8">
                          <rect width="8" height="8" fill="white"/>
                          <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                        </pattern>
                      </defs>
                      <rect x="0" y="160" width="300" height="40" fill="url(#substrate_etch_rate)"/>

                      {/* 식각 대상물질 (초록색) - 전체 */}
                      <rect x="0" y="80" width="300" height="80" fill="#4CAF50"/>

                      {/* 마스크 (보라색) */}
                      <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                      <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                      {/* 식각된 영역 (하얀색) */}
                      <rect x="80" y="60" width="140" height="60" fill="white"/>

                      {/* 세로 양방향 화살표와 x 표시 */}
                      <g>
                        <line x1="250" y1="85" x2="250" y2="115" stroke="black" strokeWidth="1.5"/>
                        <polygon points="250,85 247,90 253,90" fill="black"/>
                        <polygon points="250,115 247,110 253,110" fill="black"/>
                        <text x="255" y="105" fontSize="16" fill="black" fontWeight="bold">x</text>
                      </g>

                      {/* Etch Time = t 라벨 */}
                      <text x="150" y="30" fontSize="14" textAnchor="middle" fontWeight="bold" fill="#000">Etch Time = t</text>
                    </svg>
                  </div>
                  <p className="text-sm text-gray-600 text-center">식각 시간 t 동안 깊이 x만큼 식각됨 → E/R = x/t</p>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">물질별 일반적인 식각률 (ICP 기준)</h5>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-sm">
                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="font-semibold text-blue-700">Si</p>
                      <p className="text-2xl font-bold text-blue-900">100-300</p>
                      <p className="text-gray-600">nm/min</p>
                    </div>
                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="font-semibold text-green-700">SiO₂</p>
                      <p className="text-2xl font-bold text-green-900">50-150</p>
                      <p className="text-gray-600">nm/min</p>
                    </div>
                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="font-semibold text-purple-700">Si₃N₄</p>
                      <p className="text-2xl font-bold text-purple-900">40-120</p>
                      <p className="text-gray-600">nm/min</p>
                    </div>
                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="font-semibold text-orange-700">PR</p>
                      <p className="text-2xl font-bold text-orange-900">200-500</p>
                      <p className="text-gray-600">nm/min</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. 선택성 (Selectivity) */}
            <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-400">
              <h4 className="text-2xl font-bold text-green-800 mb-4">🎯 2. 선택성 (Selectivity)</h4>

              <div className="space-y-4">
                <div className="bg-green-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-green-900 mb-2">정의</h5>
                  <p className="text-gray-700">타겟 물질과 다른 물질(마스크, 하부층) 사이의 식각률 비율</p>
                  <div className="mt-3 p-3 bg-white rounded border-2 border-green-300">
                    <p className="font-mono text-center text-lg">Selectivity = 타겟 물질 식각률 / 기준 물질 식각률</p>
                    <p className="text-sm text-gray-600 text-center mt-2">예: Si:SiO₂ = 20:1 (Si가 SiO₂보다 20배 빠르게 식각)</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-blue-800 mb-3">선택비가 중요한 이유</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• <strong>마스크 보호:</strong> 높은 선택비로 PR 손실 최소화</li>
                      <li>• <strong>하부층 보호:</strong> 언더층 손상 방지</li>
                      <li>• <strong>공정 마진:</strong> End-point 여유 확보</li>
                      <li>• <strong>프로파일 제어:</strong> 측벽 손상 최소화</li>
                      <li>• <strong>수율 향상:</strong> 공정 안정성 증가</li>
                    </ul>
                  </div>

                  <div className="bg-purple-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-purple-800 mb-3">선택비 향상 방법</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• <strong>가스 조성 최적화:</strong> HBr 첨가 (Si 식각)</li>
                      <li>• <strong>폴리머 형성:</strong> 측벽 보호막 생성</li>
                      <li>• <strong>온도 제어:</strong> 저온에서 선택비 향상</li>
                      <li>• <strong>압력 조절:</strong> 화학적 반응 우세 조건</li>
                      <li>• <strong>바이어스 최적화:</strong> 이온 에너지 제어</li>
                    </ul>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">일반적인 선택비 예시</h5>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="p-2 text-left">식각 조합</th>
                          <th className="p-2 text-center">선택비</th>
                          <th className="p-2 text-left">주요 가스</th>
                          <th className="p-2 text-left">응용</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        <tr className="bg-white">
                          <td className="p-2">Si : SiO₂</td>
                          <td className="p-2 text-center font-bold text-blue-700">10-20 : 1</td>
                          <td className="p-2">Cl₂ + HBr</td>
                          <td className="p-2">Gate 식각</td>
                        </tr>
                        <tr className="bg-gray-50">
                          <td className="p-2">SiO₂ : Si</td>
                          <td className="p-2 text-center font-bold text-green-700">15-30 : 1</td>
                          <td className="p-2">CF₄ + CHF₃</td>
                          <td className="p-2">STI, Contact</td>
                        </tr>
                        <tr className="bg-white">
                          <td className="p-2">Si₃N₄ : SiO₂</td>
                          <td className="p-2 text-center font-bold text-purple-700">8-15 : 1</td>
                          <td className="p-2">CHF₃ + O₂</td>
                          <td className="p-2">Spacer</td>
                        </tr>
                        <tr className="bg-gray-50">
                          <td className="p-2">PR : Si</td>
                          <td className="p-2 text-center font-bold text-orange-700">∞ : 1</td>
                          <td className="p-2">O₂</td>
                          <td className="p-2">Ashing</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">선택성 개념도</h5>

                  <div className="mb-4">
                    <p className="text-sm leading-relaxed mb-2">
                      식각의 선택성이란 서로 다른 종류의 박막을 동일한 식각조건하에서 식각할때 각각의 박막에 대한 식각률의 상대적인 비율을 말함.
                    </p>
                    <div className="text-center my-3">
                      <div className="text-xl font-bold">
                        S<sub>A/B</sub> = <span className="text-lg">E<sub>A</sub></span>/<span className="text-lg">E<sub>B</sub></span>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-center items-center space-x-4">
                    {/* 왼쪽 그림 - 보라색 두께 두배, 녹색 살짝 채워짐 */}
                    <svg width="280" height="200" viewBox="0 0 300 200">
                      {/* 기판 (맨 아래 패턴) */}
                      <defs>
                        <pattern id="substrate_left" patternUnits="userSpaceOnUse" width="8" height="8">
                          <rect width="8" height="8" fill="white"/>
                          <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                        </pattern>
                      </defs>
                      <rect x="0" y="160" width="300" height="40" fill="url(#substrate_left)"/>

                      {/* 식각 대상물질 (초록색) - 전체 */}
                      <rect x="0" y="80" width="300" height="80" fill="#4CAF50"/>

                      {/* 마스크 (보라색) - 두께 두배 */}
                      <rect x="0" y="40" width="80" height="40" fill="#8E44AD"/>
                      <rect x="220" y="40" width="80" height="40" fill="#8E44AD"/>

                      {/* 식각된 영역 (하얀색) - 녹색 살짝 채워짐 */}
                      <rect x="80" y="40" width="140" height="80" fill="white"/>

                      {/* 세로 양방향 화살표와 x 표시 */}
                      <g>
                        {/* 세로 선 */}
                        <line x1="250" y1="85" x2="250" y2="115" stroke="black" strokeWidth="1.5"/>

                        {/* 위쪽 화살표 */}
                        <polygon points="250,85 247,90 253,90" fill="black"/>

                        {/* 아래쪽 화살표 */}
                        <polygon points="250,115 247,110 253,110" fill="black"/>

                        {/* x 표시 */}
                        <text x="255" y="105" fontSize="16" fill="black" fontWeight="bold">x</text>
                      </g>
                    </svg>

                    {/* 화살표 (왼쪽에서 오른쪽) */}
                    <div className="flex items-center">
                      <svg width="60" height="40" viewBox="0 0 60 40">
                        <defs>
                          <marker id="processArrow" markerWidth="10" markerHeight="7"
                                  refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#000" />
                          </marker>
                        </defs>
                        <line x1="5" y1="20" x2="50" y2="20" stroke="#000" strokeWidth="2"
                              markerEnd="url(#processArrow)"/>
                      </svg>
                    </div>

                    {/* 오른쪽 그림 - 식각 깊이 증가 */}
                    <svg width="280" height="200" viewBox="0 0 300 200">
                      {/* 기판 (맨 아래 패턴) */}
                      <defs>
                        <pattern id="substrate_right" patternUnits="userSpaceOnUse" width="8" height="8">
                          <rect width="8" height="8" fill="white"/>
                          <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                        </pattern>
                      </defs>
                      <rect x="0" y="160" width="300" height="40" fill="url(#substrate_right)"/>

                      {/* 식각 대상물질 (초록색) - 전체 */}
                      <rect x="0" y="80" width="300" height="80" fill="#4CAF50"/>

                      {/* 마스크 (보라색) */}
                      <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                      <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                      {/* 식각된 영역 (하얀색) - 더 깊게 식각 */}
                      <rect x="80" y="60" width="140" height="80" fill="white"/>

                      {/* A 표시 - 녹색 식각 깊이 */}
                      <g>
                        {/* 세로 선 */}
                        <line x1="250" y1="85" x2="250" y2="135" stroke="black" strokeWidth="1.5"/>

                        {/* 위쪽 화살표 */}
                        <polygon points="250,85 247,90 253,90" fill="black"/>

                        {/* 아래쪽 화살표 */}
                        <polygon points="250,135 247,130 253,130" fill="black"/>

                        {/* A 표시 */}
                        <text x="255" y="115" fontSize="16" fill="black" fontWeight="bold">A</text>
                      </g>

                      {/* B 표시 - 깎인 보라색 부분 */}
                      <g>
                        {/* 세로 선 - 첫번째 보라색 높이에서 두번째 보라색 높이까지 */}
                        <line x1="40" y1="40" x2="40" y2="60" stroke="black" strokeWidth="1.5"/>

                        {/* 위쪽 화살표 */}
                        <polygon points="40,40 37,45 43,45" fill="black"/>

                        {/* 아래쪽 화살표 */}
                        <polygon points="40,60 37,55 43,55" fill="black"/>

                        {/* B 표시 */}
                        <text x="45" y="55" fontSize="16" fill="black" fontWeight="bold">B</text>
                      </g>
                    </svg>
                  </div>

                  <div className="mt-4 text-sm text-gray-700">
                    <p className="text-center mb-2">
                      예) A라는 박막에 대한 <span className="text-red-500 underline">식각속도는 Ea</span>, B라는 박막에서는 동일한 <span className="text-red-500 underline">식각조건에서 Eb</span>라고 할때
                    </p>
                    <p className="text-center text-xs text-gray-600">
                      선택비 = A / B | 건식식각시 습식에 비하여 선택성이 좋지 못하기에 over etch를 하더라도 식각 대상물질이 아닌 막의 손상을 최소화하는 연구 진행
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* 3. 균일성 (Uniformity) */}
            <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-400">
              <h4 className="text-2xl font-bold text-blue-800 mb-4">⚖️ 3. 균일성 (Uniformity)</h4>

              <div className="space-y-4">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-blue-900 mb-2">정의</h5>
                  <p className="text-gray-700">웨이퍼 전체 영역에서 식각 특성(깊이, 프로파일)이 얼마나 일관적인지 나타내는 지표</p>
                  <div className="mt-3 p-3 bg-white rounded border-2 border-blue-300">
                    <p className="font-mono text-center text-lg">Uniformity (%) = ± [(Max - Min) / (2 × Average)] × 100</p>
                    <p className="text-sm text-gray-600 text-center mt-2">목표: ±3% 이내 (선단 공정)</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-red-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-red-800 mb-3">불균일성의 원인</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• <strong>플라즈마 분포:</strong> 중심/가장자리 밀도 차이</li>
                      <li>• <strong>가스 흐름:</strong> 불균일한 가스 공급</li>
                      <li>• <strong>온도 분포:</strong> 웨이퍼 온도 불균일</li>
                      <li>• <strong>전기장:</strong> RF 전력 분포 불균일</li>
                      <li>• <strong>챔버 형상:</strong> 기하학적 비대칭</li>
                    </ul>
                  </div>

                  <div className="bg-green-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-green-800 mb-3">균일성 개선 방법</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• <strong>압력 최적화:</strong> 충분히 높은 압력</li>
                      <li>• <strong>가스 주입 설계:</strong> 다중 주입구</li>
                      <li>• <strong>온도 제어:</strong> ESC 정밀 제어</li>
                      <li>• <strong>전극 설계:</strong> 대칭적 전극 구조</li>
                      <li>• <strong>회전:</strong> 웨이퍼 회전으로 평균화</li>
                    </ul>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">균일성 측정 및 평가</h5>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="bg-white p-4 rounded shadow-sm text-center">
                      <div className="text-3xl mb-2">📊</div>
                      <p className="font-semibold text-gray-800">측정 방법</p>
                      <p className="text-sm text-gray-600 mt-2">웨이퍼 49점/121점 측정</p>
                    </div>
                    <div className="bg-white p-4 rounded shadow-sm text-center">
                      <div className="text-3xl mb-2">🎯</div>
                      <p className="font-semibold text-gray-800">목표 균일성</p>
                      <p className="text-sm text-gray-600 mt-2">Logic: ±2%, Memory: ±3%</p>
                    </div>
                    <div className="bg-white p-4 rounded shadow-sm text-center">
                      <div className="text-3xl mb-2">⚡</div>
                      <p className="font-semibold text-gray-800">Trade-off</p>
                      <p className="text-sm text-gray-600 mt-2">속도 vs 균일성</p>
                    </div>
                  </div>
                </div>

                <div className="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-400">
                  <h5 className="font-semibold text-yellow-800 mb-2">💡 실무 Tip</h5>
                  <p className="text-sm text-gray-700">
                    압력을 높이면 평균 자유 행정이 짧아져 이온-분자 충돌이 증가하므로 균일성이 개선되지만,
                    대신 식각 속도가 감소하고 등방성 식각이 증가하여 프로파일이 나빠질 수 있습니다.
                    따라서 공정 목표에 따라 최적점을 찾아야 합니다.
                  </p>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">균일성 평가 개념도</h5>

                  <div className="mb-4 text-center">
                    <div className="text-lg mb-2">
                      Uniformity(%) = <span className="text-sm">
                        (max. etch rate - min. etch rate) / (max. etch rate + min. etch rate)
                      </span> × 100% &nbsp;&nbsp;or
                    </div>
                    <div className="text-lg">
                      = <span className="text-sm">
                        (max. etch rate - min. etch rate) / (2 × average etch rate)
                      </span> × 100%
                    </div>
                  </div>

                  <div className="flex justify-center">
                    <svg width="350" height="350" viewBox="0 0 280 280">
                      {/* 웨이퍼 원형 베이스 */}
                      <circle cx="140" cy="140" r="130" fill="#f0f0f0" stroke="#000" strokeWidth="2"/>

                      {/* 컬러 그라디언트 패턴들 */}
                      <defs>
                        <radialGradient id="etchGradient" cx="50%" cy="50%" r="50%">
                          <stop offset="0%" style={{stopColor: '#4a0080'}} />
                          <stop offset="15%" style={{stopColor: '#0000ff'}} />
                          <stop offset="30%" style={{stopColor: '#00ffff'}} />
                          <stop offset="45%" style={{stopColor: '#00ff00'}} />
                          <stop offset="60%" style={{stopColor: '#ffff00'}} />
                          <stop offset="75%" style={{stopColor: '#ff8000'}} />
                          <stop offset="90%" style={{stopColor: '#ff0000'}} />
                          <stop offset="100%" style={{stopColor: '#800000'}} />
                        </radialGradient>
                      </defs>

                      <circle cx="140" cy="140" r="125" fill="url(#etchGradient)"/>

                      {/* 격자 라인들 */}
                      {[...Array(8)].map((_, i) => {
                        const angle = (i * 45) * Math.PI / 180;
                        const x1 = 140 + 20 * Math.cos(angle);
                        const y1 = 140 + 20 * Math.sin(angle);
                        const x2 = 140 + 120 * Math.cos(angle);
                        const y2 = 140 + 120 * Math.sin(angle);
                        return (
                          <line key={`line-${i}`} x1={x1} y1={y1} x2={x2} y2={y2}
                                stroke="#000" strokeWidth="0.5" opacity="0.3"/>
                        );
                      })}

                      {[...Array(4)].map((_, i) => (
                        <circle key={`circle-${i}`} cx="140" cy="140" r={30 + i * 25}
                                fill="none" stroke="#000" strokeWidth="0.5" opacity="0.3"/>
                      ))}

                      {/* 측정 포인트들 */}
                      {[
                        {x: 140, y: 140, label: "35.4"},
                        {x: 80, y: 80, label: "32.1"},
                        {x: 200, y: 80, label: "28.9"},
                        {x: 200, y: 200, label: "31.2"},
                        {x: 80, y: 200, label: "33.8"},
                      ].map((point, i) => (
                        <g key={`point-${i}`}>
                          <circle cx={point.x} cy={point.y} r="3" fill="#000"/>
                          <text x={point.x} y={point.y - 8} fontSize="10" textAnchor="middle" fill="#000">
                            {point.label}
                          </text>
                        </g>
                      ))}
                    </svg>
                  </div>

                  {/* 범례 */}
                  <div className="mt-4 text-center">
                    <div className="inline-flex items-center space-x-2 text-xs">
                      <span>Etch Rate:</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#4a0080'}}></div>
                      <span>25</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#0000ff'}}></div>
                      <span>27</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#00ffff'}}></div>
                      <span>29</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#00ff00'}}></div>
                      <span>31</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#ffff00'}}></div>
                      <span>33</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#ff8000'}}></div>
                      <span>35</span>
                      <div className="w-4 h-3" style={{backgroundColor: '#ff0000'}}></div>
                      <span>37 nm/min</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 4. 이방도 (Anisotropy) */}
            <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-pink-400">
              <h4 className="text-2xl font-bold text-pink-800 mb-4">📐 4. 이방도 (Anisotropy)</h4>

              <div className="space-y-4">
                <div className="bg-pink-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-pink-900 mb-2">정의</h5>
                  <p className="text-gray-700">마스크 패턴의 충실도를 나타내는 지표. 수직 방향과 수평 방향의 식각 속도 차이</p>
                  <div className="mt-3 p-3 bg-white rounded border-2 border-pink-300">
                    <p className="font-mono text-center text-lg">Anisotropy = 1 - (수평 식각률 / 수직 식각률)</p>
                    <p className="text-sm text-gray-600 text-center mt-2">A = 1 (완전 이방성), A = 0 (완전 등방성)</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-blue-800 mb-3">이방성 식각 (Anisotropic)</h5>
                    <div className="space-y-2 text-sm text-gray-700">
                      <p className="font-semibold text-blue-900">특징:</p>
                      <ul className="space-y-1 ml-4">
                        <li>• 수직 방향으로만 식각</li>
                        <li>• 마스크 패턴 그대로 전사</li>
                        <li>• 수직 프로파일 (90°)</li>
                        <li>• 물리적 스퍼터링 우세</li>
                      </ul>
                      <p className="font-semibold text-blue-900 mt-3">조건:</p>
                      <ul className="space-y-1 ml-4">
                        <li>• 저압력 (10-50 mTorr)</li>
                        <li>• 고 바이어스 전압</li>
                        <li>• 방향성 이온 충격</li>
                        <li>• ICP 장비 사용</li>
                      </ul>
                      <p className="font-semibold text-blue-900 mt-3">응용:</p>
                      <ul className="space-y-1 ml-4">
                        <li>• Gate 식각</li>
                        <li>• Contact/Via 형성</li>
                        <li>• MEMS, TSV</li>
                      </ul>
                    </div>
                  </div>

                  <div className="bg-orange-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-orange-800 mb-3">등방성 식각 (Isotropic)</h5>
                    <div className="space-y-2 text-sm text-gray-700">
                      <p className="font-semibold text-orange-900">특징:</p>
                      <ul className="space-y-1 ml-4">
                        <li>• 모든 방향으로 균일하게 식각</li>
                        <li>• 언더컷(undercut) 발생</li>
                        <li>• 둥근 프로파일</li>
                        <li>• 화학적 반응 우세</li>
                      </ul>
                      <p className="font-semibold text-orange-900 mt-3">조건:</p>
                      <ul className="space-y-1 ml-4">
                        <li>• 고압력 (>100 mTorr)</li>
                        <li>• 저 바이어스 전압</li>
                        <li>• 라디칼 반응 우세</li>
                        <li>• 습식 식각</li>
                      </ul>
                      <p className="font-semibold text-orange-900 mt-3">응용:</p>
                      <ul className="space-y-1 ml-4">
                        <li>• Spacer 형성</li>
                        <li>• Recess 식각</li>
                        <li>• 클리닝</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">프로파일 제어</h5>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-center text-sm">
                    <div className="bg-white p-3 rounded shadow-sm">
                      <div className="text-3xl mb-2">📏</div>
                      <p className="font-semibold">Vertical</p>
                      <p className="text-gray-600">90° 프로파일</p>
                      <p className="text-xs text-blue-600 mt-1">A ~ 1.0</p>
                    </div>
                    <div className="bg-white p-3 rounded shadow-sm">
                      <div className="text-3xl mb-2">📐</div>
                      <p className="font-semibold">Tapered</p>
                      <p className="text-gray-600">경사 프로파일</p>
                      <p className="text-xs text-green-600 mt-1">0.7 &lt; A &lt; 0.9</p>
                    </div>
                    <div className="bg-white p-3 rounded shadow-sm">
                      <div className="text-3xl mb-2">🌙</div>
                      <p className="font-semibold">Undercut</p>
                      <p className="text-gray-600">언더컷</p>
                      <p className="text-xs text-orange-600 mt-1">0.3 &lt; A &lt; 0.7</p>
                    </div>
                    <div className="bg-white p-3 rounded shadow-sm">
                      <div className="text-3xl mb-2">⭕</div>
                      <p className="font-semibold">Isotropic</p>
                      <p className="text-gray-600">등방성</p>
                      <p className="text-xs text-red-600 mt-1">A ~ 0</p>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">이방도별 식각 프로파일</h5>

                  <div className="mb-6">
                    <svg width="100%" height="400" viewBox="0 0 800 400">
                      {/* 상단 마스크와 언더컷 다이어그램 */}
                      <g>
                        <text x="90" y="20" fontSize="12" textAnchor="middle" fontWeight="bold">mask</text>

                        {/* 언더컷 형상 - 마스크 중앙에서 아래로 향하는 엷은 회색 삼각형 */}
                        <polygon points="90,35 50,75 130,75" fill="#d3d3d3"/>

                        {/* 마스크 (회색 사각형) - 삼각형 위에 다시 그려서 중첩 부분 덮기 */}
                        <rect x="50" y="30" width="80" height="25" fill="#999"/>

                        {/* 언더컷 라벨 - 그림 오른쪽에 배치 */}
                        <path d="M 115 60 L 140 58" stroke="#000" strokeWidth="1" fill="none"/>
                        <text x="145" y="62" fontSize="10">undercut</text>
                      </g>

                      {/* 이방성 공식 */}
                      <g transform="translate(50, 120)">
                        <text x="0" y="0" fontSize="16" fontWeight="bold">A = 1 - R<tspan baselineShift="sub">l</tspan>/R<tspan baselineShift="sub">v</tspan></text>
                        <text x="200" y="0" fontSize="14">A=0, isotropic etching</text>
                        <text x="200" y="20" fontSize="14">A=1, anisotropic etching</text>
                        <text x="0" y="40" fontSize="12" fill="red">R<tspan baselineShift="sub">L</tspan>: lateral etch rate</text>
                        <text x="0" y="55" fontSize="12" fill="red">R<tspan baselineShift="sub">v</tspan>: vertical etch rate</text>
                      </g>

                      {/* 식각률 다이어그램 (우측 상단) */}
                      <g transform="translate(450, 50)">
                        <svg width="200" height="130" viewBox="0 0 300 200">
                          {/* 기판 (맨 아래 패턴) */}
                          <defs>
                            <pattern id="substrate_aniso" patternUnits="userSpaceOnUse" width="8" height="8">
                              <rect width="8" height="8" fill="white"/>
                              <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                            </pattern>
                          </defs>
                          <rect x="0" y="160" width="300" height="40" fill="url(#substrate_aniso)"/>

                          {/* 식각 대상물질 (회색) - 전체 */}
                          <rect x="0" y="80" width="300" height="80" fill="#808080"/>

                          {/* 마스크 (보라색) */}
                          <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                          <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                          {/* 파인 부분도 모두 회색으로 채움 - x 표시 없음 */}
                          <rect x="80" y="80" width="140" height="80" fill="#808080"/>
                        </svg>
                      </g>

                      {/* 하단 3개 구조들 - 우측 상단 스타일로 통일 */}
                      <g transform="translate(50, 200)">
                        {/* Isotropic Etch - 반원형 형태로 파임 */}
                        <g>
                          <svg width="160" height="130" viewBox="0 0 300 200">
                            {/* 기판 패턴 */}
                            <defs>
                              <pattern id="substrate_iso" patternUnits="userSpaceOnUse" width="8" height="8">
                                <rect width="8" height="8" fill="white"/>
                                <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                              </pattern>
                            </defs>
                            <rect x="0" y="160" width="300" height="40" fill="url(#substrate_iso)"/>

                            {/* 식각 대상물질 (회색) */}
                            <rect x="0" y="80" width="300" height="80" fill="#808080"/>

                            {/* 마스크 (보라색) */}
                            <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                            <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                            {/* 등방성 식각 - 타원 중심을 위로 올려서 아래 회색 부분이 보이도록 */}
                            <ellipse cx="150" cy="90" rx="80" ry="60" fill="white"/>

                            {/* 마스크 재적용 - 식각되지 않는 보라색 마스크 */}
                            <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                            <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>
                          </svg>
                          <text x="80" y="150" fontSize="12" textAnchor="middle" fontWeight="bold" fill="green">Isotropic Etch</text>
                        </g>

                        {/* Directional Etch - 경사진 형태 */}
                        <g transform="translate(200, 0)">
                          <svg width="160" height="130" viewBox="0 0 300 200">
                            {/* 기판 패턴 */}
                            <defs>
                              <pattern id="substrate_dir" patternUnits="userSpaceOnUse" width="8" height="8">
                                <rect width="8" height="8" fill="white"/>
                                <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                              </pattern>
                            </defs>
                            <rect x="0" y="160" width="300" height="40" fill="url(#substrate_dir)"/>

                            {/* 식각 대상물질 (회색) */}
                            <rect x="0" y="80" width="300" height="80" fill="#808080"/>

                            {/* 마스크 (보라색) */}
                            <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                            <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                            {/* 방향성 식각 - 경사진 형태 */}
                            <polygon points="80,80 100,160 200,160 220,80" fill="white"/>
                          </svg>
                          <text x="80" y="150" fontSize="12" textAnchor="middle" fontWeight="bold" fill="green">Directional Etch</text>
                        </g>

                        {/* Vertical Etch - 수직 형태 */}
                        <g transform="translate(400, 0)">
                          <svg width="160" height="130" viewBox="0 0 300 200">
                            {/* 기판 패턴 */}
                            <defs>
                              <pattern id="substrate_ver" patternUnits="userSpaceOnUse" width="8" height="8">
                                <rect width="8" height="8" fill="white"/>
                                <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#000" strokeWidth="0.5"/>
                              </pattern>
                            </defs>
                            <rect x="0" y="160" width="300" height="40" fill="url(#substrate_ver)"/>

                            {/* 식각 대상물질 (회색) */}
                            <rect x="0" y="80" width="300" height="80" fill="#808080"/>

                            {/* 마스크 (보라색) */}
                            <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                            <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                            {/* 수직 식각 - 바닥에 회색 남김 */}
                            <rect x="80" y="80" width="140" height="40" fill="white"/>

                            {/* 바닥에 남은 회색 물질 - 마스크 두께의 두배 */}
                            <rect x="80" y="120" width="140" height="40" fill="#808080"/>
                          </svg>
                          <text x="80" y="150" fontSize="12" textAnchor="middle" fontWeight="bold" fill="green">Vertical Etch</text>
                        </g>
                      </g>
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* 5. Loading Effect */}
            <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-purple-400">
              <h4 className="text-2xl font-bold text-purple-800 mb-4">🔄 5. Loading Effect (로딩 효과)</h4>

              <div className="space-y-4">
                <div className="bg-purple-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-purple-900 mb-2">정의</h5>
                  <p className="text-gray-700">
                    패턴 밀도(open area ratio)에 따라 식각 속도가 달라지는 현상.
                    식각되는 면적이 클수록 반응 가스가 빠르게 소모되어 식각 속도가 감소합니다.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-red-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-red-800 mb-3">발생 원인</h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      <li>• <strong>Reactant Depletion:</strong> 반응 가스의 국부적 소모</li>
                      <li>• <strong>Product Accumulation:</strong> 반응 부산물의 축적</li>
                      <li>• <strong>Ion Shadowing:</strong> 이온 플럭스 불균일</li>
                      <li>• <strong>Radical Loss:</strong> 라디칼 재결합/확산</li>
                      <li>• <strong>Temperature Rise:</strong> 고밀도 영역 온도 상승</li>
                    </ul>
                  </div>

                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h5 className="font-semibold text-blue-800 mb-3">Loading Effect 종류</h5>
                    <div className="space-y-3 text-sm">
                      <div className="bg-white p-2 rounded">
                        <p className="font-semibold text-blue-900">Macro Loading</p>
                        <p className="text-gray-700">웨이퍼 간 또는 웨이퍼 내 대면적 차이</p>
                      </div>
                      <div className="bg-white p-2 rounded">
                        <p className="font-semibold text-blue-900">Micro Loading</p>
                        <p className="text-gray-700">미세 패턴 간 밀도 차이 (수십 μm)</p>
                      </div>
                      <div className="bg-white p-2 rounded">
                        <p className="font-semibold text-blue-900">ARDE Effect</p>
                        <p className="text-gray-700">Aspect Ratio에 따른 식각률 변화</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-green-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-green-800 mb-3">개선 방법</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="font-semibold text-green-900 mb-2">공정 조건 최적화:</p>
                      <ul className="space-y-1 text-gray-700 ml-4">
                        <li>• 가스 유량 증가 (충분한 공급)</li>
                        <li>• 압력 최적화</li>
                        <li>• Over-etch 시간 조절</li>
                        <li>• 다단계 식각 (main + soft)</li>
                      </ul>
                    </div>
                    <div>
                      <p className="font-semibold text-green-900 mb-2">설계 최적화:</p>
                      <ul className="space-y-1 text-gray-700 ml-4">
                        <li>• Dummy pattern 추가</li>
                        <li>• 패턴 밀도 균일화</li>
                        <li>• OPC (Optical Proximity Correction)</li>
                        <li>• 레이아웃 최적화</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold text-gray-800 mb-3">실제 영향 예시</h5>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="p-2 text-left">패턴 밀도</th>
                          <th className="p-2 text-center">상대 식각률</th>
                          <th className="p-2 text-left">문제점</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        <tr className="bg-white">
                          <td className="p-2">High Density (80%)</td>
                          <td className="p-2 text-center font-bold text-red-700">0.7-0.8×</td>
                          <td className="p-2">Under-etch, Residue</td>
                        </tr>
                        <tr className="bg-gray-50">
                          <td className="p-2">Medium Density (50%)</td>
                          <td className="p-2 text-center font-bold text-green-700">1.0×</td>
                          <td className="p-2">기준 (정상)</td>
                        </tr>
                        <tr className="bg-white">
                          <td className="p-2">Low Density (20%)</td>
                          <td className="p-2 text-center font-bold text-blue-700">1.1-1.3×</td>
                          <td className="p-2">Over-etch, 손상</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-400">
                  <h5 className="font-semibold text-yellow-800 mb-2">💡 실무에서</h5>
                  <p className="text-sm text-gray-700">
                    Loading Effect는 특히 대면적 DRAM이나 고밀도 Logic 소자에서 심각한 문제가 됩니다.
                    예를 들어, DRAM의 Cell Array(고밀도)와 Periphery(저밀도) 사이에 20-30%의 식각률 차이가 발생할 수 있어,
                    Dummy Pattern을 삽입하거나 다단계 식각 공정을 사용하여 보상해야 합니다.
                  </p>
                </div>

                {/* 마이크로 로딩 효과 */}
                <div className="mb-6 p-4 bg-blue-50 rounded-lg">
                  <h3 className="text-xl font-bold mb-3 text-blue-800">마이크로 로딩 효과 (Micro Loading Effect)</h3>

                  <div className="mb-4 space-y-2 text-sm">
                    <div>
                      <span className="font-semibold text-blue-700">정의:</span> 패턴이 좁고 깊어지면서 발생하는 현상. 좁은 패턴 내부로 반응물은 들어가지만, 부산물이 제대로 배출되지 않아 식각 속도가 느려짐.
                    </div>
                    <div>
                      <span className="font-semibold text-blue-700">원인:</span> 좁고 깊은 패턴 내에서 부산물(Byproduct)의 배출(Pump Out) 속도 차이 때문에 발생.
                    </div>
                    <div>
                      <span className="font-semibold text-blue-700">해결 방법:</span>
                      <ul className="list-disc list-inside ml-4 mt-1">
                        <li>공정 압력 조절: 압력을 낮춰 반응물 및 부산물의 잔류 시간 감소</li>
                        <li>펄싱 식각 기법: 플라즈마를 켜고 끄는 펄싱 기법으로 Off 상태에서 부산물 배출 시간 확보</li>
                      </ul>
                    </div>
                  </div>

                  <div className="flex justify-center mb-4">
                    <svg width="100%" height="200" viewBox="0 0 300 200">
                      {/* 기판 (맨 아래 패턴) */}
                      <defs>
                        <pattern id="substrate_micro" patternUnits="userSpaceOnUse" width="2" height="2">
                          <rect width="2" height="2" fill="white"/>
                          <path d="M0,2 L2,0 M-0.5,0.5 L0.5,-0.5 M1.5,2.5 L2.5,1.5" stroke="#000" strokeWidth="0.2"/>
                        </pattern>
                      </defs>
                      <rect x="0" y="160" width="300" height="40" fill="url(#substrate_micro)"/>

                      {/* 식각 대상물질 (초록색) */}
                      <rect x="0" y="80" width="300" height="80" fill="#4CAF50"/>

                      {/* 마스크 (보라색) */}
                      <rect x="0" y="60" width="80" height="20" fill="#8E44AD"/>
                      <rect x="220" y="60" width="80" height="20" fill="#8E44AD"/>

                      {/* 식각된 영역들 - 4개의 좁은 패턴 + 1개의 넓은 패턴 (파란 배경색) */}
                      <rect x="20" y="60" width="20" height="80" fill="#EFF6FF"/>
                      <rect x="60" y="60" width="20" height="80" fill="#EFF6FF"/>
                      <rect x="100" y="60" width="20" height="80" fill="#EFF6FF"/>
                      <rect x="140" y="60" width="20" height="80" fill="#EFF6FF"/>
                      <rect x="200" y="60" width="60" height="90" fill="#EFF6FF"/>

                      {/* 보라색 마스크 재적용 */}
                      <rect x="0" y="60" width="20" height="20" fill="#8E44AD"/>
                      <rect x="40" y="60" width="20" height="20" fill="#8E44AD"/>
                      <rect x="80" y="60" width="20" height="20" fill="#8E44AD"/>
                      <rect x="120" y="60" width="20" height="20" fill="#8E44AD"/>
                      <rect x="160" y="60" width="40" height="20" fill="#8E44AD"/>
                      <rect x="260" y="60" width="40" height="20" fill="#8E44AD"/>

                      {/* 작은 패턴들 안의 위쪽 화살표 - 첫 번째 패턴 */}
                      <g>
                        <line x1="30" y1="125" x2="30" y2="70" stroke="black" strokeWidth="1.2"/>
                        <polygon points="30,70 27,75 33,75" fill="black"/>
                      </g>

                      {/* 두 번째 패턴 */}
                      <g>
                        <line x1="70" y1="125" x2="70" y2="70" stroke="black" strokeWidth="1.2"/>
                        <polygon points="70,70 67,75 73,75" fill="black"/>
                      </g>

                      {/* 세 번째 패턴 */}
                      <g>
                        <line x1="110" y1="125" x2="110" y2="70" stroke="black" strokeWidth="1.2"/>
                        <polygon points="110,70 107,75 113,75" fill="black"/>
                      </g>

                      {/* 네 번째 패턴 */}
                      <g>
                        <line x1="150" y1="125" x2="150" y2="70" stroke="black" strokeWidth="1.2"/>
                        <polygon points="150,70 147,75 153,75" fill="black"/>
                      </g>

                      {/* B 표시 - 넓은 패턴 깊이 (더 깊음) - 위쪽 화살표만 */}
                      <g>
                        <line x1="230" y1="135" x2="230" y2="70" stroke="black" strokeWidth="1.5"/>
                        <polygon points="230,70 227,75 233,75" fill="black"/>
                      </g>

                      {/* The Difference of Pump out rate 텍스트 */}
                      <text x="150" y="50" fontSize="11" textAnchor="middle" fill="black" fontWeight="bold">The Difference of Pump out rate</text>
                    </svg>
                  </div>
                  <p className="text-xs text-center text-gray-600">좁은 패턴(A)은 부산물 배출이 어려워 식각이 느리고, 넓은 패턴(B)은 배출이 원활하여 더 깊게 식각됨</p>
                </div>

                {/* 매크로 로딩 효과 */}
                <div className="mb-6 p-4 bg-green-50 rounded-lg">
                  <h3 className="text-xl font-bold mb-3 text-green-800">매크로 로딩 효과 (Macro Loading Effect)</h3>

                  <div className="mb-4 space-y-2 text-sm">
                    <div>
                      <span className="font-semibold text-green-700">정의:</span> 식각 면적의 패턴 밀도가 전체적으로 달라질 때 발생. 단위 면적당 반응물이 부족해져, 넓은 영역의 식각 속도가 느려지고 좁은 패턴의 식각 속도는 빨라지는 현상.
                    </div>
                    <div>
                      <span className="font-semibold text-green-700">원인:</span> 일정하게 공급되는 반응 가스가 면적 전체에 고르게 공급되지 못해 발생.
                    </div>
                    <div>
                      <span className="font-semibold text-green-700">해결 방법:</span>
                      <ul className="list-disc list-inside ml-4 mt-1">
                        <li>공정 조건 조절: 압력을 높여 반응 가스 공급을 원활하게 하거나, Bias Power를 감소시켜 고에너지 이온 영향 감소</li>
                        <li>더미 패턴 삽입: 넓은 영역에 더미(dummy) 패턴을 삽입하여 패턴 밀도를 균일하게 조정</li>
                      </ul>
                    </div>
                  </div>

                  <div className="flex justify-center mb-4">
                    <svg width="100%" height="240" viewBox="0 0 400 240">
                      {/* 기판 (맨 아래 패턴) */}
                      <defs>
                        <pattern id="substrate_macro_new" patternUnits="userSpaceOnUse" width="2" height="2">
                          <rect width="2" height="2" fill="white"/>
                          <path d="M0,2 L2,0 M-0.5,0.5 L0.5,-0.5 M1.5,2.5 L2.5,1.5" stroke="#000" strokeWidth="0.2"/>
                        </pattern>
                      </defs>
                      <rect x="0" y="200" width="400" height="40" fill="url(#substrate_macro_new)"/>

                      {/* 식각 대상물질 (초록색) */}
                      <rect x="0" y="100" width="400" height="100" fill="#4CAF50"/>

                      {/* 왼쪽: 좁은 홀들 (패턴 밀도 높음) - 위에서 아래까지 완전히 뚫림 - 초록색 배경 */}
                      <rect x="20" y="0" width="18" height="170" fill="#f0fdf4"/>
                      <rect x="50" y="0" width="18" height="170" fill="#f0fdf4"/>
                      <rect x="80" y="0" width="18" height="170" fill="#f0fdf4"/>
                      <rect x="110" y="0" width="18" height="170" fill="#f0fdf4"/>

                      {/* 오른쪽: 넓은 홀 (패턴 밀도 낮음) - 더 얕게 식각됨 - 초록색 배경 */}
                      <rect x="220" y="0" width="100" height="140" fill="#f0fdf4"/>

                      {/* 보라색 마스크들 - 뚫리지 않은 부분에만 배치 */}
                      {/* 맨 왼쪽 */}
                      <rect x="0" y="100" width="20" height="15" fill="#8E44AD"/>
                      {/* 첫번째와 두번째 홀 사이 */}
                      <rect x="38" y="100" width="12" height="15" fill="#8E44AD"/>
                      {/* 두번째와 세번째 홀 사이 */}
                      <rect x="68" y="100" width="12" height="15" fill="#8E44AD"/>
                      {/* 세번째와 네번째 홀 사이 */}
                      <rect x="98" y="100" width="12" height="15" fill="#8E44AD"/>
                      {/* 네번째 홀 후부터 오른쪽 큰 홀 전까지 */}
                      <rect x="128" y="100" width="92" height="15" fill="#8E44AD"/>
                      {/* 오른쪽 영역 - 큰 홀 오른쪽 */}
                      <rect x="320" y="100" width="80" height="15" fill="#8E44AD"/>

                      {/* The difference of Etchant Concentration per Unit Area 텍스트 */}
                      <text x="200" y="90" fontSize="11" textAnchor="middle" fill="black" fontWeight="bold">The difference of Etchant Concentration per Unit Area</text>
                    </svg>
                  </div>
                  <p className="text-xs text-center text-gray-600">
                    왼쪽: 패턴 밀도가 높아 반응물이 분산되어 얕게 식각됨 | 오른쪽: 패턴 밀도가 낮아 반응물이 집중되어 깊게 식각됨
                  </p>
                </div>

                {/* 비교 표 */}
                <div className="mt-6">
                  <h3 className="text-lg font-bold mb-3 text-center">마이크로 vs 매크로 로딩 효과 비교</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse border border-gray-300 text-sm">
                      <thead className="bg-gray-100">
                        <tr>
                          <th className="border border-gray-300 px-4 py-2">구분</th>
                          <th className="border border-gray-300 px-4 py-2 bg-blue-50">마이크로 로딩</th>
                          <th className="border border-gray-300 px-4 py-2 bg-green-50">매크로 로딩</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td className="border border-gray-300 px-4 py-2 font-semibold">발생 원인</td>
                          <td className="border border-gray-300 px-4 py-2">좁고 깊은 패턴 내 부산물 배출 지연</td>
                          <td className="border border-gray-300 px-4 py-2">패턴 밀도 차이로 인한 반응물 공급 부족</td>
                        </tr>
                        <tr>
                          <td className="border border-gray-300 px-4 py-2 font-semibold">영향</td>
                          <td className="border border-gray-300 px-4 py-2">좁은 패턴 내부의 식각 속도 저하</td>
                          <td className="border border-gray-300 px-4 py-2">넓은 영역과 좁은 패턴의 식각 속도 차이</td>
                        </tr>
                        <tr>
                          <td className="border border-gray-300 px-4 py-2 font-semibold">주요 해결책</td>
                          <td className="border border-gray-300 px-4 py-2">압력 감소, 펄싱 식각 기법</td>
                          <td className="border border-gray-300 px-4 py-2">압력 증가, Bias Power 감소, 더미 패턴 삽입</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

            {/* 요약 */}
            <div className="bg-gradient-to-r from-blue-50 via-purple-50 to-pink-50 p-6 rounded-lg border-2 border-indigo-200">
              <h4 className="text-xl font-bold text-indigo-900 mb-4">🎯 5대 요소 종합 정리</h4>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-sm text-center">
                <div className="bg-white p-3 rounded-lg shadow">
                  <div className="text-2xl mb-2">⚡</div>
                  <p className="font-semibold text-yellow-800">식각률</p>
                  <p className="text-xs text-gray-600 mt-1">생산성</p>
                </div>
                <div className="bg-white p-3 rounded-lg shadow">
                  <div className="text-2xl mb-2">🎯</div>
                  <p className="font-semibold text-green-800">선택성</p>
                  <p className="text-xs text-gray-600 mt-1">공정 마진</p>
                </div>
                <div className="bg-white p-3 rounded-lg shadow">
                  <div className="text-2xl mb-2">⚖️</div>
                  <p className="font-semibold text-blue-800">균일성</p>
                  <p className="text-xs text-gray-600 mt-1">수율</p>
                </div>
                <div className="bg-white p-3 rounded-lg shadow">
                  <div className="text-2xl mb-2">📐</div>
                  <p className="font-semibold text-pink-800">이방도</p>
                  <p className="text-xs text-gray-600 mt-1">패턴 충실도</p>
                </div>
                <div className="bg-white p-3 rounded-lg shadow">
                  <div className="text-2xl mb-2">🔄</div>
                  <p className="font-semibold text-purple-800">로딩효과</p>
                  <p className="text-xs text-gray-600 mt-1">밀도 보상</p>
                </div>
              </div>
              <p className="text-center text-gray-700 mt-4">
                이 5가지 요소는 서로 연관되어 있으며, 최적의 공정을 위해서는 trade-off를 고려한 균형 잡힌 설정이 필요합니다.
              </p>
            </div>
          </div>
        );

      case 'process':
        return (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-6 rounded-lg">
              <h3 className="text-xl font-bold text-green-800 mb-4">🧪 식각 원리 시뮬레이션</h3>
              <p className="text-gray-700">
                실제 식각 장비를 조작하여 다양한 물질의 식각 원리를 체험해보세요.
                가스 조성, 압력, 파워 등을 조절하며 화학 반응과 물리적 메커니즘을 이해해보세요.
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold mb-4">식각 타겟 및 장비 선택</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                {Object.keys(gasPresets).map((target) => {
                  const equipmentInfo = {
                    'Si': {
                      equipment: 'ICP',
                      pressureRange: '5-50 mTorr',
                      powerRange: '300-800 W',
                      reason: '높은 선택비와 정밀한 프로파일 제어 필요',
                      applications: 'Gate, MEMS, TSV',
                      color: 'blue'
                    },
                    'SiO2': {
                      equipment: 'CCP/ICP',
                      pressureRange: '30-100 mTorr',
                      powerRange: '400-1000 W',
                      reason: '물리+화학적 복합 작용으로 빠른 식각',
                      applications: 'STI, IMD, Contact',
                      color: 'green'
                    },
                    'Si3N4': {
                      equipment: 'ICP',
                      pressureRange: '10-30 mTorr',
                      powerRange: '200-600 W',
                      reason: '강한 결합으로 높은 플라즈마 밀도 필요',
                      applications: 'Spacer, Hard Mask',
                      color: 'purple'
                    },
                    'PR': {
                      equipment: 'CCP',
                      pressureRange: '100-300 mTorr',
                      powerRange: '100-500 W',
                      reason: '유기물 제거에 물리적 충격 효과적',
                      applications: 'Strip, Descum',
                      color: 'orange'
                    }
                  };

                  const info = equipmentInfo[target];

                  return (
                    <button
                      key={target}
                      onClick={() => {
                        setEtchTarget(target);
                        setGasFlows(gasPresets[target]);
                        setEndpointDetected(false);
                        setEtchRate(0);
                        setSelectivity(0);
                        setUniformity(0);
                        setEtchDepth(0);
                      }}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        etchTarget === target
                          ? `border-${info.color}-500 bg-${info.color}-50`
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="text-left">
                        <h5 className={`text-lg font-semibold text-${info.color}-800 mb-2`}>
                          {target} 식각
                        </h5>
                        <div className="text-sm space-y-1">
                          <p><strong>장비:</strong> {info.equipment}</p>
                          <p><strong>압력:</strong> {info.pressureRange}</p>
                          <p><strong>파워:</strong> {info.powerRange}</p>
                          <p><strong>이유:</strong> {info.reason}</p>
                          <p><strong>응용:</strong> {info.applications}</p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h5 className="font-semibold text-gray-800 mb-2">선택된 타겟: {etchTarget}</h5>
                <p className="text-sm text-gray-600">
                  {etchTarget === 'Si' && '실리콘 식각: 게이트, MEMS, TSV 등에 사용되는 핵심 공정'}
                  {etchTarget === 'SiO2' && '산화막 식각: STI, IMD, Contact 형성에 필수적'}
                  {etchTarget === 'Si3N4' && '질화막 식각: Spacer, Hard Mask 등 고선택비 요구'}
                  {etchTarget === 'PR' && 'PR Ashing: 식각 후 잔여 포토레지스트 완전 제거'}
                </p>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold mb-4">화학 반응 메커니즘</h4>

              <div className="mb-6">
                {etchTarget === 'Si' && (
                  <div className="space-y-4">
                    <div className="bg-white p-4 rounded border-l-4 border-blue-400">
                      <h6 className="font-semibold text-blue-800 mb-2">주요 반응 가스: Cl2 (염소)</h6>
                      <div className="text-sm space-y-2">
                        <p><strong>화학 반응식:</strong></p>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center">
                          Si + 2Cl₂ → SiCl₄ ↑
                        </div>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center mt-1">
                          Si + Ar⁺ → Si⁺ (물리적 스퍼터링)
                        </div>
                        <p><strong>메커니즘:</strong> Cl 라디칼이 Si 표면과 화학적으로 결합하여 휘발성 SiCl₄ 형성</p>
                        <p><strong>생성물:</strong> SiCl₄ (사염화규소) - 상온에서 기체상으로 쉽게 배출</p>
                        <p><strong>HBr 첨가 효과:</strong> 산화막과의 선택비 향상 (Si:SiO₂ = 20:1)</p>
                      </div>
                    </div>
                    <div className="bg-yellow-50 p-3 rounded">
                      <p className="text-sm text-gray-700">
                        <strong>왜 Cl₂인가?</strong> SiCl₄는 상온에서 기체상태로 쉽게 배출되며,
                        Si와의 반응성이 높아 빠른 식각이 가능합니다.
                      </p>
                    </div>
                  </div>
                )}

                {etchTarget === 'SiO2' && (
                  <div className="space-y-4">
                    <div className="bg-white p-4 rounded border-l-4 border-blue-400">
                      <h6 className="font-semibold text-blue-800 mb-2">주요 반응 가스: CF4, CHF3 (불소 화합물)</h6>
                      <div className="text-sm space-y-2">
                        <p><strong>화학 반응식:</strong></p>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center">
                          SiO₂ + 4CF₄ → SiF₄ ↑ + 2CO₂ ↑ + 2CF₂
                        </div>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center mt-1">
                          SiO₂ + CHF₃ → SiF₄ ↑ + CO ↑ + HF
                        </div>
                        <p><strong>메커니즘:</strong> F 라디칼이 Si-O 결합을 끊고 Si와 강한 Si-F 결합 형성</p>
                        <p><strong>생성물:</strong> SiF₄ (사불화규소) - 매우 안정한 휘발성 기체</p>
                        <p><strong>첨가 가스:</strong> H₂ (폴리머 형성), O₂ (폴리머 제거)</p>
                      </div>
                    </div>
                    <div className="bg-yellow-50 p-3 rounded">
                      <p className="text-sm text-gray-700">
                        <strong>왜 F계인가?</strong> Si-F 결합이 매우 강하고(565 kJ/mol) SiF₄가
                        안정한 기체상으로 쉽게 배출되어 산화막 식각에 최적화되어 있습니다.
                      </p>
                    </div>
                  </div>
                )}

                {etchTarget === 'Si3N4' && (
                  <div className="space-y-4">
                    <div className="bg-white p-4 rounded border-l-4 border-purple-400">
                      <h6 className="font-semibold text-purple-800 mb-2">주요 반응 가스: CHF3 + O2</h6>
                      <div className="text-sm space-y-2">
                        <p><strong>화학 반응식:</strong></p>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center">
                          Si₃N₄ + 12CHF₃ → 3SiF₄ ↑ + 2N₂ ↑ + 12CO ↑ + 12HF
                        </div>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center mt-1">
                          C + O₂ → CO₂ ↑ (탄소 부산물 제거)
                        </div>
                        <p><strong>메커니즘:</strong> F 라디칼이 Si-N 결합 공격, O₂가 탄소 부산물 제거</p>
                        <p><strong>생성물:</strong> SiF₄, N₂ (안정한 기체들로 배출)</p>
                        <p><strong>O₂ 첨가 이유:</strong> CHF₃ 분해 시 생성되는 탄소 제거</p>
                      </div>
                    </div>
                    <div className="bg-yellow-50 p-3 rounded">
                      <p className="text-sm text-gray-700">
                        <strong>왜 O₂ 첨가?</strong> 질화막 식각 시 생성되는 탄소 부산물이
                        식각을 방해하므로 O₂로 CO₂ 형태로 제거해야 합니다.
                      </p>
                    </div>
                  </div>
                )}

                {etchTarget === 'PR' && (
                  <div className="space-y-4">
                    <div className="bg-white p-4 rounded border-l-4 border-orange-400">
                      <h6 className="font-semibold text-orange-800 mb-2">주요 반응 가스: O2 (산소)</h6>
                      <div className="text-sm space-y-2">
                        <p><strong>화학 반응식:</strong></p>
                        <div className="bg-gray-100 p-2 rounded font-mono text-center">
                          (CH₂-CHR)ₙ + O₂ → CO₂ ↑ + H₂O ↑
                        </div>
                        <p><strong>메커니즘:</strong> O 라디칼이 C-C, C-H 결합을 무작위로 절단</p>
                        <p><strong>생성물:</strong> CO₂, H₂O (완전 산화 생성물)</p>
                        <p><strong>PR Ashing:</strong> 식각 후 변질된 포토레지스트 완전 제거</p>
                      </div>
                    </div>
                    <div className="bg-yellow-50 p-3 rounded">
                      <p className="text-sm text-gray-700">
                        <strong>왜 O₂인가?</strong> 유기물인 포토레지스트를 CO₂와 H₂O로
                        완전 연소시켜 잔여물 없이 깨끗하게 제거할 수 있습니다.
                      </p>
                    </div>
                  </div>
                )}

                {/* 선택비 예측 */}
                <div className="mt-4 bg-indigo-50 p-4 rounded border-l-4 border-indigo-400">
                  <h6 className="font-semibold text-indigo-800 mb-2">예상 선택비</h6>
                  <div className="text-sm">
                    {etchTarget === 'Si' && (
                      <p>Si : SiO₂ = <span className="font-bold text-green-600">10:1</span> (HBr 첨가 시 20:1까지 향상)</p>
                    )}
                    {etchTarget === 'SiO2' && (
                      <p>SiO₂ : Si = <span className="font-bold text-green-600">15:1</span> (폴리머 형성으로 Si 보호)</p>
                    )}
                    {etchTarget === 'Si3N4' && (
                      <p>Si₃N₄ : SiO₂ = <span className="font-bold text-green-600">8:1</span> (유사한 F계 식각이지만 N-Si 결합이 더 강함)</p>
                    )}
                    {etchTarget === 'PR' && (
                      <p>PR : 무기물 = <span className="font-bold text-green-600">∞:1</span> (무기물은 O₂에 반응하지 않음)</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold mb-4">공정 파라미터 제어</h4>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold mb-3">플라즈마 조건</h5>

                  <div className="space-y-4">
                    <div className="p-3 bg-white rounded-lg border-2 border-red-200 shadow-sm">
                      <label className="block text-sm font-medium mb-2 text-red-800">
                        압력: {pressure} mTorr
                      </label>
                      <input
                        type="range"
                        min="30"
                        max="200"
                        step="10"
                        value={pressure}
                        onChange={(e) => setPressure(Number(e.target.value))}
                        className="w-full"
                      />
                    </div>

                    <div className="p-3 bg-white rounded-lg border-2 border-blue-200 shadow-sm">
                      <label className="block text-sm font-medium mb-2 text-blue-800">
                        RF 파워: {power} W
                      </label>
                      <input
                        type="range"
                        min="100"
                        max="800"
                        step="50"
                        value={power}
                        onChange={(e) => setPower(Number(e.target.value))}
                        className="w-full"
                      />
                    </div>

                    <div className="p-3 bg-white rounded-lg border-2 border-green-200 shadow-sm">
                      <label className="block text-sm font-medium mb-2 text-green-800">
                        시간: {time} sec
                      </label>
                      <input
                        type="range"
                        min="10"
                        max="300"
                        step="10"
                        value={time}
                        onChange={(e) => setTime(Number(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold mb-3">가스 유량 제어 (sccm)</h5>

                  <div className="space-y-3">
                    {Object.entries(gasFlows).map(([gas, flow]) => (
                      <div key={gas} className="bg-white p-2 rounded border">
                        <label className="block text-sm font-medium mb-1">
                          {gas}: {flow} sccm
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          step="5"
                          value={flow}
                          onChange={(e) => setGasFlows({
                            ...gasFlows,
                            [gas]: Number(e.target.value)
                          })}
                          className="w-full"
                        />
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={runEtchSimulation}
                    disabled={isSimulating}
                    className="w-full mt-4 bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700 disabled:opacity-50"
                  >
                    {isSimulating ? '식각 진행중...' : '식각 시작'}
                  </button>

                  {isSimulating && (
                    <div className="mt-3">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-600 h-2 rounded-full transition-all duration-100"
                          style={{ width: `${simulationProgress}%` }}
                        />
                      </div>
                      <p className="text-sm text-center mt-1">진행률: {simulationProgress.toFixed(0)}%</p>
                    </div>
                  )}

                  {endpointDetected && (
                    <div className="mt-3 p-2 bg-blue-100 rounded border-l-4 border-blue-400">
                      <p className="text-sm font-semibold text-blue-800">
                        🎯 End Point 검출됨!
                      </p>
                    </div>
                  )}
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="font-semibold mb-3">📊 실험 결과</h5>
                  {etchRate > 0 ? (
                    <div className="space-y-4">
                      {/* 실험 결과 */}
                      <div className="space-y-3">
                        <div className="bg-white p-3 rounded border">
                          <div className="flex justify-between text-sm">
                            <span>✓ 식각속도:</span>
                            <span className="font-semibold text-blue-600">
                              {etchRate.toFixed(1)} nm/min
                            </span>
                          </div>
                        </div>

                        <div className="bg-white p-3 rounded border">
                          <div className="flex justify-between text-sm">
                            <span>✓ 선택비:</span>
                            <span className="font-semibold text-green-600">
                              {selectivity.toFixed(1)} : 1
                            </span>
                          </div>
                        </div>

                        <div className="bg-white p-3 rounded border">
                          <div className="flex justify-between text-sm">
                            <span>✓ 균일성:</span>
                            <span className="font-semibold text-purple-600">
                              {uniformity.toFixed(1)}%
                            </span>
                          </div>
                        </div>

                        <div className="bg-white p-3 rounded border">
                          <div className="flex justify-between text-sm">
                            <span>✓ 식각 깊이:</span>
                            <span className="font-semibold text-red-600">
                              {(etchDepth * 2).toFixed(0)} nm
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* 현재 조건 분석 */}
                      <div className="border-t pt-3">
                        <h6 className="font-semibold text-sm mb-2">💡 현재 조건 분석</h6>
                        <div className="space-y-1 text-xs text-gray-700">
                          {etchTarget === 'Si' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>Cl₂ {gasFlows.Cl2} sccm: {gasFlows.Cl2 >= 25 ? '높은 식각률 제공 ✓' : gasFlows.Cl2 >= 15 ? '적정 식각률' : '식각률 낮음 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>HBr {gasFlows.HBr} sccm: {gasFlows.HBr >= 12 ? '우수한 선택비 기여 ✓' : gasFlows.HBr >= 5 ? '선택비 보통' : '선택비 낮음 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>Ar {gasFlows.Ar} sccm: {gasFlows.Ar >= 70 ? '수직 프로파일 향상 ✓' : gasFlows.Ar >= 40 ? '이방성 보통' : '등방성 경향 ⚠'}</span>
                              </div>
                              <div className="mt-2 p-2 bg-blue-50 rounded text-xs">
                                → {gasFlows.Cl2 >= 25 && gasFlows.HBr >= 12 && gasFlows.Ar >= 70 ? '이상적인 Si 식각 조건입니다' : '일부 파라미터 조정이 필요합니다'}
                              </div>
                            </>
                          )}
                          {etchTarget === 'SiO2' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>CF₄ {gasFlows.CF4} sccm: {gasFlows.CF4 >= 20 ? 'SiO₂ 식각 활성화 ✓' : gasFlows.CF4 >= 10 ? '식각률 보통' : '식각률 부족 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>CHF₃ {gasFlows.CHF3} sccm: {gasFlows.CHF3 >= 15 ? '높은 선택비 유지 ✓' : gasFlows.CHF3 >= 8 ? '선택비 보통' : '선택비 낮음 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>Ar {gasFlows.Ar} sccm: {gasFlows.Ar >= 50 ? '물리적 충격 증가 ✓' : gasFlows.Ar >= 30 ? '적정 수준' : '스퍼터링 부족 ⚠'}</span>
                              </div>
                              <div className="mt-2 p-2 bg-blue-50 rounded text-xs">
                                → {gasFlows.CF4 >= 20 && gasFlows.CHF3 >= 15 && gasFlows.Ar >= 50 ? '이상적인 SiO₂ 식각 조건입니다' : '일부 파라미터 조정이 필요합니다'}
                              </div>
                            </>
                          )}
                          {etchTarget === 'Si3N4' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>CHF₃ {gasFlows.CHF3} sccm: {gasFlows.CHF3 >= 25 ? 'Si₃N₄ 식각 최적 ✓' : gasFlows.CHF3 >= 15 ? '식각률 보통' : '식각률 낮음 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>O₂ {gasFlows.O2} sccm: {gasFlows.O2 >= 8 && gasFlows.O2 <= 15 ? '폴리머 제거 최적 ✓' : gasFlows.O2 > 15 ? '과도한 등방성 ⚠' : 'O₂ 부족 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>Ar {gasFlows.Ar} sccm: {gasFlows.Ar >= 60 ? '수직성 확보 ✓' : gasFlows.Ar >= 40 ? '적정 수준' : '이방성 부족 ⚠'}</span>
                              </div>
                              <div className="mt-2 p-2 bg-blue-50 rounded text-xs">
                                → {gasFlows.CHF3 >= 25 && gasFlows.O2 >= 8 && gasFlows.O2 <= 15 && gasFlows.Ar >= 60 ? '이상적인 Si₃N₄ 식각 조건입니다' : '일부 파라미터 조정이 필요합니다'}
                              </div>
                            </>
                          )}
                          {etchTarget === 'PR' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>O₂ {gasFlows.O2} sccm: {gasFlows.O2 >= 80 ? 'PR 제거 최적 ✓' : gasFlows.O2 >= 50 ? '제거율 보통' : '제거율 낮음 ⚠'}</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span>•</span>
                                <span>Ar {gasFlows.Ar} sccm: {gasFlows.Ar >= 15 && gasFlows.Ar <= 25 ? '스퍼터링 보조 ✓' : gasFlows.Ar > 25 ? 'Ar 과다 ⚠' : 'Ar 부족 ⚠'}</span>
                              </div>
                              <div className="mt-2 p-2 bg-blue-50 rounded text-xs">
                                → {gasFlows.O2 >= 80 && gasFlows.Ar >= 15 && gasFlows.Ar <= 25 ? '이상적인 PR 제거 조건입니다' : '일부 파라미터 조정이 필요합니다'}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* 시뮬레이션 시작 전 가이드 */}
                      <div className="text-center py-4 text-gray-500 text-sm border-2 border-dashed border-gray-300 rounded">
                        시뮬레이션을 시작하세요
                      </div>

                      {/* 가스별 영향 가이드 */}
                      <div className="border-t pt-3">
                        <h6 className="font-semibold text-sm mb-2">💡 가스별 영향 가이드</h6>
                        <div className="space-y-1.5 text-xs text-gray-700">
                          {etchTarget === 'Si' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>Cl₂ 증가</strong> → 식각률↑, 선택비↓, 이방성 유지</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>HBr 증가</strong> → 선택비↑, 측벽 보호↑, 이방성↑</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>Ar 증가</strong> → 물리적 스퍼터링↑, 이방성↑</span>
                              </div>
                            </>
                          )}
                          {etchTarget === 'SiO2' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>CF₄ 증가</strong> → SiO₂ 식각률↑, F 라디칼↑</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>CHF₃ 증가</strong> → 높은 선택비, 폴리머 형성↑</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>Ar 증가</strong> → 물리적 충격↑, 폴리머 제거</span>
                              </div>
                            </>
                          )}
                          {etchTarget === 'Si3N4' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>CHF₃ 증가</strong> → Si₃N₄ 식각률↑, 선택비↑</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>O₂ 증가</strong> → 폴리머 제거↑, 등방성↑</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>Ar 증가</strong> → 수직성 향상↑, 이방성↑</span>
                              </div>
                            </>
                          )}
                          {etchTarget === 'PR' && (
                            <>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>O₂ 증가</strong> → PR 제거율↑, 완전 연소</span>
                              </div>
                              <div className="flex items-start gap-1">
                                <span className="text-blue-600">🔹</span>
                                <span><strong>Ar 증가</strong> → 스퍼터링 보조, 속도↑</span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold mb-4">식각 장비별 특성 및 응용</h4>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div className="bg-blue-50 p-5 rounded-lg border-l-4 border-blue-400">
                  <h5 className="text-lg font-semibold text-blue-800 mb-3">CCP (Capacitively Coupled Plasma)</h5>
                  <div className="space-y-2 text-sm">
                    <p><strong>특성:</strong></p>
                    <ul className="list-disc list-inside space-y-1 text-gray-700">
                      <li>낮은 플라즈마 밀도 (10⁹-10¹⁰ cm⁻³)</li>
                      <li>높은 바이어스 전압 (500-1000V)</li>
                      <li>물리적 스퍼터링 위주</li>
                      <li>단순한 구조, 상대적 저비용</li>
                    </ul>
                    <p><strong>주요 응용:</strong></p>
                    <ul className="list-disc list-inside space-y-1 text-gray-700">
                      <li>Metal 식각 (Al, Cu 등)</li>
                      <li>PR Ashing</li>
                      <li>Chamber Cleaning</li>
                      <li>Oxide 거친 식각</li>
                    </ul>
                    <p><strong>대표 업체:</strong> Applied Materials (DPS), Lam Research (2300)</p>
                  </div>
                </div>

                <div className="bg-purple-50 p-5 rounded-lg border-l-4 border-purple-400">
                  <h5 className="text-lg font-semibold text-purple-800 mb-3">ICP (Inductively Coupled Plasma)</h5>
                  <div className="space-y-2 text-sm">
                    <p><strong>특성:</strong></p>
                    <ul className="list-disc list-inside space-y-1 text-gray-700">
                      <li>높은 플라즈마 밀도 (10¹¹-10¹² cm⁻³)</li>
                      <li>낮은 바이어스 전압 (50-200V)</li>
                      <li>화학적 반응 위주</li>
                      <li>독립적인 플라즈마 밀도/에너지 제어</li>
                    </ul>
                    <p><strong>주요 응용:</strong></p>
                    <ul className="list-disc list-inside space-y-1 text-gray-700">
                      <li>Si Deep Etch (MEMS, TSV)</li>
                      <li>Oxide/Nitride 정밀 식각</li>
                      <li>Poly-Si Gate 식각</li>
                      <li>고선택비 요구 공정</li>
                    </ul>
                    <p><strong>대표 업체:</strong> Lam Research (Kiyo, Versys), TEL (Tactras)</p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-gray-50 to-blue-50 p-5 rounded-lg border border-gray-200">
                <h5 className="text-lg font-semibold text-gray-800 mb-3">왜 장비가 다른가?</h5>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div className="bg-white p-3 rounded shadow">
                    <h6 className="font-semibold text-blue-700 mb-1">플라즈마 밀도</h6>
                    <p className="text-gray-600">ICP는 RF 코일로 높은 밀도 달성 → 더 많은 라디칼 생성 → 화학적 식각 유리</p>
                  </div>
                  <div className="bg-white p-3 rounded shadow">
                    <h6 className="font-semibold text-purple-700 mb-1">이온 에너지</h6>
                    <p className="text-gray-600">CCP는 높은 바이어스 → 강한 물리적 충격 → 금속 식각에 적합</p>
                  </div>
                  <div className="bg-white p-3 rounded shadow">
                    <h6 className="font-semibold text-green-700 mb-1">제어성</h6>
                    <p className="text-gray-600">ICP는 밀도/에너지 독립 제어 → 정밀한 프로파일 제어 가능</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold mb-4">글로벌 Dry Etch 산업 동향 및 이슈</h4>

              <div className="space-y-6">
                <div className="bg-red-50 p-5 rounded-lg border-l-4 border-red-400">
                  <h5 className="text-lg font-semibold text-red-800 mb-3">기술적 도전과제</h5>
                  <p className="text-sm text-gray-700 mb-4">
                    반도체 공정이 3nm 이하로 극미세화되면서 식각 기술도 더욱 정밀하고 까다로워지고 있습니다.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">극미세화 (3nm 이하)</h6>
                      <ul className="space-y-2 text-gray-700">
                        <li>• <strong>Critical Dimension (CD) &lt; 10nm:</strong> 회로 선폭이 10nm보다 작아져 원자 수십 개 수준의 정밀도로 식각해야 함</li>
                        <li>• <strong>Aspect Ratio &gt; 50:1:</strong> 깊이가 폭의 50배 이상인 구조. 깊은 구멍 속까지 균일하게 식각하기 매우 어려움</li>
                        <li>• <strong>Line Edge Roughness (LER) &lt; 1nm:</strong> 회로 가장자리가 1nm 이상 울퉁불퉁하면 성능 저하. 매우 매끄러운 식각 필요</li>
                        <li>• <strong>Plasma Damage 최소화:</strong> 플라즈마의 고에너지 이온이 회로를 손상시킬 수 있어 손상 없는 식각 기술 개발 필요</li>
                      </ul>
                    </div>
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">새로운 재료 도입</h6>
                      <ul className="space-y-2 text-gray-700">
                        <li>• <strong>EUV Resist (CAR → Metal Resist):</strong> 극자외선 리소그래피용 감광제가 기존 화학증폭형에서 금속 함유 타입으로 변화. 식각 조건도 새롭게 최적화 필요</li>
                        <li>• <strong>High-k/Metal Gate Stack:</strong> 고유전율 절연막과 금속 게이트 다층 구조. 각 층마다 다른 식각 조건 필요</li>
                        <li>• <strong>2D Materials (MoS₂, Graphene):</strong> 차세대 반도체 소재인 2차원 물질. 두께가 원자 1-2층 수준이라 손상 없이 패터닝하기 극도로 어려움</li>
                        <li>• <strong>Atomic Layer Etching (ALE) 필요:</strong> 원자층 단위로 한 층씩 식각하는 기술. 위 새로운 재료들을 정밀하게 가공하기 위해 필수</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-green-50 p-5 rounded-lg border-l-4 border-green-400">
                  <h5 className="text-lg font-semibold text-green-800 mb-3">글로벌 시장 현황</h5>
                  <p className="text-sm text-gray-700 mb-4">
                    Dry Etch 장비 시장은 소수의 글로벌 기업들이 주도하고 있으며, 반도체 미세화로 인해 지속적으로 성장하고 있습니다.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div className="bg-white p-4 rounded shadow">
                      <h6 className="font-semibold text-blue-700 mb-2">시장 점유율 (2024)</h6>
                      <p className="text-xs text-gray-600 mb-2">식각 장비 시장은 3개 회사가 90% 이상 점유</p>
                      <ul className="space-y-1 text-gray-700">
                        <li>• <strong>Lam Research:</strong> 약 45% - 선도 기업, 최신 기술 보유</li>
                        <li>• <strong>Applied Materials:</strong> 약 25% - 종합 반도체 장비 기업</li>
                        <li>• <strong>Tokyo Electron:</strong> 약 20% - 일본 대표 장비사</li>
                        <li>• <strong>Others:</strong> 약 10% - 중소 전문 업체들</li>
                      </ul>
                    </div>
                    <div className="bg-white p-4 rounded shadow">
                      <h6 className="font-semibold text-purple-700 mb-2">주요 고객사</h6>
                      <p className="text-xs text-gray-600 mb-2">세계 최대 반도체 생산 기업들</p>
                      <ul className="space-y-1 text-gray-700">
                        <li>• <strong>TSMC (대만):</strong> 세계 최대 파운드리, 최대 고객</li>
                        <li>• <strong>Samsung (한국):</strong> 메모리 1위, 파운드리 2위</li>
                        <li>• <strong>Intel (미국):</strong> CPU 제조사, 자체 팹 운영</li>
                        <li>• <strong>SK Hynix (한국):</strong> DRAM/NAND 주요 업체</li>
                      </ul>
                    </div>
                    <div className="bg-white p-4 rounded shadow">
                      <h6 className="font-semibold text-orange-700 mb-2">시장 규모</h6>
                      <p className="text-xs text-gray-600 mb-2">반도체 미세화로 지속 성장 중</p>
                      <ul className="space-y-1 text-gray-700">
                        <li>• <strong>2024년:</strong> 약 150억 달러 (약 20조원) 이상</li>
                        <li>• <strong>성장률:</strong> 연평균 8-10% - 안정적 성장</li>
                        <li>• <strong>용도별:</strong> Logic(로직) &gt; Memory(메모리) &gt; 기타 순</li>
                        <li>• <strong>지역별:</strong> 아시아(한국/대만/중국) 시장이 주도</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-yellow-50 p-5 rounded-lg border-l-4 border-yellow-400">
                  <h5 className="text-lg font-semibold text-yellow-800 mb-3">환경 및 규제 이슈</h5>
                  <p className="text-sm text-gray-700 mb-4">
                    식각 공정에서 사용되는 불화합물 가스들은 강력한 온실가스로 환경 규제가 강화되고 있습니다.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">PFC 가스 규제</h6>
                      <p className="text-xs text-gray-600 mb-2">불소화합물 가스의 온실가스 문제</p>
                      <ul className="space-y-2 text-gray-700">
                        <li>• <strong>GWP (지구온난화지수) 매우 높음:</strong> 이산화탄소 대비 온실효과가 수천~수만 배</li>
                        <li>• <strong>CF₄: 7,390배, SF₆: 22,800배:</strong> CF₄는 CO₂보다 7천배, SF₆는 2만배 이상 온실효과 유발</li>
                        <li>• <strong>EU REACH, 미국 EPA 규제 강화:</strong> 유럽과 미국에서 사용량 제한과 배출 규제 강화 중</li>
                        <li>• <strong>대체 가스 개발 필요:</strong> 환경 영향이 적은 새로운 식각 가스 개발이 시급한 과제</li>
                      </ul>
                    </div>
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">Abatement 기술</h6>
                      <p className="text-xs text-gray-600 mb-2">배출 가스 처리 시스템</p>
                      <ul className="space-y-2 text-gray-700">
                        <li>• <strong>Thermal/Plasma Abatement:</strong> 고온 연소나 플라즈마로 유해 가스를 분해하는 장치. 모든 식각 장비에 필수 설치</li>
                        <li>• <strong>90%+ 제거 효율 요구:</strong> 배출되는 PFC 가스의 90% 이상을 제거해야 규제 기준 충족</li>
                        <li>• <strong>운영비 증가 요인:</strong> 처리 장비 설치 및 운영에 많은 비용 소요. 반도체 제조 원가 상승 원인</li>
                        <li>• <strong>In-situ Cleaning 기술 개발:</strong> 챔버 내부를 현장에서 세정해 가스 사용량을 줄이는 기술 개발 중</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-blue-50 p-5 rounded-lg border-l-4 border-blue-400">
                  <h5 className="text-lg font-semibold text-blue-800 mb-3">미래 기술 동향</h5>
                  <p className="text-sm text-gray-700 mb-4">
                    반도체 미세화가 한계에 도달하면서 원자 단위 정밀도와 AI 기술 적용이 핵심 트렌드입니다.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">Atomic Layer Processing</h6>
                      <p className="text-xs text-gray-600 mb-2">원자층 단위 초정밀 식각 기술</p>
                      <ul className="space-y-2 text-gray-700">
                        <li>• <strong>ALE (Atomic Layer Etching):</strong> 원자층 한 층씩만 제거하는 초정밀 식각 기술. 3nm 이하 공정의 필수 기술</li>
                        <li>• <strong>Self-limiting 반응:</strong> 화학 반응이 자동으로 한 층에서 멈추는 특성. 정확히 원하는 만큼만 식각 가능</li>
                        <li>• <strong>단원자층 정밀도 제어:</strong> 0.3nm (원자 1개 두께) 수준의 정밀도로 두께 제어 가능</li>
                        <li>• <strong>Damage-free Processing:</strong> 물리적 충격 없이 화학 반응만으로 식각해 소자 손상 제로 목표</li>
                      </ul>
                    </div>
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">AI/ML 적용</h6>
                      <p className="text-xs text-gray-600 mb-2">인공지능 기반 공정 관리</p>
                      <ul className="space-y-2 text-gray-700">
                        <li>• <strong>Real-time Process Control:</strong> AI가 센서 데이터를 실시간 분석해 공정 조건을 자동 최적화. 수율과 품질 향상</li>
                        <li>• <strong>Predictive Maintenance:</strong> 장비 상태를 AI가 예측해 고장 전 미리 정비. 가동률 향상과 비용 절감</li>
                        <li>• <strong>Recipe Optimization:</strong> 머신러닝으로 최적의 식각 조건(레시피)을 자동으로 찾아줌. 개발 시간 단축</li>
                        <li>• <strong>Virtual Metrology:</strong> 실제 측정 없이 AI로 결과를 예측. 측정 시간과 비용 대폭 절감</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 p-6 rounded-lg border-l-4 border-yellow-400">
              <h4 className="text-lg font-semibold text-yellow-800 mb-4">🤔 생각해 보기</h4>
              <div className="space-y-4 text-gray-700">
                <div className="bg-white p-4 rounded-lg">
                  <p><strong>장비 기술 관련:</strong></p>
                  <p><strong>Q1:</strong> 왜 Deep Si 식각에는 ICP를, Metal 식각에는 CCP를 주로 사용할까요?</p>
                  <p><strong>Q2:</strong> ICP에서 플라즈마 밀도와 바이어스 전압을 독립적으로 제어할 수 있는 장점은 무엇일까요?</p>
                </div>

                <div className="bg-white p-4 rounded-lg">
                  <p><strong>산업 동향 관련:</strong></p>
                  <p><strong>Q3:</strong> 3nm 이하 공정에서 ALE(Atomic Layer Etching)가 필요한 이유는 무엇일까요?</p>
                  <p><strong>Q4:</strong> PFC 가스 규제가 강화되면서 식각 공정에 어떤 변화가 필요할까요?</p>
                </div>

                <div className="bg-white p-4 rounded-lg">
                  <p><strong>실험 관련:</strong></p>
                  <p><strong>Q5:</strong> 같은 Si 식각이라도 Logic 소자와 Memory 소자에서 요구사항이 다른 이유는?</p>
                  <p><strong>Q6:</strong> AI/ML을 식각 공정에 적용한다면 어떤 부분에서 가장 효과적일까요?</p>
                </div>
              </div>
            </div>
          </div>
        );

      case 'analysis':
        return <SiliconEtchingSimulator />;

      case 'quiz':
        return (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-pink-50 to-purple-50 p-6 rounded-lg">
              <h3 className="text-xl font-bold text-pink-800 mb-4">📝 식각 공정 평가</h3>
              <p className="text-gray-700">
                학습한 식각 공정 내용을 바탕으로 퀴즈를 풀어보세요.
                각 문제마다 해설이 제공됩니다.
              </p>
            </div>

            {!showResults ? (
              <div className="bg-white p-6 rounded-lg shadow-md">
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-600">
                      문제 {currentQuestion + 1} / {quizQuestions.length}
                    </span>
                    <span className="text-sm font-medium text-purple-600">
                      점수: {score} / {quizQuestions.length}
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${((currentQuestion + 1) / quizQuestions.length) * 100}%` }}
                    />
                  </div>
                </div>

                <div className="mb-6">
                  <h4 className="text-lg font-semibold mb-4">
                    {quizQuestions[currentQuestion]?.question}
                  </h4>

                  <div className="space-y-3">
                    {quizQuestions[currentQuestion]?.options.map((option, index) => (
                      <label
                        key={index}
                        className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                          selectedAnswer === index.toString()
                            ? 'bg-purple-50 border-purple-400'
                            : 'hover:bg-gray-50 border-gray-200'
                        }`}
                      >
                        <input
                          type="radio"
                          name="answer"
                          value={index.toString()}
                          checked={selectedAnswer === index.toString()}
                          onChange={(e) => setSelectedAnswer(e.target.value)}
                          className="mr-3"
                        />
                        <span>{option}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <button
                  onClick={submitAnswer}
                  disabled={!selectedAnswer}
                  className="w-full bg-purple-600 text-white py-3 px-4 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {currentQuestion < quizQuestions.length - 1 ? '다음 문제' : '결과 보기'}
                </button>
              </div>
            ) : (
              <div className="bg-white p-6 rounded-lg shadow-md">
                <div className="text-center mb-6">
                  <h4 className="text-2xl font-bold mb-4">퀴즈 완료!</h4>
                  <div className="text-6xl font-bold text-purple-600 mb-4">
                    {score} / {quizQuestions.length}
                  </div>
                  <div className="text-lg mb-2">
                    정답률: {((score / quizQuestions.length) * 100).toFixed(0)}%
                  </div>

                  <div className="text-lg text-gray-600 mb-6">
                    {score === quizQuestions.length && "완벽합니다! 🎉"}
                    {score >= quizQuestions.length * 0.8 && score < quizQuestions.length && "우수합니다! 👏"}
                    {score >= quizQuestions.length * 0.6 && score < quizQuestions.length * 0.8 && "좋습니다! 👍"}
                    {score < quizQuestions.length * 0.6 && "더 학습이 필요합니다. 💪"}
                  </div>
                </div>

                <div className="mb-6">
                  <h5 className="text-lg font-semibold mb-4">정답 및 해설</h5>
                  <div className="space-y-4">
                    {quizQuestions.map((question, index) => (
                      <div key={index} className="bg-gray-50 p-4 rounded-lg">
                        <p className="font-semibold mb-2">Q{index + 1}: {question.question}</p>
                        <p className="text-green-700 font-medium mb-2">
                          정답: {question.options[question.correct]}
                        </p>
                        <p className="text-gray-700 text-sm">
                          {question.explanation}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  onClick={resetQuiz}
                  className="w-full bg-purple-600 text-white py-3 px-6 rounded-lg hover:bg-purple-700"
                >
                  다시 도전하기
                </button>
              </div>
            )}

            <div className="bg-yellow-50 p-6 rounded-lg border-l-4 border-yellow-400">
              <h4 className="text-lg font-semibold text-yellow-800 mb-4">🤔 생각해 보기</h4>
              <div className="space-y-3 text-gray-700">
                <p><strong>Q1:</strong> 실제 반도체 제조에서 식각 공정의 수율을 높이기 위한 방법들을 생각해보세요.</p>
                <p><strong>Q2:</strong> 차세대 반도체 소자에서 요구되는 식각 기술의 도전과제는 무엇일까요?</p>
                <p><strong>Q3:</strong> 식각 공정에서 발생할 수 있는 defect들과 그 해결 방안을 연구해보세요.</p>
              </div>
            </div>
          </div>
        );

      default:
        return <div>탭을 선택해주세요.</div>;
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-gray-50">
      {/* 탭 네비게이션 */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="flex space-x-1 p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-4 py-3 rounded-lg font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-blue-100 text-blue-800 shadow-sm'
                  : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
              }`}
            >
              <span className="text-lg">{tab.icon}</span>
              <span>{tab.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 컨텐츠 영역 */}
      <div className="flex-1 overflow-auto">
        <div className="p-6">
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
};

export default EtchSimulator;
