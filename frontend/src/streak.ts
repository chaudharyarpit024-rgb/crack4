export type StreakDay = {
  date: string;
  day_name: string;
  day_abbr: string;
  logged: boolean;
  is_today: boolean;
};

export type StreakData = {
  current_streak: number;
  longest_streak: number;
  logged_today: boolean;
  streak_active: boolean;
  today_date: string;
  weekly_activity: StreakDay[];
  message: string;
};
