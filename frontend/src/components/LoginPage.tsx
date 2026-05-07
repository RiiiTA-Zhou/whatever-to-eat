import { useState } from 'react';
import { Card, Input, Button, Divider, Icon } from 'animal-island-ui';
import { registerUser, loadMemory } from '../api';

interface LoginPageProps {
  onLogin: (userId: string) => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [userId, setUserId] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const handleRegister = async () => {
    const id = userId.trim();
    if (!id) {
      setStatus({ type: 'error', text: '请输入用户 ID' });
      return;
    }

    setLoading(true);
    setStatus(null);

    try {
      const data = await registerUser(id);
      const msg =
        data.status === 'exists'
          ? `欢迎回来，${id}！`
          : `新用户 ${id} 创建成功！`;

      // Verify we can load memory
      await loadMemory(id);

      setStatus({ type: 'success', text: msg });
      setTimeout(() => onLogin(id), 600);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : '注册失败，请检查 API 服务';
      setStatus({ type: 'error', text: message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-bg-decor" />
      <Card type="title" className="login-card">
        <div className="login-header">
          <Icon name="icon-shopping" size={56} bounce />
          <h1 className="login-title">随便吃</h1>
          <p className="login-subtitle">
            今天吃什么？让 AI 帮你决定！
          </p>
        </div>

        <Divider type="wave-yellow" />

        <div className="login-form">
          <label className="login-label">用户 ID</label>
          <Input
            size="large"
            placeholder="输入你的用户 ID"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRegister()}
            allowClear
          />

          <Button
            type="primary"
            size="large"
            block
            loading={loading}
            onClick={handleRegister}
          >
            注册 / 登录
          </Button>

          {status && (
            <div className={`login-status login-status--${status.type}`}>
              {status.text}
            </div>
          )}
        </div>

        <div className="login-tips">
          <p>💡 第一次使用？输入任意 ID 即可自动注册</p>
          <p>🍳 AI 会根据你的口味偏好推荐菜谱</p>
        </div>
      </Card>
    </div>
  );
}
