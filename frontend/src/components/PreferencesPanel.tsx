import { useState, useEffect } from 'react';
import {
  Card,
  Input,
  Button,
  Select,
  Divider,
} from 'animal-island-ui';
import type { UserMemory, UserPreferences } from '../types';
import { loadMemory, saveMemory } from '../api';

interface PreferencesPanelProps {
  userId: string;
  onClose: () => void;
  onSaved: (memory: UserMemory) => void;
}

function parseList(text: string): string[] {
  return text
    .split(/[,，、\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatList(list: string[] | undefined): string {
  return (list || []).join('，');
}

function formatRecentMeals(meals: UserMemory['recent_meals'] | undefined): string {
  return (meals || [])
    .map((m) => `${m.date}: ${m.dish}`)
    .join('\n');
}

function parseRecentMeals(text: string): { date: string; dish: string }[] {
  const meals: { date: string; dish: string }[] = [];
  for (const line of text.trim().split('\n')) {
    const l = line.trim();
    if (!l) continue;
    const idx = l.indexOf(':');
    if (idx > 0) {
      meals.push({ date: l.slice(0, idx).trim(), dish: l.slice(idx + 1).trim() });
    } else {
      meals.push({
        date: new Date().toISOString().slice(0, 10),
        dish: l,
      });
    }
  }
  return meals;
}

const difficultyOptions = [
  { key: '1', label: '⭐ 新手小白' },
  { key: '2', label: '⭐⭐ 简单' },
  { key: '3', label: '⭐⭐⭐ 中等' },
  { key: '4', label: '⭐⭐⭐⭐ 较难' },
  { key: '5', label: '⭐⭐⭐⭐⭐ 专业大厨' },
];

export default function PreferencesPanel({
  userId,
  onClose,
  onSaved,
}: PreferencesPanelProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tastes, setTastes] = useState('');
  const [dislikes, setDislikes] = useState('');
  const [avoid, setAvoid] = useState('');
  const [difficulty, setDifficulty] = useState('3');
  const [recentMeals, setRecentMeals] = useState('');
  const [status, setStatus] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  useEffect(() => {
    loadMemory(userId)
      .then((memory) => {
        const prefs = memory.preferences || {};
        setTastes(formatList(prefs.tastes));
        setDislikes(formatList(prefs.dislikes));
        setAvoid(formatList(prefs.avoid));
        setDifficulty(String(prefs.difficulty_preference || 3));
        setRecentMeals(formatRecentMeals(memory.recent_meals));
      })
      .catch((err: unknown) => {
        setStatus({
          type: 'error',
          text: err instanceof Error ? err.message : '加载偏好失败',
        });
      })
      .finally(() => setLoading(false));
  }, [userId]);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);

    const memory: Partial<UserMemory> = {
      preferences: {
        tastes: parseList(tastes),
        dislikes: parseList(dislikes),
        avoid: parseList(avoid),
        difficulty_preference: Number(difficulty) || null,
      } as UserPreferences,
      recent_meals: parseRecentMeals(recentMeals),
    };

    try {
      await saveMemory(userId, memory);
      setStatus({ type: 'success', text: '偏好已保存！' });
      onSaved(memory as UserMemory);
      setTimeout(onClose, 800);
    } catch (err: unknown) {
      setStatus({
        type: 'error',
        text: err instanceof Error ? err.message : '保存失败',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="preferences-overlay" onClick={onClose}>
        <Card className="preferences-panel" onClick={(e) => e.stopPropagation()}>
          <div className="preferences-loading">加载中...</div>
        </Card>
      </div>
    );
  }

  return (
    <div className="preferences-overlay" onClick={onClose}>
      <Card
        className="preferences-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="preferences-header">
          <h2>偏好设置</h2>
          <button className="preferences-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="preferences-body">
          <div className="pref-field">
            <label>喜欢的口味</label>
            <Input
              placeholder="例：清淡，鲜香，辣"
              value={tastes}
              onChange={(e) => setTastes(e.target.value)}
              allowClear
            />
          </div>

          <div className="pref-field">
            <label>不喜欢的食物</label>
            <Input
              placeholder="例：太油腻的，内脏"
              value={dislikes}
              onChange={(e) => setDislikes(e.target.value)}
              allowClear
            />
          </div>

          <div className="pref-field">
            <label>忌口 / 过敏</label>
            <Input
              placeholder="例：牛奶，海鲜"
              value={avoid}
              onChange={(e) => setAvoid(e.target.value)}
              allowClear
            />
          </div>

          <div className="pref-field">
            <label>菜谱难度偏好</label>
            <Select
              value={difficulty}
              onChange={setDifficulty}
              options={difficultyOptions}
              placeholder="选择难度"
            />
          </div>

          <div className="pref-field">
            <label>近期饮食记录</label>
            <textarea
              className="pref-textarea"
              placeholder={'格式：日期: 菜品\n例：2026-04-27: 宫保鸡丁'}
              value={recentMeals}
              onChange={(e) => setRecentMeals(e.target.value)}
              rows={4}
            />
          </div>

          <Divider type="line-yellow" />

          <Button
            type="primary"
            size="large"
            block
            loading={saving}
            onClick={handleSave}
          >
            保存偏好
          </Button>

          {status && (
            <div className={`pref-status pref-status--${status.type}`}>
              {status.text}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
