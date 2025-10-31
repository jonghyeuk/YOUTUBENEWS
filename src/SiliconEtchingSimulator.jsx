import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';

const SiliconEtchingSimulator = () => {
  const mountRef = useRef(null);
  const [selectedGas, setSelectedGas] = useState('SF6');
  const [isSimulating, setIsSimulating] = useState(false);
  const [etchDepth, setEtchDepth] = useState(0);
  const [stats, setStats] = useState({
    dissociatedMolecules: 0,
    siAtomsRemoved: 0,
    byproductsGenerated: 0
  });

  // Gas types configuration
  const gasTypes = {
    SF6: {
      name: 'SF₆',
      color: 0x00ff00,
      structure: 'octahedral',
      byproduct: 'SiF₄',
      formula: 'SF₆ → SF₅ + F',
      description: '팔면체 구조, 높은 식각 속도'
    },
    CF4: {
      name: 'CF₄',
      color: 0x00bfff,
      structure: 'tetrahedral',
      byproduct: 'SiF₄',
      formula: 'CF₄ → CF₃ + F',
      description: '사면체 구조, 선택적 식각'
    },
    Cl2: {
      name: 'Cl₂',
      color: 0xffff00,
      structure: 'diatomic',
      byproduct: 'SiCl₄',
      formula: 'Cl₂ → 2Cl',
      description: '이원자 분자, 실리콘 식각'
    },
    HBr: {
      name: 'HBr',
      color: 0xff6600,
      structure: 'diatomic',
      byproduct: 'SiBr₄',
      formula: 'HBr → H + Br',
      description: '이원자 분자, 고선택비 식각'
    }
  };

  useEffect(() => {
    if (!mountRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);

    const camera = new THREE.PerspectiveCamera(
      75,
      mountRef.current.clientWidth / mountRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 10, 25);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    mountRef.current.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0xffffff, 1);
    pointLight.position.set(10, 10, 10);
    scene.add(pointLight);

    // Plasma chamber (walls)
    const chamberGeometry = new THREE.BoxGeometry(20, 15, 20);
    const chamberMaterial = new THREE.MeshBasicMaterial({
      color: 0x333333,
      wireframe: true,
      transparent: true,
      opacity: 0.3
    });
    const chamber = new THREE.Mesh(chamberGeometry, chamberMaterial);
    chamber.position.y = 5;
    scene.add(chamber);

    // Silicon wafer (bottom surface)
    const waferGeometry = new THREE.CylinderGeometry(8, 8, 0.5, 32);
    const waferMaterial = new THREE.MeshPhongMaterial({
      color: 0x708090,
      shininess: 100
    });
    const wafer = new THREE.Mesh(waferGeometry, waferMaterial);
    wafer.position.y = -2;
    scene.add(wafer);

    // Si atoms on wafer surface (grid)
    const siAtoms = [];
    const siAtomGeometry = new THREE.SphereGeometry(0.3, 16, 16);
    const siAtomMaterial = new THREE.MeshPhongMaterial({ color: 0x4169e1 });

    for (let x = -6; x <= 6; x += 1.5) {
      for (let z = -6; z <= 6; z += 1.5) {
        if (Math.sqrt(x*x + z*z) < 7) {
          const siAtom = new THREE.Mesh(siAtomGeometry, siAtomMaterial);
          siAtom.position.set(x, -1.5, z);
          siAtom.userData = { removed: false, originalY: -1.5 };
          scene.add(siAtom);
          siAtoms.push(siAtom);
        }
      }
    }

    // Particle arrays
    const gasMolecules = [];
    const radicals = [];
    const byproducts = [];

    // Create molecular structure based on gas type
    const createMolecule = (gasType, position) => {
      const group = new THREE.Group();
      const config = gasTypes[gasType];

      switch (config.structure) {
        case 'octahedral': // SF6
          // Central S atom
          const sAtom = new THREE.Mesh(
            new THREE.SphereGeometry(0.4, 16, 16),
            new THREE.MeshPhongMaterial({ color: 0xffff00 })
          );
          group.add(sAtom);

          // 6 F atoms at octahedral positions
          const positions = [
            [1, 0, 0], [-1, 0, 0],
            [0, 1, 0], [0, -1, 0],
            [0, 0, 1], [0, 0, -1]
          ];
          positions.forEach(pos => {
            const fAtom = new THREE.Mesh(
              new THREE.SphereGeometry(0.3, 16, 16),
              new THREE.MeshPhongMaterial({ color: 0x00ff00 })
            );
            fAtom.position.set(...pos);
            group.add(fAtom);
          });
          break;

        case 'tetrahedral': // CF4
          // Central C atom
          const cAtom = new THREE.Mesh(
            new THREE.SphereGeometry(0.35, 16, 16),
            new THREE.MeshPhongMaterial({ color: 0x808080 })
          );
          group.add(cAtom);

          // 4 F atoms at tetrahedral positions
          const tetraPos = [
            [0.8, 0.8, 0.8],
            [0.8, -0.8, -0.8],
            [-0.8, 0.8, -0.8],
            [-0.8, -0.8, 0.8]
          ];
          tetraPos.forEach(pos => {
            const fAtom = new THREE.Mesh(
              new THREE.SphereGeometry(0.3, 16, 16),
              new THREE.MeshPhongMaterial({ color: 0x00bfff })
            );
            fAtom.position.set(...pos);
            group.add(fAtom);
          });
          break;

        case 'diatomic': // Cl2, HBr
          const atom1 = new THREE.Mesh(
            new THREE.SphereGeometry(0.4, 16, 16),
            new THREE.MeshPhongMaterial({ color: config.color })
          );
          atom1.position.x = -0.5;
          group.add(atom1);

          const atom2 = new THREE.Mesh(
            new THREE.SphereGeometry(0.4, 16, 16),
            new THREE.MeshPhongMaterial({ color: config.color })
          );
          atom2.position.x = 0.5;
          group.add(atom2);
          break;
      }

      group.position.copy(position);
      group.userData = { type: 'molecule', gasType, velocity: new THREE.Vector3() };
      return group;
    };

    // Create radical (dissociated particle)
    const createRadical = (position, gasType) => {
      const config = gasTypes[gasType];
      const radical = new THREE.Mesh(
        new THREE.SphereGeometry(0.2, 16, 16),
        new THREE.MeshPhongMaterial({
          color: config.color,
          emissive: config.color,
          emissiveIntensity: 0.5
        })
      );
      radical.position.copy(position);
      radical.userData = {
        type: 'radical',
        gasType,
        velocity: new THREE.Vector3(
          (Math.random() - 0.5) * 0.05,
          -0.1 - Math.random() * 0.1,
          (Math.random() - 0.5) * 0.05
        ),
        lifetime: 0
      };
      scene.add(radical);
      radicals.push(radical);

      setStats(prev => ({
        ...prev,
        dissociatedMolecules: prev.dissociatedMolecules + 1
      }));
    };

    // Create byproduct
    const createByproduct = (position, gasType) => {
      const config = gasTypes[gasType];
      const byproduct = new THREE.Mesh(
        new THREE.SphereGeometry(0.25, 16, 16),
        new THREE.MeshPhongMaterial({
          color: 0xff69b4,
          transparent: true,
          opacity: 0.8
        })
      );
      byproduct.position.copy(position);
      byproduct.userData = {
        type: 'byproduct',
        name: config.byproduct,
        velocity: new THREE.Vector3(
          (Math.random() - 0.5) * 0.03,
          0.08 + Math.random() * 0.05,
          (Math.random() - 0.5) * 0.03
        )
      };
      scene.add(byproduct);
      byproducts.push(byproduct);

      setStats(prev => ({
        ...prev,
        byproductsGenerated: prev.byproductsGenerated + 1
      }));
    };

    // Animation loop
    let animationId;
    let time = 0;

    const animate = () => {
      animationId = requestAnimationFrame(animate);
      time += 0.016;

      if (isSimulating) {
        // Spawn new gas molecules
        if (Math.random() < 0.05 && gasMolecules.length < 30) {
          const molecule = createMolecule(
            selectedGas,
            new THREE.Vector3(
              (Math.random() - 0.5) * 15,
              12,
              (Math.random() - 0.5) * 15
            )
          );
          molecule.userData.velocity.y = -0.05 - Math.random() * 0.03;
          scene.add(molecule);
          gasMolecules.push(molecule);
        }

        // Update gas molecules - plasma dissociation
        gasMolecules.forEach((molecule, index) => {
          molecule.position.add(molecule.userData.velocity);
          molecule.rotation.x += 0.02;
          molecule.rotation.y += 0.02;

          // Dissociation in plasma region (y > 2)
          if (molecule.position.y < 5 && molecule.position.y > 2 && Math.random() < 0.02) {
            createRadical(molecule.position.clone(), molecule.userData.gasType);
            scene.remove(molecule);
            gasMolecules.splice(index, 1);
          }

          // Remove if out of bounds
          if (molecule.position.y < -3) {
            scene.remove(molecule);
            gasMolecules.splice(index, 1);
          }
        });

        // Update radicals
        radicals.forEach((radical, index) => {
          radical.position.add(radical.userData.velocity);
          radical.userData.lifetime += 1;

          // Check collision with Si atoms
          siAtoms.forEach(siAtom => {
            if (!siAtom.userData.removed) {
              const distance = radical.position.distanceTo(siAtom.position);
              if (distance < 0.8) {
                // Etching reaction
                siAtom.userData.removed = true;
                createByproduct(siAtom.position.clone(), radical.userData.gasType);

                // Remove Si atom with animation
                const targetY = siAtom.position.y - 0.5;
                siAtom.userData.targetY = targetY;

                setStats(prev => ({
                  ...prev,
                  siAtomsRemoved: prev.siAtomsRemoved + 1
                }));
                setEtchDepth(prev => prev + 0.1);

                // Remove radical
                scene.remove(radical);
                radicals.splice(index, 1);
              }
            }
          });

          // Remove old radicals
          if (radical.userData.lifetime > 200 || radical.position.y < -3) {
            scene.remove(radical);
            radicals.splice(index, 1);
          }
        });

        // Update byproducts (exhaust)
        byproducts.forEach((byproduct, index) => {
          byproduct.position.add(byproduct.userData.velocity);
          byproduct.rotation.y += 0.05;

          // Fade out as it rises
          if (byproduct.position.y > 12) {
            scene.remove(byproduct);
            byproducts.splice(index, 1);
          }
        });

        // Animate Si atoms removal
        siAtoms.forEach(siAtom => {
          if (siAtom.userData.removed && siAtom.userData.targetY) {
            if (siAtom.position.y > siAtom.userData.targetY) {
              siAtom.position.y -= 0.01;
              siAtom.material.opacity = Math.max(0, siAtom.material.opacity - 0.01);
              siAtom.material.transparent = true;
            }
          }
        });
      }

      renderer.render(scene, camera);
    };

    animate();

    // Handle window resize
    const handleResize = () => {
      if (mountRef.current) {
        camera.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
      }
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationId);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [selectedGas, isSimulating]);

  const resetSimulation = () => {
    setIsSimulating(false);
    setEtchDepth(0);
    setStats({
      dissociatedMolecules: 0,
      siAtomsRemoved: 0,
      byproductsGenerated: 0
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-6 rounded-lg">
        <h3 className="text-2xl font-bold text-blue-800 mb-3">🔬 실리콘 식각 메커니즘 시뮬레이터</h3>
        <p className="text-gray-700 leading-relaxed">
          실시간 3D 시뮬레이션으로 플라즈마 식각의 전체 과정을 관찰하세요.
          가스 분자의 해리, 라디칼의 Si 표면 반응, 반응 생성물의 배출까지 모든 단계를 시각화합니다.
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h4 className="text-lg font-semibold mb-4">식각 가스 선택</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          {Object.entries(gasTypes).map(([key, gas]) => (
            <button
              key={key}
              onClick={() => setSelectedGas(key)}
              className={`p-4 rounded-lg border-2 transition-all ${
                selectedGas === key
                  ? 'border-blue-500 bg-blue-50 shadow-md'
                  : 'border-gray-300 hover:border-blue-300'
              }`}
            >
              <div className="text-2xl mb-2">{gas.name}</div>
              <div className="text-xs text-gray-600">{gas.description}</div>
            </button>
          ))}
        </div>

        <div className="flex gap-4">
          <button
            onClick={() => setIsSimulating(!isSimulating)}
            className={`px-6 py-3 rounded-lg font-semibold transition-colors ${
              isSimulating
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-green-600 hover:bg-green-700 text-white'
            }`}
          >
            {isSimulating ? '⏸ 일시정지' : '▶ 시뮬레이션 시작'}
          </button>
          <button
            onClick={resetSimulation}
            className="px-6 py-3 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-semibold transition-colors"
          >
            🔄 초기화
          </button>
        </div>
      </div>

      {/* 3D Viewer */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h4 className="text-lg font-semibold mb-4">3D 시뮬레이션 뷰어</h4>
        <div
          ref={mountRef}
          className="w-full rounded-lg overflow-hidden border-2 border-gray-200"
          style={{ height: '500px' }}
        />
        <div className="mt-3 grid grid-cols-3 gap-3 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-gray-500 rounded"></div>
            <span>실리콘 웨이퍼</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-500 rounded-full"></div>
            <span>Si 원자</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-pink-400 rounded-full"></div>
            <span>반응 생성물</span>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-lg shadow-md">
          <div className="text-3xl font-bold text-blue-600">{stats.dissociatedMolecules}</div>
          <div className="text-sm text-gray-600 mt-1">플라즈마 해리</div>
        </div>
        <div className="bg-white p-5 rounded-lg shadow-md">
          <div className="text-3xl font-bold text-green-600">{stats.siAtomsRemoved}</div>
          <div className="text-sm text-gray-600 mt-1">Si 원자 제거</div>
        </div>
        <div className="bg-white p-5 rounded-lg shadow-md">
          <div className="text-3xl font-bold text-purple-600">{stats.byproductsGenerated}</div>
          <div className="text-sm text-gray-600 mt-1">생성물 배출</div>
        </div>
        <div className="bg-white p-5 rounded-lg shadow-md">
          <div className="text-3xl font-bold text-orange-600">{etchDepth.toFixed(1)} nm</div>
          <div className="text-sm text-gray-600 mt-1">식각 깊이</div>
        </div>
      </div>

      {/* Reaction Details */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h4 className="text-lg font-semibold mb-4">선택된 가스의 반응 메커니즘</h4>
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-purple-50 to-blue-50 p-4 rounded-lg">
            <h5 className="font-semibold text-purple-800 mb-2">1️⃣ 플라즈마 해리</h5>
            <div className="text-lg font-mono text-center py-2">
              {gasTypes[selectedGas].formula}
            </div>
            <p className="text-sm text-gray-700 mt-2">
              {selectedGas === 'SF6' && '육불화황 분자가 플라즈마 에너지를 받아 SF₅ 라디칼과 F 라디칼로 분해됩니다.'}
              {selectedGas === 'CF4' && '사불화탄소 분자가 플라즈마에서 CF₃ 라디칼과 F 라디칼로 해리됩니다.'}
              {selectedGas === 'Cl2' && '염소 분자가 플라즈마 충돌로 2개의 Cl 라디칼로 분리됩니다.'}
              {selectedGas === 'HBr' && '브롬화수소 분자가 H 라디칼과 Br 라디칼로 해리됩니다.'}
            </p>
          </div>

          <div className="bg-gradient-to-r from-green-50 to-teal-50 p-4 rounded-lg">
            <h5 className="font-semibold text-green-800 mb-2">2️⃣ 표면 반응</h5>
            <div className="text-lg font-mono text-center py-2">
              Si + {gasTypes[selectedGas].name.split('₂')[0]} → {gasTypes[selectedGas].byproduct}
            </div>
            <p className="text-sm text-gray-700 mt-2">
              라디칼이 Si 웨이퍼 표면에 도달하여 Si 원자와 화학 반응을 일으킵니다.
              {selectedGas === 'SF6' && ' F 라디칼이 Si-Si 결합을 끊고 Si-F 결합을 형성합니다.'}
              {selectedGas === 'CF4' && ' F 라디칼의 높은 반응성으로 Si 표면을 효과적으로 식각합니다.'}
              {selectedGas === 'Cl2' && ' Cl 라디칼이 Si와 결합하여 SiCl₄를 형성합니다.'}
              {selectedGas === 'HBr' && ' Br 라디칼이 Si와 반응하여 높은 선택비를 제공합니다.'}
            </p>
          </div>

          <div className="bg-gradient-to-r from-pink-50 to-rose-50 p-4 rounded-lg">
            <h5 className="font-semibold text-pink-800 mb-2">3️⃣ 생성물 배출</h5>
            <div className="text-lg font-mono text-center py-2">
              {gasTypes[selectedGas].byproduct} ↑ (기체)
            </div>
            <p className="text-sm text-gray-700 mt-2">
              반응 생성물인 {gasTypes[selectedGas].byproduct}는 휘발성 기체 상태로 표면에서 탈착되어
              진공 펌프를 통해 챔버 밖으로 배출됩니다. 이 과정이 연속적으로 일어나면서 식각이 진행됩니다.
            </p>
          </div>
        </div>
      </div>

      {/* Molecular Structure Info */}
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h4 className="text-lg font-semibold mb-4">분자 구조 특성</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-gray-50 p-4 rounded-lg">
            <h5 className="font-semibold text-gray-800 mb-2">구조 분류</h5>
            <ul className="space-y-2 text-sm text-gray-700">
              <li><strong>팔면체 (Octahedral):</strong> SF₆ - 중심 S 원자 주위에 6개의 F 원자가 배치</li>
              <li><strong>사면체 (Tetrahedral):</strong> CF₄ - 중심 C 원자 주위에 4개의 F 원자가 배치</li>
              <li><strong>이원자 (Diatomic):</strong> Cl₂, HBr - 2개의 원자가 단일 결합으로 연결</li>
            </ul>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <h5 className="font-semibold text-gray-800 mb-2">반응성 비교</h5>
            <ul className="space-y-2 text-sm text-gray-700">
              <li><strong>SF₆:</strong> 안정한 구조, 플라즈마에서 F 라디칼 생성 - 고속 식각</li>
              <li><strong>CF₄:</strong> C-F 강한 결합, 선택적 식각에 유리</li>
              <li><strong>Cl₂:</strong> 약한 Cl-Cl 결합, 쉽게 해리되어 높은 식각 속도</li>
              <li><strong>HBr:</strong> Br의 큰 원자 크기, 높은 선택비와 이방성 제공</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SiliconEtchingSimulator;
