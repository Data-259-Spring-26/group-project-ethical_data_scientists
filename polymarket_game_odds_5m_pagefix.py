import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from zoneinfo import ZoneInfo


PAGE_SIZE = 1000
MAX_OFFSET = 10000
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
        print_available_markets(markets)
        raise ValueError("No matching market found.")

    return candidates[0]


def print_available_markets(markets: list[dict]) -> None:
    print("\nAvailable markets:")

    for i, m in enumerate(markets):
        print()
        print(f"[{i}]")
        print(f"question: {m.get('question')}")
        print(f"type: {m.get('sports_market_type')}")
        print(f"conditionId: {m.get('condition_id')}")
        print(f"outcomes: {m.get('outcomes')}")


def fetch_all_trades(condition_id: str) -> pd.DataFrame:
    """Fetch paged trades without prematurely stopping at 1,000 rows.

    The Data API can return 1,000 rows even when you request a larger limit.
    The old script used LIMIT=10000, got 1,000 rows, then stopped because
    1,000 < 10,000. That is why your CSV started late.
    """
    all_trades = []
    seen = set()

    for offset in range(0, MAX_OFFSET + 1, PAGE_SIZE):
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
        r.raise_for_status()

        batch = r.json()

        if not batch:
            print(f"Fetched 0 trades at offset {offset:,}; stopping.")
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
            f"Fetched {len(batch):,} trades at offset {offset:,} "
            f"({added:,} new). Total unique: {len(all_trades):,}"
        )

        if len(batch) < PAGE_SIZE:
            break

        time.sleep(SLEEP_SECONDS)

    df = pd.DataFrame(all_trades)

    if not df.empty and "timestamp" in df.columns:
        ts = pd.to_numeric(df["timestamp"], errors="coerce")
        dt = pd.to_datetime(ts, unit="s", utc=True)
        print()
        print(f"Raw API visible trade range UTC: {dt.min()} to {dt.max()}")

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
        print("No trades found inside the requested time window.")
        print(f"Requested local window: {start_local} to {end_local}")
        print(f"Requested UTC window:   {start_utc} to {end_utc}")
        print()
        print("Available trade range from API:")
        print(f"First trade UTC: {df['datetime_utc'].min()}")
        print(f"Last trade UTC:  {df['datetime_utc'].max()}")
        print(f"First trade ET:  {df['datetime_et'].min()}")
        print(f"Last trade ET:   {df['datetime_et'].max()}")
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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--event",
        required=True,
        help="Polymarket event URL or slug.",
    )
    parser.add_argument(
        "--start",
        required=True,
        help='Local start time, e.g. "2026-03-29 00:00:00".',
    )
    parser.add_argument(
        "--end",
        required=True,
        help='Local end time, e.g. "2026-03-30 00:00:00".',
    )
    parser.add_argument(
        "--timezone",
        default="America/New_York",
        help='IANA timezone. Default: "America/New_York".',
    )
    parser.add_argument(
        "--market-type",
        default="moneyline",
        help="Market type to select. Examples: moneyline, spread, total.",
    )
    parser.add_argument(
        "--market-query",
        default=None,
        help="Optional text filter for the market question.",
    )
    parser.add_argument(
        "--list-markets",
        action="store_true",
        help="List markets for the event and exit.",
    )
    parser.add_argument(
        "--outfile",
        default=None,
        help="Output CSV filename.",
    )
    parser.add_argument(
        "--no-fill-missing",
        action="store_true",
        help="Only output 5-minute intervals that had trades.",
    )

    args = parser.parse_args()

    slug = extract_slug(args.event)
    local_tz = ZoneInfo(args.timezone)

    start_local = pd.Timestamp(args.start, tz=local_tz)
    end_local = pd.Timestamp(args.end, tz=local_tz)

    if end_local <= start_local:
        raise ValueError(
            f"End time must be after start time. Got start={start_local}, end={end_local}"
        )

    print(f"Event slug: {slug}")
    print(f"Local window: {start_local} to {end_local}")
    print(f"UTC window:   {start_local.tz_convert('UTC')} to {end_local.tz_convert('UTC')}")

    event = get_event_by_slug(slug)
    markets = get_markets_from_event(event)

    if args.list_markets:
        print_available_markets(markets)
        return

    market = choose_market(
        markets=markets,
        market_type=args.market_type,
        market_query=args.market_query,
    )

    condition_id = market["condition_id"]

    print()
    print(f"Selected market: {market.get('question')}")
    print(f"Market type: {market.get('sports_market_type')}")
    print(f"Condition ID: {condition_id}")
    print(f"Outcomes: {market.get('outcomes')}")

    trades = fetch_all_trades(condition_id)

    if trades.empty:
        raise ValueError("No trades returned for this market.")

    tmp = trades.copy()
    if "timestamp" in tmp.columns:
        tmp["timestamp"] = pd.to_numeric(tmp["timestamp"], errors="coerce")
        tmp["datetime_utc"] = pd.to_datetime(tmp["timestamp"], unit="s", utc=True)
        oldest = tmp["datetime_utc"].min()
        newest = tmp["datetime_utc"].max()
        requested_start_utc = start_local.tz_convert("UTC")
        print()
        print(f"Visible trade range UTC: {oldest} to {newest}")
        if oldest > requested_start_utc:
            print("WARNING: Oldest visible trade is after requested start.")
            print(f"Requested start UTC: {requested_start_utc}")
            print(f"Oldest API trade UTC: {oldest}")
            print("If this still starts late after paging, the public endpoint is not exposing older trades for this market.")

    bars = make_complete_5m_bars(
        trades=trades,
        start_local=start_local,
        end_local=end_local,
        local_tz=local_tz,
        fill_missing=not args.no_fill_missing,
    )

    outfile = args.outfile or f"{slug}_{args.market_type}_5m_full.csv"
    bars.to_csv(outfile, index=False)

    print()
    print(f"Saved CSV: {Path(outfile).resolve()}")
    print(f"Rows: {len(bars):,}")
    print()
    print(bars.head(30).to_string(index=False))


if __name__ == "__main__":
    main()