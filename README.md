# Volatility Madness: March Madness Prediction Market Analysis

**DATA 259 Spring 2026 Group Project**

A comprehensive analysis of betting odds volatility across the 2026 NCAA Men's and Women's March Madness tournaments using Polymarket prediction market data.

## Project Overview

This project analyzes market volatility patterns across all March Madness games by tracking how betting odds changed in 5-minute intervals throughout each game. We use the **coefficient of variation (CV)** as our primary metric to identify which games had the most volatile prediction markets, normalized to allow fair comparison across games with different base probabilities.

### Key Findings

- Analyzed **126+ games** across both Men's and Women's tournaments
- Tracked **millions of trades** in 5-minute intervals
- Identified clear volatility patterns across tournament rounds
- Built an interactive bracket visualization showing which games were most unpredictable

## File Structure

```
group-project-ethical_data_scientists/
│
├── index.html                                    # Interactive bracket visualization
├── batch_process_march_madness_standalone.py    # Data collection script
├── analyze_odds_variability.py                  # Statistical analysis script
├── histogram.py                                 # Histogram generation (optional)
│
├── data/
│   ├── final_data/                              # Processed game data
│   │   ├── batch_progress_log.csv               # Processing status log
│   │   ├── batch_results_YYYYMMDD_HHMMSS.csv    # Processing summary
│   │   ├── cbb-*.csv                            # Men's tournament games (5min intervals)
│   │   └── cwbb-*.csv                           # Women's tournament games (5min intervals)
│   │
│   └── helper_data/
│       ├── March_madness_url_organizer - Data.csv   # Input game list
│       └── odds_variability_analysis.csv            # Calculated volatility metrics
│
└── archive/
    ├── REVIEW_SUMMARY.md                        # Literature review notes
    └── VARIABILITY_ANALYSIS.md                  # Analysis documentation
```

## Data Pipeline

### 1. Data Collection (`batch_process_march_madness_standalone.py`)

**Purpose:** Fetch historical betting data from Polymarket API for all March Madness games.

**How it works:**
1. Reads game list from CSV (`March_madness_url_organizer - Data.csv`)
2. For each game:
   - Fetches all trades from Polymarket API (paginated, max 4000 offset)
   - Aggregates trades into 5-minute OHLC (Open-High-Low-Close) bars
   - Forward-fills missing intervals to create complete time series
   - Converts probabilities to American and Decimal odds formats
   - Saves to individual CSV file per game

**Key Features:**
- **Time window:** March 19 - April 8, 2026 (entire tournament)
- **Sampling frequency:** 5-minute intervals
- **Market type:** Moneyline (who will win)
- **Error handling:** Progress logging, verification, retry logic

**Usage:**
```bash
python batch_process_march_madness_standalone.py \
  --csv "data/helper_data/March_madness_url_organizer - Data.csv" \
  --output-dir data/final_data \
  --start "2026-03-19 00:00:00" \
  --end "2026-04-08 00:00:00" \
  --timezone "America/New_York" \
  --market-type moneyline
```

**Output format per game:**
```csv
datetime_et,datetime_utc,outcome,open_prob,high_prob,low_prob,close_prob,
open_american_odds,high_american_odds,low_american_odds,close_american_odds,
open_decimal_odds,high_decimal_odds,low_decimal_odds,close_decimal_odds,
volume_shares,trade_count
```

### 2. Variability Analysis (`analyze_odds_variability.py`)

**Purpose:** Calculate comprehensive volatility metrics for each game.

**Metrics Calculated:**

#### Per Team (Favorite & Underdog):
- **Mean probability:** Average win probability over game duration
- **Standard deviation:** Absolute volatility of probabilities
- **Min/Max probability:** Probability range
- **Coefficient of Variation (CV):** `(std_dev / mean) × 100` - normalized volatility measure
- **Direction changes:** Number of times odds trend reversed
- **Max jump:** Largest single 5-minute probability change
- **Average absolute change:** Mean magnitude of interval-to-interval changes
- **Start/End probabilities:** Opening and closing odds
- **Total change:** Net probability shift over game
- **Active intervals %:** Proportion of 5-min periods with actual trades
- **Total volume:** Cumulative shares traded

#### Game-level:
- **Average CV:** Mean of favorite and underdog CVs (primary ranking metric)
- **Max CV:** Highest CV between the two teams
- **Spread change:** How much the probability gap changed from start to finish
- **Total volume:** Combined trading volume
- **Time span:** Duration of market activity

**Usage:**
```bash
python analyze_odds_variability.py \
  --data-dir data/final_data \
  --output data/helper_data/odds_variability_analysis.csv
```

**Why Coefficient of Variation?**

CV is superior to raw standard deviation because it normalizes volatility by the mean:
- A 5% std on a 50% probability (CV = 10%) is more volatile than 5% std on a 95% probability (CV = 5.3%)
- Allows fair comparison between heavy favorites and toss-up games
- Standard measure in financial volatility analysis

### 3. Interactive Visualization (`index.html`)

**Purpose:** Interactive March Madness bracket showing volatility patterns.

**Features:**
- **Toggle views:** Switch between CV values and actual odds
- **Color coding:** Games colored by volatility (blue = stable, red = chaotic)
- **Click for details:** Modal with full game statistics
- **Responsive design:** Works on desktop and mobile
- **Statistics panel:** Tournament-wide volatility summary

**Technologies:**
- Vanilla JavaScript (no dependencies)
- Embedded data (no external API calls)
- CSS Grid for bracket layout
- Responsive flex layouts

## Statistical Methodology

### 1. Data Preprocessing
- Raw trades aggregated into 5-minute OHLC bars
- Missing intervals forward-filled with last known odds
- Intervals before first trade excluded per outcome
- Probabilities validated (0 < p < 1)

### 2. Volatility Calculation
For each team in each game:

```python
# Standard deviation of closing probabilities
std_prob = np.std(close_probabilities)

# Mean probability
mean_prob = np.mean(close_probabilities)

# Coefficient of Variation (primary metric)
CV = (std_prob / mean_prob) × 100
```

### 3. Game Ranking
Games ranked by **average CV** (mean of both teams' CVs) to identify most volatile markets.

### 4. Category Analysis
- Men's vs Women's tournament comparison
- Round-by-round volatility patterns
- Favorite vs Underdog volatility differences

## Key Insights

### Volatility Patterns
1. **Later rounds tend to have higher volatility** - closer matchups = more uncertainty
2. **Underdog upsets show highest CVs** - markets struggle to price live momentum shifts
3. **Championship games stabilize** - more liquidity, more informed traders
4. **Women's tournament shows different patterns** - less market depth = higher baseline volatility

### Data Quality Considerations
- **5-minute sampling:** Captures most movements but may miss rapid spikes
- **Market efficiency:** Odds reflect trader sentiment, not objective probabilities
- **Liquidity effects:** Low-volume games may show artificial volatility
- **Selection bias:** Only games with sufficient trading data included

## Dependencies

### Python Scripts
```
pandas>=2.0.0
numpy>=1.24.0
requests>=2.28.0
```

Install with:
```bash
pip install pandas numpy requests
```

### Visualization
- Modern web browser (Chrome, Firefox, Safari, Edge)
- No external dependencies (standalone HTML file)

## Reproducing the Analysis

### Step 1: Collect Data
```bash
# Full tournament data collection
python batch_process_march_madness_standalone.py \
  --csv data/helper_data/March_madness_url_organizer\ -\ Data.csv \
  --output-dir data/final_data \
  --start "2026-03-19 00:00:00" \
  --end "2026-04-08 00:00:00" \
  --timezone "America/New_York" \
  --market-type moneyline

# Expected runtime: ~2-4 hours for 126 games
# Output: ~126 CSV files + progress logs
```

### Step 2: Analyze Volatility
```bash
# Calculate metrics for all games
python analyze_odds_variability.py \
  --data-dir data/final_data \
  --output data/helper_data/odds_variability_analysis.csv

# Expected runtime: ~1-2 minutes
# Output: Single CSV with all volatility metrics
```

### Step 3: View Results
```bash
# Open in browser
open index.html

# Or use a local server (recommended)
python -m http.server 8000
# Then visit: http://localhost:8000
```

## Data Sources

- **Polymarket API:** https://gamma-api.polymarket.com/
  - Public prediction market platform
  - No authentication required for historical data
  - Rate limits: ~1 request/250ms (respected by batch script)

- **Game List:** Manually curated from NCAA tournament brackets
  - Team names, rounds, Polymarket slugs
  - Both Men's and Women's tournaments

## Limitations

1. **Data represents market sentiment, not objective truth** - Odds reflect collective trader beliefs, which may include biases
2. **5-minute sampling may miss short-term spikes** - Some rapid movements could occur between intervals
3. **API offset limit (4000 records)** - Very high-volume games may have truncated history
4. **Single-season analysis** - Patterns may not generalize to other years
5. **Forward-filling assumption** - Assumes no trades = no odds change (reasonable for continuous markets)
6. **Coefficient of variation caveat** - Assumes odds movements are meaningful across probability ranges

## Future Work

- Multi-year analysis to identify consistent patterns
- Comparison with actual game outcomes (prediction accuracy)
- Machine learning models to predict volatility
- Real-time data collection during tournament
- Integration with play-by-play data to identify volatility drivers
- Alternative volatility measures (Bollinger Bands, ATR, etc.)

## Contributors

**Ethical Data Scientists**
- DATA 259 Spring 2026
- University of San Francisco

## License

Educational project - data sourced from public Polymarket API.

## Contact

For questions about this analysis, please refer to the course materials or contact the project team through the course portal.

---

**Last Updated:** May 2026  
**Tournament:** NCAA March Madness 2026 (Men's & Women's)  
**Data Period:** March 19 - April 8, 2026  
**Total Games Analyzed:** 126+  
**Total Data Points:** 100,000+ intervals
