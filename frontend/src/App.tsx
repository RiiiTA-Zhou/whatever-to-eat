import { useState } from 'react';
import { Cursor, Footer } from 'animal-island-ui';
import LoginPage from './components/LoginPage';
import ChatPage from './components/ChatPage';
import './App.css';

function App() {
  const [userId, setUserId] = useState<string | null>(() => {
    return sessionStorage.getItem('whatever-to-eat-user');
  });

  const handleLogin = (id: string) => {
    sessionStorage.setItem('whatever-to-eat-user', id);
    setUserId(id);
  };

  const handleLogout = () => {
    sessionStorage.removeItem('whatever-to-eat-user');
    setUserId(null);
  };

  return (
    <Cursor>
      <div className="app">
        {userId ? (
          <ChatPage userId={userId} onLogout={handleLogout} />
        ) : (
          <LoginPage onLogin={handleLogin} />
        )}
        <Footer type="sea" />
      </div>
    </Cursor>
  );
}

export default App;
