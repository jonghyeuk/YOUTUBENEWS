import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="App">
      <header className="App-header">
        <h1>EduNews</h1>
        <p>로컬 React 애플리케이션에 오신 것을 환영합니다!</p>
        <div className="card">
          <button onClick={() => setCount((count) => count + 1)}>
            count is {count}
          </button>
        </div>
      </header>
    </div>
  )
}

export default App
