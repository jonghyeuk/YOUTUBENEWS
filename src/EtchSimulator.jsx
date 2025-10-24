import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar } from 'recharts';

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

  // 탭 정의
  const tabs = [
    { id: 'overview', name: '식각 공정 개요', icon: '📋' },
    { id: 'etch-rate', name: '식각률', icon: '⚡' },
    { id: 'selectivity', name: '선택성', icon: '🎯' },
    { id: 'uniformity', name: '균일성', icon: '⚖️' },
    { id: 'anisotropy', name: '이방도', icon: '📐' },
    { id: 'loading-effect', name: 'Loading Effect', icon: '🔄' },
    { id: 'etch-principle', name: '식각원리', icon: '🔬' },
    { id: 'process', name: '식각 실험', icon: '🧪' },
    { id: 'analysis', name: '영향 인자 분석', icon: '📊' },
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
              <h4 className="text-lg font-semibold mb-4 text-center">식각 공정 관리 5대 핵심 요소</h4>

              {/* 중앙의 순환 다이어그램 */}
              <div className="flex justify-center mb-6">
                <svg width="400" height="400" viewBox="0 0 400 400">
                  {/* 중앙 원 */}
                  <circle cx="200" cy="200" r="50" fill="#e0f2fe" stroke="#0284c7" strokeWidth="3"/>
                  <text x="200" y="195" textAnchor="middle" className="text-sm font-bold" fill="#0284c7">식각</text>
                  <text x="200" y="210" textAnchor="middle" className="text-sm font-bold" fill="#0284c7">공정</text>

                  {/* 5개 요소 원들 */}
                  <g>
                    {/* 1. 식각률 (12시) */}
                    <circle cx="200" cy="80" r="40" fill="#fef3c7" stroke="#f59e0b" strokeWidth="2"/>
                    <text x="200" y="75" textAnchor="middle" className="text-xs font-semibold">Etch Rate</text>
                    <text x="200" y="88" textAnchor="middle" className="text-xs">식각률</text>
                    <line x1="200" y1="150" x2="200" y2="120" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                    {/* 2. 선택성 (2시) */}
                    <circle cx="310" cy="140" r="40" fill="#dcfce7" stroke="#22c55e" strokeWidth="2"/>
                    <text x="310" y="135" textAnchor="middle" className="text-xs font-semibold">Selectivity</text>
                    <text x="310" y="148" textAnchor="middle" className="text-xs">선택성</text>
                    <line x1="245" y1="165" x2="275" y2="155" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                    {/* 3. 균일성 (4시) */}
                    <circle cx="310" cy="260" r="40" fill="#e0e7ff" stroke="#6366f1" strokeWidth="2"/>
                    <text x="310" y="255" textAnchor="middle" className="text-xs font-semibold">Uniformity</text>
                    <text x="310" y="268" textAnchor="middle" className="text-xs">균일성</text>
                    <line x1="245" y1="235" x2="275" y2="245" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                    {/* 4. 이방도 (8시) */}
                    <circle cx="90" cy="260" r="40" fill="#fce7f3" stroke="#ec4899" strokeWidth="2"/>
                    <text x="90" y="255" textAnchor="middle" className="text-xs font-semibold">Anisotropy</text>
                    <text x="90" y="268" textAnchor="middle" className="text-xs">이방도</text>
                    <line x1="155" y1="235" x2="125" y2="245" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrowhead)"/>

                    {/* 5. Loading Effect (10시) */}
                    <circle cx="90" cy="140" r="40" fill="#f3e8ff" stroke="#a855f7" strokeWidth="2"/>
                    <text x="90" y="135" textAnchor="middle" className="text-xs font-semibold">Loading</text>
                    <text x="90" y="148" textAnchor="middle" className="text-xs">로딩효과</text>
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
                <p>• 각 탭을 클릭하여 식각의 핵심 요소들을 자세히 학습하세요</p>
                <p>• 실험 탭에서 실제 공정 조건을 조절해보며 결과를 관찰하세요</p>
                <p>• 분석 탭에서 파라미터 변화가 식각 결과에 미치는 영향을 확인하세요</p>
                <p>• 평가 탭에서 학습한 내용을 점검해보세요</p>
              </div>
            </div>
          </div>
        );

      case 'process':
        return (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-6 rounded-lg">
              <h3 className="text-xl font-bold text-green-800 mb-4">🔬 식각 실험 시뮬레이션</h3>
              <p className="text-gray-700">
                실제 식각 장비를 조작하여 다양한 물질의 식각 공정을 체험해보세요.
                가스 조성, 압력, 파워 등을 조절하여 최적의 식각 조건을 찾아보세요.
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
                  <h5 className="font-semibold mb-3">실험 결과</h5>
                  {etchRate > 0 && (
                    <div className="space-y-3">
                      <div className="bg-white p-3 rounded border">
                        <div className="flex justify-between text-sm">
                          <span>식각속도:</span>
                          <span className="font-semibold text-blue-600">
                            {etchRate.toFixed(1)} nm/min
                          </span>
                        </div>
                      </div>

                      <div className="bg-white p-3 rounded border">
                        <div className="flex justify-between text-sm">
                          <span>선택비:</span>
                          <span className="font-semibold text-green-600">
                            {selectivity.toFixed(1)} : 1
                          </span>
                        </div>
                      </div>

                      <div className="bg-white p-3 rounded border">
                        <div className="flex justify-between text-sm">
                          <span>균일성:</span>
                          <span className="font-semibold text-purple-600">
                            {uniformity.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      <div className="bg-white p-3 rounded border">
                        <div className="flex justify-between text-sm">
                          <span>식각 깊이:</span>
                          <span className="font-semibold text-red-600">
                            {(etchDepth * 2).toFixed(0)} nm
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold mb-4">실시간 식각 과정 시뮬레이션</h4>

              <div className="flex justify-center">
                <svg width="500" height="350" viewBox="0 0 500 350">
                  {/* 챔버 외곽 */}
                  <rect x="50" y="50" width="400" height="250" fill="none" stroke="#374151" strokeWidth="2" rx="5"/>
                  <text x="250" y="40" textAnchor="middle" className="text-sm font-bold">Etch Chamber</text>

                  {/* 기판 */}
                  <rect x="100" y="250" width="300" height="30" fill="#4a5568" />
                  <text x="250" y="270" textAnchor="middle" fill="white" className="text-xs font-semibold">
                    {etchTarget === 'PR' ? 'Si Substrate (with PR)' : 'Si Substrate'}
                  </text>

                  {/* 1. 전체 타겟층 - 마스크로 보호된 부분만, 타겟에 따라 색상 변경 */}
                  <rect x="100" y="220" width="80" height="30" fill={
                    etchTarget === 'Si' ? "#60a5fa" :
                    etchTarget === 'SiO2' ? "#94a3b8" :
                    etchTarget === 'Si3N4' ? "#a855f7" :
                    "#fbbf24"
                  } />
                  <rect x="220" y="220" width="60" height="30" fill={
                    etchTarget === 'Si' ? "#60a5fa" :
                    etchTarget === 'SiO2' ? "#94a3b8" :
                    etchTarget === 'Si3N4' ? "#a855f7" :
                    "#fbbf24"
                  } />
                  <rect x="320" y="220" width="80" height="30" fill={
                    etchTarget === 'Si' ? "#60a5fa" :
                    etchTarget === 'SiO2' ? "#94a3b8" :
                    etchTarget === 'Si3N4' ? "#a855f7" :
                    "#fbbf24"
                  } />

                  {/* 노출된 타겟 영역 - 식각에 따라 크기 변화, 타겟에 따라 색상 변경 */}
                  {isSimulating && (() => {
                    const targetEtchProgress = Math.min(etchDepth / 80, 1);
                    const remainingHeight = Math.max(0, 30 - (targetEtchProgress * 35)); // 최대 35px까지 식각
                    const etchedFromTop = Math.min(targetEtchProgress * 35, 35);
                    const targetColor =
                      etchTarget === 'Si' ? "#60a5fa" :
                      etchTarget === 'SiO2' ? "#94a3b8" :
                      etchTarget === 'Si3N4' ? "#a855f7" :
                      "#fbbf24";

                    return (
                      <>
                        {remainingHeight > 0 && (
                          <>
                            <rect
                              x="180"
                              y={220 + etchedFromTop}
                              width="40"
                              height={remainingHeight}
                              fill={targetColor}
                            />
                            <rect
                              x="280"
                              y={220 + etchedFromTop}
                              width="40"
                              height={remainingHeight}
                              fill={targetColor}
                            />
                          </>
                        )}
                      </>
                    );
                  })()}

                  {/* 2. 마스크 (황색) - 식각에 따라 크기 변화 */}
                  {isSimulating && (() => {
                    const maskEtchProgress = Math.min(etchDepth / 200, 0.8);
                    const maskRemainingHeight = Math.max(0, 10 - (maskEtchProgress * 10));
                    const maskEtchedFromTop = Math.min(maskEtchProgress * 10, 10);

                    return maskRemainingHeight > 0 ? (
                      <>
                        <rect
                          x="100"
                          y={210 + maskEtchedFromTop}
                          width="80"
                          height={maskRemainingHeight}
                          fill="#fbbf24"
                        />
                        <rect
                          x="220"
                          y={210 + maskEtchedFromTop}
                          width="60"
                          height={maskRemainingHeight}
                          fill="#fbbf24"
                        />
                        <rect
                          x="320"
                          y={210 + maskEtchedFromTop}
                          width="80"
                          height={maskRemainingHeight}
                          fill="#fbbf24"
                        />
                      </>
                    ) : null;
                  })()}

                  {/* 3. 플라즈마 및 이온들 - 타겟에 따라 다른 이온 타입 */}
                  {Array.from({length: 20}, (_, i) => {
                    const seed = i * 23 + 37;
                    const x = 60 + (seed % 380);
                    const cyclePeriod = 100;
                    const ionCycle = (animatedValue * 3 + i * 15) % cyclePeriod;
                    const isActive = ionCycle < 70;
                    const ionY = 60 + ionCycle * 2.5;

                    // 타겟에 따라 다른 이온 타입 정의
                    const getIonsByTarget = (target) => {
                      switch(target) {
                        case 'Si':
                          return [
                            { color: "#dc2626", name: "Cl+", size: 2 },
                            { color: "#7c3aed", name: "Ar+", size: 2.5 },
                            { color: "#ea580c", name: "HBr+", size: 1.8 }
                          ];
                        case 'SiO2':
                          return [
                            { color: "#059669", name: "F+", size: 1.5 },
                            { color: "#0891b2", name: "CF3+", size: 2 },
                            { color: "#7c3aed", name: "Ar+", size: 2.5 }
                          ];
                        case 'Si3N4':
                          return [
                            { color: "#059669", name: "F+", size: 1.5 },
                            { color: "#0891b2", name: "CHF2+", size: 1.8 },
                            { color: "#dc2626", name: "O+", size: 1.3 }
                          ];
                        case 'PR':
                          return [
                            { color: "#dc2626", name: "O+", size: 1.5 },
                            { color: "#ea580c", name: "O2+", size: 1.8 },
                            { color: "#7c3aed", name: "Ar+", size: 2 }
                          ];
                        default:
                          return [
                            { color: "#7c3aed", name: "Ion+", size: 2 }
                          ];
                      }
                    };

                    const ionTypes = getIonsByTarget(etchTarget);
                    const ionType = ionTypes[seed % ionTypes.length];

                    // 표면 충돌 확인
                    const maskSurface = 210 + (etchDepth > 200 ? 10 : (etchDepth / 200) * 10);
                    const targetSurface = 220 + Math.min(etchDepth / 80, 1) * 35;

                    const hitsMask = ((x >= 100 && x <= 180) || (x >= 220 && x <= 280) || (x >= 320 && x <= 400));
                    const hitsTarget = ((x >= 180 && x <= 220) || (x >= 280 && x <= 320));

                    const hasCollision = (hitsMask && ionY >= maskSurface) || (hitsTarget && ionY >= targetSurface);

                    return isActive && !hasCollision ? (
                      <g key={i}>
                        <circle
                          cx={x}
                          cy={ionY}
                          r={ionType.size}
                          fill={ionType.color}
                          opacity="0.8"
                          style={{
                            animation: 'flash 0.5s ease-in-out infinite'
                          }}
                        />
                        {/* 이온 궤적 */}
                        <line
                          x1={x}
                          y1={ionY - 10}
                          x2={x}
                          y2={ionY}
                          stroke={ionType.color}
                          strokeWidth="1"
                          opacity="0.4"
                        />
                      </g>
                    ) : null;
                  })}

                  {/* 4. 반응 생성물 상승 - 타겟에 따라 다른 생성물 */}
                  {Array.from({length: 12}, (_, i) => {
                    const seed = i * 29 + 53;
                    const riseX = 70 + (seed % 360);
                    const riseCycle = (animatedValue * 2 + i * 25) % 200;
                    const isRising = riseCycle < 140;
                    const riseDistance = riseCycle * 1.8;
                    const productY = 260 - riseDistance;

                    // 타겟에 따라 다른 생성물 정의
                    const getProductsByTarget = (target) => {
                      switch(target) {
                        case 'Si':
                          return [
                            { color: "#f97316", name: "SiCl4", size: 1.8 },
                            { color: "#7c3aed", name: "Ar", size: 1.2 },
                            { color: "#dc2626", name: "Cl2", size: 1.5 }
                          ];
                        case 'SiO2':
                          return [
                            { color: "#38bdf8", name: "SiF4", size: 1.5 },
                            { color: "#84cc16", name: "CO2", size: 1.2 },
                            { color: "#06b6d4", name: "CF2", size: 1.3 }
                          ];
                        case 'Si3N4':
                          return [
                            { color: "#38bdf8", name: "SiF4", size: 1.5 },
                            { color: "#3b82f6", name: "N2", size: 1.4 },
                            { color: "#a855f7", name: "CO", size: 1.2 }
                          ];
                        case 'PR':
                          return [
                            { color: "#84cc16", name: "CO2", size: 1.5 },
                            { color: "#06b6d4", name: "H2O", size: 1.3 },
                            { color: "#f59e0b", name: "O2", size: 1.1 }
                          ];
                        default:
                          return [
                            { color: "#84cc16", name: "Product", size: 1.5 }
                          ];
                      }
                    };

                    const products = getProductsByTarget(etchTarget);
                    const product = products[seed % products.length];

                    return isRising && productY > 60 ? (
                      <g key={`rise-${i}`}>
                        <circle
                          cx={riseX}
                          cy={productY}
                          r={product.size}
                          fill={product.color}
                          opacity={0.7 - (riseDistance / 200)}
                        />
                        {/* 상승 궤적 */}
                        <line
                          x1={riseX}
                          y1={productY}
                          x2={riseX}
                          y2={productY + 8}
                          stroke={product.color}
                          strokeWidth="0.5"
                          opacity="0.3"
                        />
                        {/* 생성물 라벨 */}
                        {riseDistance < 20 && (
                          <text
                            x={riseX + 8}
                            y={productY + 2}
                            className="text-xs"
                            fill={product.color}
                            opacity="0.7"
                          >
                            {product.name}
                          </text>
                        )}
                      </g>
                    ) : null;
                  })}

                  {/* 가스 입구 */}
                  <circle cx="100" cy="70" r="5" fill="#6b7280" />
                  <circle cx="250" cy="65" r="5" fill="#6b7280" />
                  <circle cx="400" cy="70" r="5" fill="#6b7280" />
                  <text x="250" y="55" textAnchor="middle" className="text-xs">Gas Inlet</text>

                  {/* 진공 배출 */}
                  <rect x="420" y="290" width="15" height="8" fill="#374151" />
                  <text x="427" y="310" textAnchor="middle" className="text-xs">Pump</text>

                  {/* 정보 표시 */}
                  <g transform="translate(60, 210)">
                    <rect x="0" y="0" width="110" height="60" fill="white" fillOpacity="0.95" stroke="#e5e7eb" strokeWidth="1" rx="3"/>

                    {isSimulating ? (
                      <>
                        <text x="5" y="12" className="text-xs font-semibold">실시간 상태</text>
                        <text x="5" y="25" className="text-xs">진행: {simulationProgress.toFixed(0)}%</text>
                        <text x="5" y="37" className="text-xs">깊이: {(etchDepth * 2).toFixed(0)}nm</text>
                        <text x="5" y="49" className="text-xs">{pressure}mT, {power}W</text>
                      </>
                    ) : (
                      <>
                        <text x="5" y="15" className="text-xs font-semibold">준비 상태</text>
                        <text x="5" y="28" className="text-xs">타겟: {etchTarget}</text>
                        <text x="5" y="41" className="text-xs">시작 대기중</text>
                      </>
                    )}
                  </g>

                  {/* 결과 표시 */}
                  {endpointDetected && (
                    <g transform="translate(350, 210)">
                      <rect x="0" y="0" width="80" height="60" fill="green" fillOpacity="0.1" stroke="#10b981" strokeWidth="2" rx="3"/>
                      <text x="5" y="12" className="text-xs font-semibold text-green-700">완료!</text>
                      <text x="5" y="25" className="text-xs text-green-700">속도: {etchRate.toFixed(0)}</text>
                      <text x="5" y="37" className="text-xs text-green-700">선택비: {selectivity.toFixed(1)}</text>
                      <text x="5" y="49" className="text-xs text-green-700">End Point</text>
                    </g>
                  )}

                  {/* CSS 애니메이션 */}
                  <defs>
                    <style>{`
                      @keyframes flash {
                        0% { r: 1; opacity: 1; }
                        50% { r: 3; opacity: 0.8; }
                        100% { r: 5; opacity: 0; }
                      }
                    `}</style>
                  </defs>
                </svg>
              </div>

              <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-4 text-sm bg-gray-50 p-4 rounded-lg">
                <div className="text-center">
                  <div className="font-semibold text-purple-700 mb-1">1. 플라즈마 분해</div>
                  <p className="text-gray-600">
                    {etchTarget === 'Si' && 'Cl2, HBr, Ar 가스가 플라즈마로 분해됨'}
                    {etchTarget === 'SiO2' && 'CF4, CHF3 가스가 F 라디칼 생성'}
                    {etchTarget === 'Si3N4' && 'CHF3, O2 가스가 F 라디칼과 O 라디칼 생성'}
                    {etchTarget === 'PR' && 'O2 가스가 O 라디칼로 분해됨'}
                  </p>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-red-700 mb-1">2. 표면 반응</div>
                  <p className="text-gray-600">
                    {etchTarget === 'Si' && 'Cl 라디칼이 Si와 반응하여 SiCl4 형성'}
                    {etchTarget === 'SiO2' && 'F 라디칼이 Si-O 결합을 끊어 SiF4 형성'}
                    {etchTarget === 'Si3N4' && 'F 라디칼이 Si-N 결합 공격, O2로 탄소 제거'}
                    {etchTarget === 'PR' && 'O 라디칼이 C-C, C-H 결합을 절단'}
                  </p>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-blue-700 mb-1">3. 생성물 배출</div>
                  <p className="text-gray-600">
                    {etchTarget === 'Si' && 'SiCl4가 기체상으로 상승하여 배출'}
                    {etchTarget === 'SiO2' && 'SiF4, CO2가 휘발성 기체로 배출'}
                    {etchTarget === 'Si3N4' && 'SiF4, N2가 안정한 기체로 배출'}
                    {etchTarget === 'PR' && 'CO2, H2O가 완전 연소 생성물로 배출'}
                  </p>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-orange-700 mb-1">4. 선택비 제어</div>
                  <p className="text-gray-600">
                    {etchTarget === 'Si' && 'HBr 첨가로 옥사이드 선택비 향상'}
                    {etchTarget === 'SiO2' && '폴리머 형성으로 Si 보호, 선택적 식각'}
                    {etchTarget === 'Si3N4' && '적절한 F/C 비율로 선택비 조절'}
                    {etchTarget === 'PR' && '무기물은 O2에 반응하지 않아 완전 선택적'}
                  </p>
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
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">극미세화 (3nm 이하)</h6>
                      <ul className="list-disc list-inside space-y-1 text-gray-700">
                        <li>Critical Dimension (CD) &lt; 10nm</li>
                        <li>Aspect Ratio &gt; 50:1</li>
                        <li>Line Edge Roughness (LER) &lt; 1nm</li>
                        <li>Plasma Damage 최소화</li>
                      </ul>
                    </div>
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">새로운 재료 도입</h6>
                      <ul className="list-disc list-inside space-y-1 text-gray-700">
                        <li>EUV Resist (CAR → Metal Resist)</li>
                        <li>High-k/Metal Gate Stack</li>
                        <li>2D Materials (MoS₂, Graphene)</li>
                        <li>Atomic Layer Etching (ALE) 필요</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-green-50 p-5 rounded-lg border-l-4 border-green-400">
                  <h5 className="text-lg font-semibold text-green-800 mb-3">글로벌 시장 현황</h5>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div className="bg-white p-4 rounded shadow">
                      <h6 className="font-semibold text-blue-700 mb-2">시장 점유율 (2024)</h6>
                      <ul className="space-y-1 text-gray-700">
                        <li>Lam Research: ~45%</li>
                        <li>Applied Materials: ~25%</li>
                        <li>Tokyo Electron: ~20%</li>
                        <li>Others: ~10%</li>
                      </ul>
                    </div>
                    <div className="bg-white p-4 rounded shadow">
                      <h6 className="font-semibold text-purple-700 mb-2">주요 고객사</h6>
                      <ul className="space-y-1 text-gray-700">
                        <li>TSMC (Taiwan)</li>
                        <li>Samsung (Korea)</li>
                        <li>Intel (USA)</li>
                        <li>SK Hynix (Korea)</li>
                      </ul>
                    </div>
                    <div className="bg-white p-4 rounded shadow">
                      <h6 className="font-semibold text-orange-700 mb-2">시장 규모</h6>
                      <ul className="space-y-1 text-gray-700">
                        <li>2024: $15B+</li>
                        <li>연평균 성장률: 8-10%</li>
                        <li>Logic &gt; Memory &gt; Others</li>
                        <li>아시아 시장 주도</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-yellow-50 p-5 rounded-lg border-l-4 border-yellow-400">
                  <h5 className="text-lg font-semibold text-yellow-800 mb-3">환경 및 규제 이슈</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">PFC 가스 규제</h6>
                      <ul className="list-disc list-inside space-y-1 text-gray-700">
                        <li>GWP (Global Warming Potential) 높음</li>
                        <li>CF₄: 7,390배, SF₆: 22,800배</li>
                        <li>EU REACH, 미국 EPA 규제 강화</li>
                        <li>대체 가스 개발 필요</li>
                      </ul>
                    </div>
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">Abatement 기술</h6>
                      <ul className="list-disc list-inside space-y-1 text-gray-700">
                        <li>Thermal/Plasma Abatement</li>
                        <li>90%+ 제거 효율 요구</li>
                        <li>운영비 증가 요인</li>
                        <li>In-situ Cleaning 기술 개발</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="bg-blue-50 p-5 rounded-lg border-l-4 border-blue-400">
                  <h5 className="text-lg font-semibold text-blue-800 mb-3">미래 기술 동향</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">Atomic Layer Processing</h6>
                      <ul className="list-disc list-inside space-y-1 text-gray-700">
                        <li>ALE (Atomic Layer Etching)</li>
                        <li>Self-limiting 반응</li>
                        <li>단원자층 정밀도 제어</li>
                        <li>Damage-free Processing</li>
                      </ul>
                    </div>
                    <div>
                      <h6 className="font-semibold text-gray-800 mb-2">AI/ML 적용</h6>
                      <ul className="list-disc list-inside space-y-1 text-gray-700">
                        <li>Real-time Process Control</li>
                        <li>Predictive Maintenance</li>
                        <li>Recipe Optimization</li>
                        <li>Virtual Metrology</li>
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
        return (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 p-6 rounded-lg">
              <h3 className="text-xl font-bold text-purple-800 mb-4">📊 식각 영향 인자 분석</h3>
              <p className="text-gray-700 leading-relaxed">
                식각 공정에 영향을 미치는 핵심 인자들을 개별적으로 조절하여
                각각이 식각 결과에 미치는 영향을 분석해보세요.
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold text-gray-800 mb-4">1. 압력(Pressure) 영향 분석</h4>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-gray-700">
                      압력 설정: {analysisPressure} mTorr
                    </label>
                    <input
                      type="range"
                      min="30"
                      max="200"
                      step="10"
                      value={analysisPressure}
                      onChange={(e) => setAnalysisPressure(Number(e.target.value))}
                      className="w-full"
                    />
                    <div className="text-center">
                      <button
                        onClick={() => setShowAnalysisResult(true)}
                        className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
                      >
                        분석 실행
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 space-y-2 text-sm bg-gray-50 p-4 rounded">
                    <h6 className="font-semibold">압력 효과 예측:</h6>
                    <p><strong>등방성 지수:</strong> {calculatePressureEffect(analysisPressure).toFixed(2)}</p>
                    <p><strong>프로파일:</strong> {analysisPressure > 100 ? '등방성 증가' : '이방성 유리'}</p>
                    <p><strong>평균 자유행정:</strong> {(10/analysisPressure).toFixed(3)} cm</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="bg-red-50 p-4 rounded border-l-4 border-red-400">
                    <h6 className="font-semibold text-red-800">고압력 조건 (&gt;100 mTorr)</h6>
                    <ul className="text-sm text-gray-700 mt-2 space-y-1">
                      <li>• 짧은 평균 자유행정 → 이온-분자 충돌 증가</li>
                      <li>• 등방성 식각 경향 → 언더컷 발생</li>
                      <li>• 낮은 이온 에너지 → 물리적 식각 감소</li>
                      <li>• 라디칼 농도 증가 → 화학적 식각 활성화</li>
                    </ul>
                  </div>

                  <div className="bg-blue-50 p-4 rounded border-l-4 border-blue-400">
                    <h6 className="font-semibold text-blue-800">저압력 조건 (&lt;100 mTorr)</h6>
                    <ul className="text-sm text-gray-700 mt-2 space-y-1">
                      <li>• 긴 평균 자유행정 → 직진성 향상</li>
                      <li>• 이방성 식각 → 수직 프로파일</li>
                      <li>• 높은 이온 에너지 → 물리적 식각 우세</li>
                      <li>• 라디칼 밀도 감소 → 선택비 저하 가능</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold text-gray-800 mb-4">2. RF 파워 영향 분석</h4>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-gray-700">
                      RF 파워: {analysisPower} W
                    </label>
                    <input
                      type="range"
                      min="200"
                      max="800"
                      step="50"
                      value={analysisPower}
                      onChange={(e) => setAnalysisPower(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  <div className="mt-4 space-y-2 text-sm bg-gray-50 p-4 rounded">
                    <h6 className="font-semibold">파워 효과 예측:</h6>
                    <p><strong>식각속도 지수:</strong> {calculatePowerEffect(analysisPower).toFixed(2)}</p>
                    <p><strong>플라즈마 밀도:</strong> {((analysisPower/300) * 5e11).toExponential(1)} cm⁻³</p>
                    <p><strong>바이어스 전압:</strong> ~{(analysisPower * 0.3).toFixed(0)} V</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="bg-orange-50 p-4 rounded border-l-4 border-orange-400">
                    <h6 className="font-semibold text-orange-800">고출력 조건 (&gt;500W)</h6>
                    <ul className="text-sm text-gray-700 mt-2 space-y-1">
                      <li>• 높은 플라즈마 밀도 → 빠른 식각속도</li>
                      <li>• 강한 이온 충격 → 플라즈마 데미지 위험</li>
                      <li>• 높은 바이어스 전압 → 이방성 증가</li>
                      <li>• 발열 증가 → 온도 제어 필요</li>
                    </ul>
                  </div>

                  <div className="bg-green-50 p-4 rounded border-l-4 border-green-400">
                    <h6 className="font-semibold text-green-800">저출력 조건 (&lt;300W)</h6>
                    <ul className="text-sm text-gray-700 mt-2 space-y-1">
                      <li>• 낮은 플라즈마 밀도 → 느린 식각속도</li>
                      <li>• 약한 이온 충격 → 데미지 최소화</li>
                      <li>• 낮은 바이어스 → 화학적 식각 우세</li>
                      <li>• 온도 안정성 → 정밀 제어 가능</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold text-gray-800 mb-4">3. 가스 비율 최적화</h4>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-gray-700">
                      주 가스 비율: {analysisGasRatio}%
                    </label>
                    <input
                      type="range"
                      min="10"
                      max="90"
                      step="5"
                      value={analysisGasRatio}
                      onChange={(e) => setAnalysisGasRatio(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  <div className="mt-4 space-y-2 text-sm bg-gray-50 p-4 rounded">
                    <h6 className="font-semibold">가스비 효과 예측:</h6>
                    <p><strong>선택비 지수:</strong> {calculateGasRatioEffect(analysisGasRatio).toFixed(2)}</p>
                    <p><strong>Cl₂/HBr 비율:</strong> {analysisGasRatio}:{100-analysisGasRatio}</p>
                    <p><strong>예상 선택비:</strong> {(10 * calculateGasRatioEffect(analysisGasRatio)).toFixed(1)}:1</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="bg-cyan-50 p-4 rounded border-l-4 border-cyan-400">
                    <h6 className="font-semibold text-cyan-800">Cl₂ 우세 (&gt;70%)</h6>
                    <ul className="text-sm text-gray-700 mt-2 space-y-1">
                      <li>• 높은 식각속도 → 생산성 향상</li>
                      <li>• 낮은 선택비 → 마스크 손상 위험</li>
                      <li>• 이방성 프로파일 → 수직 식각</li>
                      <li>• 폴리머 형성 부족 → 측벽 거칠음</li>
                    </ul>
                  </div>

                  <div className="bg-pink-50 p-4 rounded border-l-4 border-pink-400">
                    <h6 className="font-semibold text-pink-800">HBr 첨가 증가 (&gt;30%)</h6>
                    <ul className="text-sm text-gray-700 mt-2 space-y-1">
                      <li>• 높은 선택비 → 마스크 보호</li>
                      <li>• 낮은 식각속도 → 공정시간 증가</li>
                      <li>• 측벽 보호 → 부드러운 프로파일</li>
                      <li>• 온도 의존성 → 정밀 제어 필요</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h4 className="text-lg font-semibold text-gray-800 mb-4">종합 분석 결과</h4>

              {showAnalysisResult && (
                <div className="space-y-6">
                  <ResponsiveContainer width="100%" height={400}>
                    <LineChart data={generateAnalysisData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="pressure" label={{ value: '압력 (mTorr)', position: 'insideBottom', offset: -10 }} />
                      <YAxis label={{ value: '값', angle: -90, position: 'insideLeft' }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="etchRate" stroke="#8884d8" strokeWidth={2} name="식각속도" />
                      <Line type="monotone" dataKey="uniformity" stroke="#82ca9d" strokeWidth={2} name="균일성" />
                    </LineChart>
                  </ResponsiveContainer>

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-white p-4 rounded-lg text-center">
                      <div className="text-sm text-gray-600 mb-2">최적 압력</div>
                      <div className="text-2xl font-bold text-blue-700">100 mTorr</div>
                    </div>

                    <div className="bg-white p-4 rounded-lg text-center">
                      <div className="text-sm text-gray-600 mb-2">최적 파워</div>
                      <div className="text-2xl font-bold text-green-700">300 W</div>
                    </div>

                    <div className="bg-white p-4 rounded-lg text-center">
                      <div className="text-sm text-gray-600 mb-2">예상 식각속도</div>
                      <div className="text-2xl font-bold text-purple-700">
                        {(calculatePressureEffect(analysisPressure) * calculatePowerEffect(analysisPower) * 50).toFixed(0)} nm/min
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="bg-yellow-50 p-6 rounded-lg border-l-4 border-yellow-400">
              <h4 className="text-lg font-semibold text-yellow-800 mb-4">🤔 생각해 보기</h4>
              <div className="space-y-3 text-gray-700">
                <p><strong>Q1:</strong> 압력을 높일 때와 낮출 때 식각 프로파일이 어떻게 달라지는지 분석해보세요.</p>
                <p><strong>Q2:</strong> RF 파워를 과도하게 높이면 어떤 문제가 발생할 수 있을까요?</p>
                <p><strong>Q3:</strong> 가스 비율 조절로 식각속도와 선택비 사이의 trade-off를 어떻게 최적화할 수 있을까요?</p>
              </div>
            </div>
          </div>
        );

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
