import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set seed for reproducibility
np.random.seed(42)

# Parameters
n_players = 1000
n_sessions = 100000  # Total number of sessions
current_date = datetime.now()
# relaease date was 12th Nov 2021
time_frame_days = (current_date - datetime(2021, 11, 12)).days

# Player IDs
players = np.array([f'Player_{i}' for i in range(n_players)])

# Game modes, roles, platforms
game_modes = np.array(['Conquest', 'Breakthrough', 'Hazard Zone'])
player_roles = np.array(['Assault', 'Engineer', 'Support', 'Recon'])
platforms = np.array(['PC', 'PlayStation', 'Xbox'])

# Adjusted country distribution (weighted probabilities)
countries = np.array(['USA', 'Canada', 'UK', 'Germany', 'France', 'Japan', 'Australia', 'Brazil', 'South Korea'])
country_weights = np.array([0.30, 0.10, 0.15, 0.15, 0.10, 0.08, 0.05, 0.05, 0.02])

# Assign each player a country & platform (consistent across all sessions)
player_country = {player: np.random.choice(countries, p=country_weights) for player in players}
player_platform = {player: np.random.choice(platforms) for player in players}

# Generate First Session Dates
first_session_days = np.random.randint(0, time_frame_days, size=n_players)
player_first_sessions = {
    player: current_date - timedelta(days=int(day), hours=np.random.randint(0, 24), minutes=np.random.randint(0, 60))
    for player, day in zip(players, first_session_days)
}

# Generate Sessions with Decaying Frequency
session_data = []
for player in players:
    first_session = player_first_sessions[player]
    total_sessions = np.random.randint(20, 200)  # Players have different total session counts

    # Generate increasing gaps between sessions
    gaps = np.cumsum(np.random.exponential(scale=1, size=total_sessions))  
    session_dates = [first_session + timedelta(days=int(gap), hours=np.random.randint(0, 24), minutes=np.random.randint(0, 60)) for gap in gaps if first_session + timedelta(days=int(gap), hours=np.random.randint(0, 24), minutes=np.random.randint(0, 60)) <= current_date]

    for session_date in session_dates:
        session_data.append([player, session_date])

# Convert to DataFrame
df = pd.DataFrame(session_data, columns=['Player_ID', 'Session_Date'])

# Assign game attributes
df['Match_Mode'] = np.random.choice(game_modes, len(df))
df['Role'] = np.random.choice(player_roles, len(df))
df['Country'] = df['Player_ID'].map(player_country)
df['Platform'] = df['Player_ID'].map(player_platform)

# Performance Metrics Based on Experience
base_kills = {'Recon': (2, 45), 'Support': (0, 40), 'Default': (5, 45)}
base_headshots = (0, 10)
base_deaths = (5, 45)
base_assists = {'Support': (2, 35), 'Engineer': (2, 35), 'Default': (0, 25)}
base_revives = {'Support': (10, 60), 'Default': (5, 50)}
base_achievements = (0, 5)

# Scale performance based on how far into a player's session history this game is
df['Session_Number'] = df.groupby('Player_ID').cumcount() + 1
df['Experience_Level'] = (df['Session_Number'] / df.groupby('Player_ID')['Session_Number'].transform('max')).round(2)

# Define scaling function
def scale_stat(base_range, experience):
    return np.random.randint(base_range[0], base_range[1]) + int(experience * 10)

# Apply experience-based scaling
df['Kills'] = [scale_stat(base_kills.get(role, base_kills['Default']), exp) for role, exp in zip(df['Role'], df['Experience_Level'])]
df['Headshots'] = [min(scale_stat(base_headshots, exp), kills) for kills, exp in zip(df['Kills'], df['Experience_Level'])]
df['Deaths'] = [scale_stat(base_deaths, exp) for exp in df['Experience_Level']]
df['Assists'] = [scale_stat(base_assists.get(role, base_assists['Default']), exp) for role, exp in zip(df['Role'], df['Experience_Level'])]
df['Revives'] = [scale_stat(base_revives.get(role, base_revives['Default']), exp) for role, exp in zip(df['Role'], df['Experience_Level'])]
df['Vehicle_Kills'] = np.random.randint(0, (df['Kills'] * 0.4).astype(int) + 1, size=len(df))
df['Achievements'] = [scale_stat(base_achievements, exp) for exp in df['Experience_Level']]

df['Sector_Captures'] = np.where(df['Match_Mode'].isin(['Conquest', 'Breakthrough']),
                                 np.random.randint(0, 3, size=len(df)), 0)

df['K_D_Ratio'] = df['Kills'] / df['Deaths']
df['K_D_Ratio'] = df['K_D_Ratio'].round(2).fillna(0)  # Handle divide-by-zero cases

df['Match_Outcome'] = np.where(np.random.rand(len(df)) > 0.5, 'Win', 'Loss')

# Remove unnecessary columns
df = df.drop(columns=['Experience_Level'])

# Sort the data by Player_ID and Session_Date
df = df.sort_values(by=['Player_ID', 'Session_Date'])

# Save Gameplay Data
df.to_csv('battlefield_gameplay_data.csv', index=False)

#sort the data by player id and session date
print(df.head(20))
