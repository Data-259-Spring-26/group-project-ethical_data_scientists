# Volatility Madness

[Website](https://variabilitymadness.lol)

---

## Project Structure

```
group-project-ethical_data_scientists/
│
├── batch_process_march_madness_standalone.py  # Main data collection script
├── analyze_odds_variability.py                # Volatility metrics calculation
├── histogram.py                               # Round-by-round visualization
├── index.html                                 # Interactive website
│
├── data/
│   ├── final_data/                           # Processed datasets
│   └── helper_data/                          # Organizer CSVs and analysis outputs
│
├── cv_histogram_by_round.png                 # Generated visualization
├── .gitignore
├── CNAME                                     # Custom domain configuration
└── README.md                                 # This file
```

---

## Installation

### Dependencies

- **pandas**: Data manipulation and CSV processing
- **numpy**: Numerical computations and statistical analysis
- **matplotlib**: Data visualization and histogram generation
- **requests**: HTTP requests to Polymarket API

---

## Usage

### Data Collection

The `batch_process_march_madness_standalone.py` script fetches betting odds data from the Polymarket API at 5-minute intervals for specified games.

#### Basic Usage

```bash
python batch_process_march_madness_standalone.py \
  --csv "March_madness_url_organizer - Data.csv" \
  --output-dir "march_madness_odds_data" \
  --start "2026-03-19 00:00:00" \
  --end "2026-04-08 00:00:00" \
  --timezone "America/New_York" \
  --market-type "moneyline"
```

#### Parameters


| Parameter           | Description                           | Default                                  | Required |
| ------------------- | ------------------------------------- | ---------------------------------------- | -------- |
| `--csv`             | Input CSV with game URLs and metadata | `March_madness_url_organizer - Data.csv` | No       |
| `--output-dir`      | Directory for output CSV files        | `march_madness_odds_data`                | No       |
| `--start`           | Start timestamp (local time)          | -                                        | Yes      |
| `--end`             | End timestamp (local time)            | -                                        | Yes      |
| `--timezone`        | IANA timezone identifier              | `America/New_York`                       | No       |
| `--market-type`     | Market type to fetch                  | `moneyline`                              | No       |
| `--filter-category` | Filter by `Mens` or `Womens`          | None                                     | No       |
| `--filter-round`    | Filter by specific round              | None                                     | No       |
| `--limit`           | Limit number of games (testing)       | None                                     | No       |
| `--delay`           | Delay between API calls (seconds)     | `1.0`                                    | No       |
| `--no-fill-missing` | Don't forward-fill missing intervals  | False                                    | No       |


#### Output Format

Each game produces a CSV file with the following columns:

- `datetime_et` / `datetime_utc`: Timestamp in local and UTC
- `outcome`: Team name
- `open_prob`, `high_prob`, `low_prob`, `close_prob`: Probability values for 5-min interval
- `open_american_odds`, `close_american_odds`, etc.: American odds format
- `open_decimal_odds`, `close_decimal_odds`, etc.: Decimal odds format
- `volume_shares`: Trading volume in shares
- `trade_count`: Number of trades in interval

---

### Volatility Analysis

The `analyze_odds_variability.py` script calculates comprehensive volatility metrics for each game.

#### Basic Usage

```bash
python analyze_odds_variability.py \
  --data-dir "march_madness_odds_data" \
  --output "odds_variability_analysis.csv"
```

#### Calculated Metrics

The analysis generates 40+ metrics per game, including:

**Team Metrics:**

- Mean, standard deviation, min/max probability
- Coefficient of Variation (CV)
- Direction changes and maximum jumps
- Start/end probabilities and total change
- Trading volume and activity percentage

**Game-Level Metrics:**

- Total volume and time span
- Average combined CV and max CV
- Probability spread changes over time

---

## Data Pipeline

```
1. INPUT
   ├── March Madness URL organizer CSV
   │   └── Contains: game slugs, teams, rounds, gender category
   │
2. DATA COLLECTION (batch_process_march_madness_standalone.py)
   ├── Extract slug from URL/path
   ├── Fetch event data from Polymarket API
   ├── Select appropriate market (moneyline)
   ├── Fetch trades with pagination (up to 4000 offset limit)
   ├── Create 5-minute OHLC bars
   ├── Forward-fill missing intervals
   ├── Convert to American/Decimal odds
   └── Output: Individual game CSV files
   │
3. VALIDATION
   ├── Verify file exists and has data
   ├── Check for required columns
   ├── Validate minimum row count
   └── Log progress and errors
   │
4. VOLATILITY ANALYSIS (analyze_odds_variability.py)
   ├── Load all game CSVs
   ├── Calculate metrics per outcome (favorite/underdog)
   ├── Aggregate game-level statistics
   └── Output: odds_variability_analysis.csv
   │
5. VISUALIZATION
   ├── histogram.py → Round comparison charts
   └── index.html → Interactive bracket interface
```

---

## Methodology

We automated data collection from Polymarket prediction markets ([gamma-api.polymarket.com](http://gamma-api.polymarket.com)) in 5-minute intervals, looking specifically at the Moneyline (general outcome) markets published by Polymarket for march madness (all tournament rounds from Round of 64 through Championship). The data collection implemented logic to handle the 4000-record offset limit, a 0.25-second delay between requests to avoid rate limiting, and deduplication by transaction hash. 

After pulling the data, we then calculate the **Coefficient of Variation (CV), which is defined as

```
CV = (Standard Deviation of Probabilities / Mean Probability) × 100
```

CV normalizes volatility by the mean, making it comparable across different probability ranges. Other metrics which were calculated as supporting metrics and included in the detail view on the website for each game include:

- **Probability Range**: Max probability - Min probability
- **Direction Changes**: Number of trend reversals
- **Max Jump**: Largest single 5-minute probability change
- **Average Absolute Change**: Mean of |change| between intervals
- **Total Change**: End probability - Start probability
- **Activity Percentage**: % of intervals with actual trades

---

## Technologies

### Backend / Data Processing

- **Python 3.11+**: Core programming language
- **pandas**: Data manipulation and CSV processing
- **numpy**: Statistical computations
- **requests**: API communication
- **matplotlib**: Data visualization

### Frontend / Visualization

- **HTML5/CSS3**: Interactive website structure
- **JavaScript**: Dynamic bracket visualization
- **SVG**: Vector graphics for bracket layout

### APIs & Data Sources

- **Polymarket Gamma API**: Prediction market event data
- **Polymarket Data API**: Historical trade data

### Infrastructure

- **GitHub Pages**: Website hosting
- **Custom Domain**: variabilitymadness.lol

---

