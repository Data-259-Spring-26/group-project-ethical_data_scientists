import argparse
import json
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd
import requests


PAGE_SIZE = 1000
MAX_OFFSET = 4000  # API limit
SLEEP_SECONDS = 0.25


def extract_slug(event_url_or_slug: str) -> str:
    value = event_url_or_slug.strip()

    if value.startswith("http"):
        parsed = urlparse(value)
        parts = [p for p in parsed.path.split("/") if p]

        if "event" in parts:
            idx = parts.index("event")
            if idx + 1 < len(parts):
                return parts[idx + 1]

        return parts[-1]

    return value


def parse_jsonish(value):
    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value

    return value


def get_event_by_slug(slug: str) -> dict:
    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def get_markets_from_event(event: dict) -> list[dict]:
    markets = event.get("markets", [])

    if not markets:
        raise ValueError("No markets found on this event.")

    output = []

    for m in markets:
        output.append(
            {
                "question": m.get("question"),
                "slug": m.get("slug"),
                "condition_id": m.get("conditionId"),
                "sports_market_type": m.get("sportsMarketType"),
                "outcomes": parse_jsonish(m.get("outcomes")),
                "clob_token_ids": parse_jsonish(m.get("clobTokenIds")),
            }
        )

    return output


def choose_market(
    markets: list[dict],
    market_type: str | None,
    market_query: str | None,
) -> dict:
    candidates = markets

    if market_type:
        mt = market_type.lower()
        candidates = [
            m for m in candidates
            if str(m.get("sports_market_type", "")).lower() == mt
        ]

    if market_query:
        q = market_query.lower()
        candidates = [
            m for m in candidates
            if q in str(m.get("question", "")).lower()
        ]

    if not candidates:
        raise ValueError("No matching market found.")

    return candidates[0]


def fetch_all_trades(condition_id: str) -> pd.DataFrame:
    """Fetch paged trades with API limit handling (max offset ~4000)."""
    all_trades = []
    seen = set()

    for offset in range(0, MAX_OFFSET + 1, PAGE_SIZE):
        try:
            r = requests.get(
                "https://data-api.polymarket.com/trades",
                params={
                    "market": condition_id,
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "takerOnly": "true",
                },
                timeout=30,
            )

            # If we hit the offset limit, stop gracefully
            if r.status_code == 400:
                print(f"  Reached API offset limit at {offset:,}; stopping.")
                break

            r.raise_for_status()

            batch = r.json()

            if not batch:
                print(f"  Fetched 0 trades at offset {offset:,}; stopping.")
                break

            added = 0
            for t in batch:
                key = (
                    t.get("transactionHash"),
                    t.get("asset"),
                    t.get("outcome"),
                    t.get("timestamp"),
                    t.get("price"),
                    t.get("size"),
                )
                if key in seen:
                    continue
                seen.add(key)
                all_trades.append(t)
                added += 1

            print(
                f"  Fetched {len(batch):,} trades at offset {offset:,} "
                f"({added:,} new). Total unique: {len(all_trades):,}"
            )

            if len(batch) < PAGE_SIZE:
                break

            time.sleep(SLEEP_SECONDS)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print(f"  Reached API offset limit at {offset:,}; stopping.")
                break
            else:
                raise

    df = pd.DataFrame(all_trades)

    if not df.empty and "timestamp" in df.columns:
        ts = pd.to_numeric(df["timestamp"], errors="coerce")
        dt = pd.to_datetime(ts, unit="s", utc=True)
        print(f"  Raw API visible trade range UTC: {dt.min()} to {dt.max()}")

    return df


def implied_prob_to_american_odds(prob: float):
    if pd.isna(prob) or prob <= 0 or prob >= 1:
        return None

    if prob >= 0.5:
        return round(-100 * prob / (1 - prob))

    return round(100 * (1 - prob) / prob)


def make_complete_5m_bars(
    trades: pd.DataFrame,
    start_local: pd.Timestamp,
    end_local: pd.Timestamp,
    local_tz: ZoneInfo,
    fill_missing: bool = True,
) -> pd.DataFrame:
    required_cols = {
        "timestamp",
        "outcome",
        "price",
        "size",
        "side",
        "asset",
        "transactionHash",
    }

    missing = required_cols - set(trades.columns)

    if missing:
        raise ValueError(f"Missing expected columns: {missing}")

    df = trades.copy()

    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["size"] = pd.to_numeric(df["size"], errors="coerce")

    df = df.dropna(subset=["timestamp", "price", "size", "outcome"])

    if df.empty:
        raise ValueError("Trades were returned, but none had usable timestamp/price/size/outcome values.")

    df["datetime_utc"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df["datetime_et"] = df["datetime_utc"].dt.tz_convert(local_tz)

    start_utc = start_local.tz_convert("UTC")
    end_utc = end_local.tz_convert("UTC")

    # Keep only trades inside the requested time window.
    df_window = df[
        (df["datetime_utc"] >= start_utc) &
        (df["datetime_utc"] < end_utc)
    ].copy()

    if df_window.empty:
        print()
        print("  No trades found inside the requested time window.")
        print(f"  Requested local window: {start_local} to {end_local}")
        print(f"  Requested UTC window:   {start_utc} to {end_utc}")
        print()
        print("  Available trade range from API:")
        print(f"  First trade UTC: {df['datetime_utc'].min()}")
        print(f"  Last trade UTC:  {df['datetime_utc'].max()}")
        raise ValueError("No trades found inside the specified time window.")

    df_window = df_window.sort_values("datetime_utc")

    # Build raw 5-minute OHLC bars only where trades exist.
    bars = (
        df_window.set_index("datetime_utc")
        .groupby("outcome")
        .resample("5min")
        .agg(
            open_prob=("price", "first"),
            high_prob=("price", "max"),
            low_prob=("price", "min"),
            close_prob=("price", "last"),
            volume_shares=("size", "sum"),
            trade_count=("transactionHash", "count"),
        )
        .reset_index()
    )

    if fill_missing:
        # Complete grid: every 5-minute interval for every outcome.
        full_times = pd.date_range(
            start=start_utc,
            end=end_utc,
            freq="5min",
            inclusive="left",
        )

        outcomes = sorted(df_window["outcome"].dropna().unique())

        full_index = pd.MultiIndex.from_product(
            [outcomes, full_times],
            names=["outcome", "datetime_utc"],
        )

        bars = (
            bars.set_index(["outcome", "datetime_utc"])
            .reindex(full_index)
            .reset_index()
        )

        # Empty intervals have no trades.
        bars["volume_shares"] = bars["volume_shares"].fillna(0)
        bars["trade_count"] = bars["trade_count"].fillna(0).astype(int)

        # Forward-fill prices by outcome so every interval has the last known odds.
        price_cols = ["open_prob", "high_prob", "low_prob", "close_prob"]

        for col in price_cols:
            bars[col] = bars.groupby("outcome")[col].ffill()

        # Drop intervals before the first observed trade for each outcome.
        bars = bars.dropna(subset=["close_prob"]).copy()

    else:
        bars = bars.dropna(subset=["close_prob"]).copy()
        bars["volume_shares"] = bars["volume_shares"].fillna(0)
        bars["trade_count"] = bars["trade_count"].fillna(0).astype(int)

    bars["datetime_et"] = bars["datetime_utc"].dt.tz_convert(local_tz)

    # Odds conversions.
    for col in ["open_prob", "high_prob", "low_prob", "close_prob"]:
        bars[col.replace("_prob", "_american_odds")] = bars[col].apply(implied_prob_to_american_odds)
        bars[col.replace("_prob", "_decimal_odds")] = bars[col].apply(
            lambda p: round(1 / p, 4) if pd.notna(p) and p > 0 else None
        )

    bars = bars[
        [
            "datetime_et",
            "datetime_utc",
            "outcome",
            "open_prob",
            "high_prob",
            "low_prob",
            "close_prob",
            "open_american_odds",
            "high_american_odds",
            "low_american_odds",
            "close_american_odds",
            "open_decimal_odds",
            "high_decimal_odds",
            "low_decimal_odds",
            "close_decimal_odds",
            "volume_shares",
            "trade_count",
        ]
    ]

    return bars.sort_values(["datetime_utc", "outcome"])


def verify_output_file(file_path: Path, expected_rows_min: int = 10) -> dict:
    """Verify that an output CSV file is valid and contains data."""
    result = {
        "valid": False,
        "exists": False,
        "rows": 0,
        "outcomes": [],
        "time_range": None,
        "error": None,
    }

    try:
        if not file_path.exists():
            result["error"] = "File does not exist"
            return result

        result["exists"] = True

        df = pd.read_csv(file_path)
        result["rows"] = len(df)

        if df.empty:
            result["error"] = "File is empty"
            return result

        # Check for required columns
        required_cols = [
            "datetime_et", "datetime_utc", "outcome",
            "open_prob", "close_prob", "volume_shares"
        ]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            result["error"] = f"Missing columns: {missing}"
            return result

        # Check minimum rows
        if len(df) < expected_rows_min:
            result["error"] = f"Too few rows: {len(df)} < {expected_rows_min}"
            return result

        # Get outcomes
        result["outcomes"] = sorted(df["outcome"].unique().tolist())

        # Get time range
        if "datetime_et" in df.columns:
            result["time_range"] = f"{df['datetime_et'].min()} to {df['datetime_et'].max()}"

        result["valid"] = True

    except Exception as e:
        result["error"] = f"Exception: {str(e)}"

    return result


def process_single_game(
    slug: str,
    team1: str,
    team2: str,
    round_name: str,
    category: str,
    start_local: pd.Timestamp,
    end_local: pd.Timestamp,
    local_tz: ZoneInfo,
    market_type: str,
    output_dir: Path,
    fill_missing: bool = True,
) -> dict:
    """Process a single game and return result status."""

    result = {
        "slug": slug,
        "team1": team1,
        "team2": team2,
        "round": round_name,
        "category": category,
        "success": False,
        "output_file": None,
        "error": None,
        "rows": 0,
        "outcomes": [],
        "trades_fetched": 0,
        "verification": None,
    }

    try:
        print(f"\n{'='*80}")
        print(f"Processing: {team1} vs {team2} ({round_name} - {category})")
        print(f"Slug: {slug}")

        # Get event data
        event = get_event_by_slug(slug)
        markets = get_markets_from_event(event)

        # Choose market
        market = choose_market(
            markets=markets,
            market_type=market_type,
            market_query=None,
        )

        condition_id = market["condition_id"]

        print(f"Market: {market.get('question')}")
        print(f"Type: {market.get('sports_market_type')}")
        print(f"Outcomes: {market.get('outcomes')}")

        # Fetch trades
        trades = fetch_all_trades(condition_id)
        result["trades_fetched"] = len(trades)

        if trades.empty:
            result["error"] = "No trades returned"
            return result

        # Create 5-minute bars
        bars = make_complete_5m_bars(
            trades=trades,
            start_local=start_local,
            end_local=end_local,
            local_tz=local_tz,
            fill_missing=fill_missing,
        )

        result["rows"] = len(bars)
        result["outcomes"] = sorted(bars["outcome"].unique().tolist())

        # Save output
        safe_team1 = team1.replace("/", "-").replace(" ", "_")
        safe_team2 = team2.replace("/", "-").replace(" ", "_")
        filename = f"{slug}_{safe_team1}_vs_{safe_team2}_{market_type}_5m.csv"
        output_file = output_dir / filename

        bars.to_csv(output_file, index=False)
        result["output_file"] = str(output_file)

        # Verify output
        verification = verify_output_file(output_file)
        result["verification"] = verification

        if verification["valid"]:
            result["success"] = True
            print(f"✓ SUCCESS: Saved {len(bars):,} rows to {output_file.name}")
            print(f"  Outcomes: {result['outcomes']}")
            print(f"  Time range: {verification['time_range']}")
        else:
            result["error"] = f"Verification failed: {verification['error']}"
            print(f"✗ VERIFICATION FAILED: {result['error']}")

    except Exception as e:
        result["error"] = str(e)
        print(f"✗ ERROR: {result['error']}")

    return result


def save_progress_log(results: list[dict], log_file: Path):
    """Save progress log with all results."""
    df = pd.DataFrame(results)
    df.to_csv(log_file, index=False)
    print(f"\nProgress log saved: {log_file}")


def print_summary(results: list[dict]):
    """Print summary statistics."""
    print("\n" + "="*80)
    print("BATCH PROCESSING SUMMARY")
    print("="*80)

    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful

    print(f"Total games processed: {total}")
    print(f"Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")

    total_rows = sum(r["rows"] for r in results if r["success"])
    total_trades = sum(r["trades_fetched"] for r in results)

    print(f"\nTotal rows generated: {total_rows:,}")
    print(f"Total trades fetched: {total_trades:,}")

    if failed > 0:
        print(f"\nFailed games:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['team1']} vs {r['team2']}: {r['error']}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch process March Madness games from CSV"
    )

    parser.add_argument(
        "--csv",
        default="March_madness_url_organizer - Data.csv",
        help="Input CSV with game data",
    )
    parser.add_argument(
        "--output-dir",
        default="march_madness_odds_data",
        help="Output directory for CSV files",
    )
    parser.add_argument(
        "--start",
        required=True,
        help='Start time for all games, e.g. "2026-03-19 00:00:00"',
    )
    parser.add_argument(
        "--end",
        required=True,
        help='End time for all games, e.g. "2026-04-08 00:00:00"',
    )
    parser.add_argument(
        "--timezone",
        default="America/New_York",
        help='IANA timezone. Default: "America/New_York"',
    )
    parser.add_argument(
        "--market-type",
        default="moneyline",
        help="Market type to select (default: moneyline)",
    )
    parser.add_argument(
        "--filter-category",
        choices=["Mens", "Womens"],
        help="Only process Mens or Womens games",
    )
    parser.add_argument(
        "--filter-round",
        help="Only process specific round (e.g., 'First', 'Sweet 16')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of games to process (for testing)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between games (default: 1.0)",
    )
    parser.add_argument(
        "--no-fill-missing",
        action="store_true",
        help="Only output 5-minute intervals that had trades",
    )

    args = parser.parse_args()

    # Setup
    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    local_tz = ZoneInfo(args.timezone)
    start_local = pd.Timestamp(args.start, tz=local_tz)
    end_local = pd.Timestamp(args.end, tz=local_tz)

    # Load CSV
    print(f"Loading games from {csv_path}")
    df = pd.read_csv(csv_path)

    # Apply filters
    if args.filter_category:
        df = df[df["Mens/Womans"] == args.filter_category]
        print(f"Filtered to {args.filter_category} games: {len(df)} games")

    if args.filter_round:
        df = df[df["Round"] == args.filter_round]
        print(f"Filtered to {args.filter_round} round: {len(df)} games")

    if args.limit:
        df = df.head(args.limit)
        print(f"Limited to first {args.limit} games")

    print(f"\nTotal games to process: {len(df)}")
    print(f"Output directory: {output_dir.resolve()}")
    print(f"Time window: {start_local} to {end_local}")

    # Process each game
    results = []
    start_time = datetime.now()

    for idx, row in df.iterrows():
        game_num = idx + 1
        print(f"\n[{game_num}/{len(df)}] Starting...")

        result = process_single_game(
            slug=row["URL Slug"],
            team1=row["Team 1"],
            team2=row["Team 2"],
            round_name=row["Round"],
            category=row["Mens/Womans"],
            start_local=start_local,
            end_local=end_local,
            local_tz=local_tz,
            market_type=args.market_type,
            output_dir=output_dir,
            fill_missing=not args.no_fill_missing,
        )

        results.append(result)

        # Save progress after each game
        log_file = output_dir / "batch_progress_log.csv"
        save_progress_log(results, log_file)

        # Delay between games
        if game_num < len(df):
            time.sleep(args.delay)

    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time

    print_summary(results)
    print(f"\nTotal time: {duration}")
    print(f"Average time per game: {duration / len(df)}")

    # Save final log
    final_log = output_dir / f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    save_progress_log(results, final_log)


if __name__ == "__main__":
    main()
