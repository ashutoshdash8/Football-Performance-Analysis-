import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

base_folder = os.path.dirname(os.path.abspath(__file__))

# 1. Load data
df = pd.read_csv(os.path.join(base_folder, "players.csv"))
print("First 5 rows:")
print(df.head())
print("\nShape:", df.shape)
print("\nMissing values:\n", df.isnull().sum())

# 2. New columns
df["Goals_Per_Match"] = np.round(df["Goals"] / df["Matches"], 2)
df["Shot_Accuracy"] = np.round(np.where(df["Shots"] > 0, df["Shots_On_Target"] / df["Shots"] * 100, 0), 1)
df["Goal_Contributions"] = df["Goals"] + df["Assists"]
df["Best_Player_Score"] = np.round(df["Goal_Contributions"] / df["Matches"], 2)

# 3. Analysis
print("\nTop 3 scorers:")
print(df.nlargest(3, "Goals")[["Player", "Team", "Goals"]])

print("\nBest Player ranking (Goal Contributions / Matches):")
print(df.sort_values("Best_Player_Score", ascending=False)[["Player", "Team", "Position", "Goal_Contributions", "Matches", "Best_Player_Score"]].head(5).to_string(index=False))

best = df.loc[df["Best_Player_Score"].idxmax()]
print(f"\nBEST PLAYER: {best['Player']} ({best['Team']}) with score {best['Best_Player_Score']}")

print("\nTeam totals:")
team = df.groupby("Team")[["Goals", "Assists", "Shots"]].sum()
print(team)

print("\nAverage pass accuracy by position:")
print(df.groupby("Position")["Pass_Accuracy"].mean().round(1))

print("\nCorrelation Shots vs Goals:", round(np.corrcoef(df["Shots"], df["Goals"])[0, 1], 2))

# 4. Charts (window 1)
fig, axes = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle("Football Performance Analysis", fontsize=16, fontweight="bold")

sns.barplot(data=df.sort_values("Goals", ascending=False).head(6), x="Player", y="Goals",
            hue="Player", palette="viridis", legend=False, ax=axes[0, 0])
axes[0, 0].set_title("Top 6 Goal Scorers")

team.plot(kind="bar", ax=axes[0, 1], rot=0)
axes[0, 1].set_title("Team Goals, Assists & Shots")

sns.scatterplot(data=df, x="Shots", y="Goals", hue="Position", s=100, ax=axes[1, 0])
axes[1, 0].set_title("Shots vs Goals")

sns.boxplot(data=df, x="Position", y="Pass_Accuracy", hue="Position", legend=False, ax=axes[1, 1])
axes[1, 1].set_title("Pass Accuracy by Position")

plt.tight_layout()
plt.savefig(os.path.join(base_folder, "football_analysis.png"), dpi=120)

# Window 2: Best player chart
plt.figure(figsize=(10, 6))
top_best = df.sort_values("Best_Player_Score", ascending=False).head(8)
sns.barplot(data=top_best, x="Player", y="Best_Player_Score", hue="Team", dodge=False)
plt.title("Best Player Score (Goal Contributions per Match)")
plt.tight_layout()
plt.savefig(os.path.join(base_folder, "best_players.png"), dpi=120)

# Window 3: Heatmap
plt.figure(figsize=(11, 8))
sns.heatmap(df.corr(numeric_only=True), annot=True, fmt=".2f", cmap="coolwarm", linewidths=0.5)
plt.title("Correlation Heatmap")
plt.tight_layout()
plt.savefig(os.path.join(base_folder, "heatmap.png"), dpi=120)

plt.show()
