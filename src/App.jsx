import EtchSimulator from './EtchSimulator'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Tailwind 테스트 */}
      <div className="p-8">
        <div className="bg-blue-500 text-white p-6 rounded-lg shadow-lg mb-4">
          <h1 className="text-3xl font-bold">Tailwind CSS 테스트</h1>
          <p className="mt-2">이 텍스트가 파란 배경에 흰색 글자로 보이면 Tailwind가 작동하는 것입니다!</p>
        </div>
        <div className="bg-gradient-to-r from-purple-400 via-pink-500 to-red-500 text-white p-6 rounded-lg shadow-xl">
          <p className="text-xl font-semibold">그라데이션도 보이나요?</p>
        </div>
      </div>

      <EtchSimulator />
    </div>
  )
}

export default App
