import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Input,
  Button,
  Icon,
  Time,
  Typewriter,
} from 'animal-island-ui';
import type { Message, UserMemory } from '../types';
import { chatStream } from '../api';
import PreferencesPanel from './PreferencesPanel';

interface ChatPageProps {
  userId: string;
  onLogout: () => void;
}

export default function ChatPage({ userId, onLogout }: ChatPageProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: `你好！我是「随便吃」AI 助手 🍳\n\n告诉我你今天想吃什么，或者直接说「随便」，我来给你推荐！`,
    },
  ]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);
  const [connected, setConnected] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [welcomeDone, setWelcomeDone] = useState(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || streaming) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: msg }]);
    setStreaming(true);

    try {
      let accumulated = '';
      const assistantMsg: Message = { role: 'assistant', content: '' };
      setMessages((prev) => [...prev, assistantMsg]);

      for await (const token of chatStream(userId, msg)) {
        accumulated += token;
        setMessages((prev) => {
          const updated = [...prev];
          if (
            updated.length > 0 &&
            updated[updated.length - 1].role === 'assistant'
          ) {
            updated[updated.length - 1] = {
              role: 'assistant',
              content: accumulated,
            };
          }
          return updated;
        });
      }

      if (!accumulated) {
        setMessages((prev) => {
          const updated = [...prev];
          if (
            updated.length > 0 &&
            updated[updated.length - 1].role === 'assistant'
          ) {
            updated[updated.length - 1] = {
              role: 'assistant',
              content: '抱歉，我没有获取到有效回复，请重新试试。',
            };
          }
          return updated;
        });
      }
    } catch (err: unknown) {
      const errMsg =
        err instanceof Error ? err.message : '请求失败，请检查 API 服务';
      setMessages((prev) => [...prev, { role: 'assistant', content: `错误：${errMsg}` }]);
    } finally {
      setStreaming(false);
      setConnected(true);
    }
  };

  const handlePrefSaved = (_memory: UserMemory) => {
    // Re-inject preferences into agent by sending a system note
    // Actually, the agent auto-refreshes on save via API
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <Icon name="icon-miles" size={28} bounce />
          <h1 className="chat-title">随便吃</h1>
          <Time />
        </div>
        <div className="chat-header-right">
          <span className="chat-user-badge">
            <Icon name="icon-critterpedia" size={16} />
            {userId}
          </span>
          <span
            className={`chat-status-dot ${connected ? 'connected' : 'disconnected'}`}
            title={connected ? 'API 已连接' : 'API 未连接'}
          />
          <Button size="small" type="primary" onClick={() => setShowPrefs(true)}>
            偏好
          </Button>
          <Button size="small" type="text" onClick={onLogout}>
            退出
          </Button>
        </div>
      </header>

      {/* Messages */}
      <div className="chat-messages">
        <div className="chat-messages-inner">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`message-row message-row--${msg.role}`}
            >
              {msg.role === 'assistant' && (
                <div className="message-avatar">
                  <Icon name="icon-chat" size={20} />
                </div>
              )}
              <div className={`message-bubble message-bubble--${msg.role}`}>
                {msg.role === 'assistant' && idx === 0 && !welcomeDone ? (
                  <Typewriter speed={40} onDone={() => setWelcomeDone(true)}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                  </Typewriter>
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                    {streaming && msg.role === 'assistant' && idx === messages.length - 1 && (
                      <span className="streaming-cursor">▍</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <div className="chat-input-row">
          <Input
            size="large"
            placeholder={
              streaming ? 'AI 正在回复...' : '今天想吃什么？说「随便」让我来推荐！'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            suffix={
              <button
                className="chat-send-btn"
                onClick={handleSend}
                disabled={streaming || !input.trim()}
              >
                <Icon name="icon-chat" size={20} />
              </button>
            }
          />
        </div>
      </div>

      {/* Preferences Modal */}
      {showPrefs && (
        <PreferencesPanel
          userId={userId}
          onClose={() => setShowPrefs(false)}
          onSaved={handlePrefSaved}
        />
      )}
    </div>
  );
}
