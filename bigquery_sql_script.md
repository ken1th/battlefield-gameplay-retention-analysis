# Getting the First Game Date

The following SQL query creates or replaces a table that adds two new columns: 
1. `First_Game_Date` - the timestamp of the player's first recorded game session.
2. `Days_Since_First_Game` - the number of days elapsed since the player's first game.

```sql
CREATE OR REPLACE TABLE `bf_gameplay.gameplay_ext` AS
SELECT 
    *,
    MIN(TIMESTAMP(Session_Date)) OVER (PARTITION BY Player_ID) AS First_Game_Date,
    TIMESTAMP_DIFF(TIMESTAMP(Session_Date), MIN(TIMESTAMP(Session_Date)) OVER (PARTITION BY Player_ID), SECOND) / 86400.0 AS Days_Since_First_Game
FROM `bf_gameplay.gameplay`;
```

# Calculating Retention Rates by Player Segments

This SQL query creates a table that calculates **player retention rates** over the first 30 days, segmented by different player attributes such as country, platform, match mode, and role. 

### **Breakdown of the Query:**
1. **Base Table (`base`)**: Filters gameplay data to only include the first 30 days from a player's first login and extracts relevant player attributes.
2. **Cohort Sizes (`cohort_sizes`)**: Determines the number of unique players who logged in on **Day 0** for each category (e.g., country, platform).
3. **Retention Counts (`retention_counts`)**: Counts the number of **retained players** for each subsequent day (Day 1 to 30) in each category.
4. **Final Calculation**: Joins `cohort_sizes` and `retention_counts` to compute the **retention rate** as:
Retention Rate = `Retained Players` / `Total Players on Day 0`
5. **Sorting and Output**: The results are sorted by category, dimension value (e.g., country name), and day since first login.

This table helps analyze **player engagement** by understanding how well different player groups retain over time.

```sql
CREATE OR REPLACE TABLE `bf_gameplay.retention_rates` AS
WITH base AS (
  SELECT 
    Player_ID,
    CAST(FLOOR(Days_Since_First_Game) AS INT64) AS Day_from_first_login,
    Country,
    Platform,
    Match_Mode,
    Role
  FROM `bf_gameplay.gameplay_ext`
  WHERE Days_Since_First_Game BETWEEN 0 AND 30 -- Limit to first 30 days
),
cohort_sizes AS (
  -- Count the number of players on Day 0 for each category & group
  SELECT 
    1 AS Day_from_first_login, 
    'Country' AS Category, Country AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Total_Players 
  FROM base WHERE Day_from_first_login = 0 GROUP BY Country

  UNION ALL

  SELECT 
    1 AS Day_from_first_login, 
    'Platform' AS Category, Platform AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Total_Players 
  FROM base WHERE Day_from_first_login = 0 GROUP BY Platform

  UNION ALL

  SELECT 
    1 AS Day_from_first_login, 
    'Match_Mode' AS Category, Match_Mode AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Total_Players 
  FROM base WHERE Day_from_first_login = 0 GROUP BY Match_Mode

  UNION ALL

  SELECT 
    1 AS Day_from_first_login, 
    'Role' AS Category, Role AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Total_Players 
  FROM base WHERE Day_from_first_login = 0 GROUP BY Role

  UNION ALL

  -- "Overall" category: Retention rate across all players
  SELECT 
    1 AS Day_from_first_login, 
    'Overall' AS Category, 'Overall' AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Total_Players 
  FROM base WHERE Day_from_first_login = 0 
),
retention_counts AS (
  -- Count retained players per day for each category & group
  SELECT 
    Day_from_first_login, 
    'Country' AS Category, Country AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Retained_Players 
  FROM base GROUP BY Day_from_first_login, Country

  UNION ALL

  SELECT 
    Day_from_first_login, 
    'Platform' AS Category, Platform AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Retained_Players 
  FROM base GROUP BY Day_from_first_login, Platform

  UNION ALL

  SELECT 
    Day_from_first_login, 
    'Match_Mode' AS Category, Match_Mode AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Retained_Players 
  FROM base GROUP BY Day_from_first_login, Match_Mode

  UNION ALL

  SELECT 
    Day_from_first_login, 
    'Role' AS Category, Role AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Retained_Players 
  FROM base GROUP BY Day_from_first_login, Role

  UNION ALL

  -- "Overall" category: Retention rate across all players
  SELECT 
    Day_from_first_login, 
    'Overall' AS Category, 'Overall' AS Dimension_Value, COUNT(DISTINCT Player_ID) AS Retained_Players 
  FROM base GROUP BY Day_from_first_login
)
SELECT 
  rc.Day_from_first_login,
  rc.Category,
  rc.Dimension_Value,
  SAFE_DIVIDE(rc.Retained_Players, cs.Total_Players) AS Retention_Rate
FROM retention_counts rc
JOIN cohort_sizes cs
ON rc.Category = cs.Category AND rc.Dimension_Value = cs.Dimension_Value
ORDER BY rc.Category, rc.Dimension_Value, rc.Day_from_first_login;
```

# Monthly Cohort-Based Retention Analysis

This SQL query calculates **cohort-based retention rates** by tracking player activity at specific time intervals (1, 7, and 30 days) after their first session. The results are grouped by the **month of first play** to analyze player retention trends over time.

### **Breakdown of the Query:**
1. **Determine First Session Date (`first_sessions`)**: Identifies the **first-ever session date** for each player.
2. **Extract Distinct Session Dates (`sessions`)**: Collects **unique session dates** for each player to track their return visits.
3. **Define Cohorts (`cohorts`)**: Groups players into cohorts based on the **month of their first session** (formatted as YYYY-MM).
4. **Calculate Retention (`retention`)**:
   - Defines **retention periods** (1, 7, and 30 days after the first session).
   - Counts the **total cohort size** (players who first played in a given month).
   - Counts how many of these players **returned** on the specified retention days.
5. **Final Output**:
   - Computes the **retention rate** as:
     Retention Rate = `Retained Players` / `Cohort Size`
   - Orders the results by **cohort month** and **retention period** for easy trend analysis.

This table provides valuable insights into **player engagement over time**, helping to identify trends in player retention across different cohorts.

```sql
CREATE OR REPLACE TABLE `bf_gameplay.retention_by_date` AS
WITH
  -- Determine each player's first session date (their cohort date)
  first_sessions AS (
    SELECT 
      Player_ID, 
      MIN(DATE(Session_Date)) AS first_session_date
    FROM `bf_gameplay.gameplay_ext`
    GROUP BY Player_ID
  ),
  -- Get distinct sessions by date for each player
  sessions AS (
    SELECT DISTINCT 
      Player_ID, 
      DATE(Session_Date) AS session_date
    FROM `bf_gameplay.gameplay_ext`
  ),
  -- Define cohorts by the month of first play (formatted as YYYY-MM)
  cohorts AS (
    SELECT 
      Player_ID,
      first_session_date,
      FORMAT_DATE('%Y-%m', first_session_date) AS cohort_month
    FROM first_sessions
  ),
  -- For each cohort and each retention offset, count the number of players
  -- and how many returned exactly offset days after their first session.
  retention AS (
    SELECT 
      c.cohort_month,
      offset AS retention_day,
      COUNT(DISTINCT c.Player_ID) AS cohort_size,
      COUNT(DISTINCT CASE 
                       WHEN s.Player_ID IS NOT NULL THEN c.Player_ID 
                     END) AS retained_players
    FROM cohorts c
    -- Check for offsets of 1, 7, and 30 days
    CROSS JOIN UNNEST([1, 7, 30]) AS offset
    LEFT JOIN sessions s 
      ON s.Player_ID = c.Player_ID 
         AND s.session_date = DATE_ADD(c.first_session_date, INTERVAL offset DAY)
    GROUP BY c.cohort_month, offset
  )
  
SELECT 
  cohort_month,
  retention_day AS retention_period,
  cohort_size,
  retained_players,
  SAFE_DIVIDE(retained_players, cohort_size) AS retention_rate
FROM retention
ORDER BY cohort_month, retention_period;
```