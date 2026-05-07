export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface UserPreferences {
  tastes: string[];
  dislikes: string[];
  avoid: string[];
  difficulty_preference: number | null;
}

export interface RecentMeal {
  date: string;
  dish: string;
}

export interface UserMemory {
  preferences: UserPreferences;
  recent_meals: RecentMeal[];
}
