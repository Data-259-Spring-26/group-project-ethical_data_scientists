# March Madness 2026 - Odds Variability Analysis

## Overview

This analysis examines the volatility and variability of prediction market odds across 125 March Madness games (63 Men's, 62 Women's) from Polymarket.

## Output File

**File:** `odds_variability_analysis.csv`  
**Size:** 79 KB  
**Rows:** 125 games (1 game excluded due to incomplete data)  
**Columns:** 41 metrics per game

## Metrics Calculated

### Favorite Team Metrics (prefix: `fav_`)
- **mean_prob** - Average probability throughout the observation period
- **std_prob** - Standard deviation of probabilities
- **min_prob / max_prob** - Lowest and highest probabilities observed
- **prob_range** - Difference between max and min (total swing)
- **cv** - Coefficient of Variation (CV = std/mean × 100) - normalized volatility
- **direction_changes** - Number of times trend reversed
- **max_jump** - Largest single probability change between 5-minute intervals
- **avg_abs_change** - Average magnitude of change between intervals
- **start_prob / end_prob** - Opening and closing probabilities
- **total_change** - Net change from start to end
- **pct_active** - Percentage of 5-minute intervals with actual trades
- **total_volume** - Total shares traded for this outcome

### Underdog Team Metrics (prefix: `und_`)
Same metrics as favorite, calculated for the underdog (lower average probability team)

### Game-Level Metrics
- **avg_combined_cv** - Average CV of both teams (primary volatility measure)
- **max_cv** - Maximum CV between the two teams
- **prob_spread_start** - Initial probability difference between teams
- **prob_spread_end** - Final probability difference between teams
- **spread_change** - Change in probability spread (positive = favorite strengthened)
- **total_volume** - Combined trading volume for both outcomes
- **total_intervals** - Number of 5-minute intervals in observation window
- **time_span_hours** - Duration of trading activity

## Key Findings

### Overall Statistics
- **Mean CV across all games:** 178.78%
- **Median CV:** 140.00%
- **Maximum CV:** 1,204.00%
- **Mean probability range:** 0.364 (36.4 percentage points)
- **Mean total volume:** 1,430,257 shares

### Men's vs Women's Tournament

| Metric | Men's (63 games) | Women's (62 games) | Ratio |
|--------|------------------|-------------------|-------|
| **Mean CV** | 281.32% | 74.58% | 3.8x |
| **Median CV** | 233.62% | 67.24% | 3.5x |
| **Mean Prob Range** | 0.393 | 0.334 | 1.2x |
| **Mean Volume** | 2,811,741 shares | 26,490 shares | 106x |

**Key Insight:** Men's tournament markets are dramatically more volatile (3.8x higher CV) and have 106x more trading volume than Women's markets.

## Top 10 Most Volatile Games

| Rank | Matchup | Category | Avg CV | Prob Range | Volume |
|------|---------|----------|--------|------------|--------|
| 1 | High Point vs Wisconsin | Men's | 604.6% | 0.939 | 1.36M |
| 2 | Iowa vs Florida | Men's | 600.6% | 0.859 | 2.26M |
| 3 | Kentucky vs Santa Clara | Men's | 538.0% | 0.679 | 1.42M |
| 4 | VCU vs North Carolina | Men's | 528.3% | 0.975 | 2.14M |
| 5 | TCU vs Ohio State | Men's | 509.3% | 0.669 | 1.15M |
| 6 | Illinois vs Houston | Men's | 485.0% | 0.569 | 4.60M |
| 7 | UConn vs Duke | Men's | 475.0% | 0.959 | 3.19M |
| 8 | Arizona vs Purdue | Men's | 462.7% | 0.509 | 3.71M |
| 9 | Duke vs St. John's | Men's | 453.6% | 0.619 | 2.34M |
| 10 | Tennessee vs Virginia | Men's | 438.0% | 0.419 | 1.40M |

**Notable:** All top 10 most volatile games were Men's tournament games.

## Top 10 Least Volatile Games

| Rank | Matchup | Category | Avg CV | Prob Range | Volume |
|------|---------|----------|--------|------------|--------|
| 1 | TCU vs UCSD | Women's | 2.5% | 0.042 | 3,145 |
| 2 | Kentucky vs James Madison | Women's | 4.3% | 0.099 | 3,756 |
| 3 | Alabama vs Rhode Island | Women's | 4.3% | 0.189 | 5,195 |
| 4 | LSU vs Texas Tech | Women's | 4.7% | 0.129 | 14,983 |
| 5 | UConn vs North Carolina | Women's | 5.1% | 0.049 | 57,101 |
| 6 | South Carolina vs USC | Women's | 5.2% | 0.119 | 3,027 |
| 7 | UCLA vs Oklahoma State | Women's | 5.8% | 0.429 | 68,230 |
| 8 | Baylor vs Nebraska | Women's | 6.9% | 0.521 | 866 |
| 9 | Ole Miss vs Gonzaga | Women's | 7.5% | 0.139 | 1,679 |
| 10 | Louisville vs Vermont | Women's | 8.4% | 0.030 | 3,765 |

**Notable:** All top 10 least volatile games were Women's tournament games.

## Volatility Patterns

### High Volatility Characteristics
Games with CV > 400% typically exhibited:
- Large probability swings (0.5-1.0 range)
- Heavy trading during game events
- Initial uncertainty about outcomes
- Many direction changes (10-20+)
- High single-interval jumps (0.2-0.7)

### Low Volatility Characteristics
Games with CV < 10% typically exhibited:
- Narrow probability ranges (0.03-0.20)
- Sparse trading activity
- Strong early favorites maintained throughout
- Few direction changes (0-5)
- Small incremental moves

## Interpretation Guide

### Coefficient of Variation (CV)
- **0-50%**: Very stable market, little uncertainty
- **50-150%**: Moderate volatility, typical competitive game
- **150-300%**: High volatility, significant uncertainty
- **300%+**: Extreme volatility, major odds swings

### Probability Range
- **0.00-0.10**: Extremely stable (dominant favorite)
- **0.10-0.30**: Stable (clear favorite throughout)
- **0.30-0.50**: Moderate swings (competitive or shifting momentum)
- **0.50+**: Wild swings (massive uncertainty or game-changing events)

### Direction Changes
- **0-5**: Steady trend (one-sided game or blowout)
- **5-15**: Normal fluctuations (back-and-forth competition)
- **15+**: Chaotic (multiple momentum shifts)

## Use Cases for This Data

1. **Market Efficiency Analysis**: Compare CV to actual game competitiveness
2. **Trading Strategy Development**: Identify patterns in volatile vs stable markets
3. **Risk Assessment**: CV as a proxy for prediction uncertainty
4. **Tournament Analysis**: Compare early rounds vs late rounds volatility
5. **Gender Comparison Studies**: Systematic differences in betting patterns
6. **Volume-Volatility Correlation**: Does higher volume predict stability?

## Data Quality Notes

- 1 game excluded (UTSA vs UConn Women's) due to incomplete outcome data
- All metrics calculated from 5-minute OHLC bars
- CV can be very high when mean probability is low (mathematical property)
- Forward-filled data may smooth out some short-term volatility
- Volume includes both sides of trades

## Files Referenced

- **Input:** `march_madness_odds_data/*.csv` (126 game files)
- **Output:** `odds_variability_analysis.csv`
- **Script:** `analyze_odds_variability.py`

## Column Reference

Full list of columns in `odds_variability_analysis.csv`:

1. slug
2. category
3. file_name
4. favorite
5. underdog
6. fav_mean_prob
7. fav_std_prob
8. fav_min_prob
9. fav_max_prob
10. fav_prob_range
11. fav_cv
12. fav_direction_changes
13. fav_max_jump
14. fav_avg_abs_change
15. fav_start_prob
16. fav_end_prob
17. fav_total_change
18. fav_pct_active
19. fav_total_volume
20. und_mean_prob
21. und_std_prob
22. und_min_prob
23. und_max_prob
24. und_prob_range
25. und_cv
26. und_direction_changes
27. und_max_jump
28. und_avg_abs_change
29. und_start_prob
30. und_end_prob
31. und_total_change
32. und_pct_active
33. und_total_volume
34. total_volume
35. total_intervals
36. time_span_hours
37. avg_combined_cv
38. max_cv
39. prob_spread_start
40. prob_spread_end
41. spread_change

## Future Analysis Ideas

- Correlation between CV and actual game scores
- Round-by-round volatility trends
- Pre-game vs in-game volatility comparison
- Team-specific volatility patterns
- Upset probability vs market volatility
- Time-of-day trading pattern analysis

---

**Generated:** May 19, 2026  
**Data Period:** March 19 - April 8, 2026  
**Source:** Polymarket prediction markets
