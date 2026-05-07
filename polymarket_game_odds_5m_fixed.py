import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from zoneinfo import ZoneInfo


DATA_API_TRADES_URL = "https://data-api.polymarket.com/trades"
GAMMA_EVENT_SLUG_URL = "https://gamma-api.polymarket.com/events/slug/{slug}"

# Polymarket Data API docs currently cap both limit and offset at 10,000.
# With limit=10,000 and offset=10,000, the deepest page available is roughly
# the latest 20,000 records for a market. High-volume live sports can exceed
# that, so this script now detects truncation instead of silently creating a
# misleading CSV that starts late in the game.
LIMIT = 10000
MAX_OFFSET = 10000
SLEEP_SECONDS = 0.25


@dataclass
class CandidateResult:
    market: dict
    trades: pd.DataFrame
    window_count: int
    total_count: int
    first_utc: pd.Timestamp | None
    last_utc: pd.Timestamp | None
    first_local: pd.Timestamp | None
    last_local: pd.Timestamp | None
    likely_truncated_before_start: bool


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


def parse_local_timestamp(value: str, local_tz: ZoneInfo) -> pd.Timestamp:
    """Parse either naive local time or ISO timestamp with offset."""
    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        return ts.tz_localize(local_tz)

    return ts.tz_convert(local_tz)


def get_event_by_slug(slug: str) -> dict:
    r = requests.get(GAMMA_EVENT_SLUG_URL.format(slug=slug), timeout=30)
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


def filter_candidate_markets(
    markets: list[dict],
    market_type: str | None,
    market_query: str | None,
) -> list[dict]:
    candidates = markets

    if market_type:
        mt = market_type.lower().strip()
        candidates = [
            m for m in candidates
            if str(m.get("sports_market_type", "")).lower() == mt
        ]

    if market_query:
        q = market_query.lower().strip()
        candidates = [
            m for m in candidates
            if q in str(m.get("question", "")).lower()
        ]

    candidates = [m for m in candidates if m.get("condition_id")]

    if not candidates:
        print_available_markets(markets)
        raise ValueError("No matching market found. Use --list-markets or add --market-query.")

    return candidates


def print_available_markets(markets: list[dict]) -> None:
    print("\nAvailable markets:")

    for i, m in enumerate(markets):
        print()
        print(f"[{i}]")
        print(f"question: {m.get('question')}")
        print(f"slug: {m.get('slug')}")
        print(f"type: {m.get('sports_market_type')}")
        print(f"conditionId: {m.get('condition_id')}")
        print(f"outcomes: {m.get('outcomes')}")


def fetch_trades_page(condition_id: str, offset: int, taker_only: bool | None) -> list[dict]:
    params = {
        "market": condition_id,
        "limit": LIMIT,
        "offset": offset,
    }

    if taker_only is not None:
        params["takerOnly"] = str(taker_only).lower()

    r = requests.get(DATA_API_TRADES_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_trades(condition_id: str, taker_only: bool | None = None) -> pd.DataFrame:
    """Fetch all public Data API trades that the endpoint will expose.

    Important: the public docs cap offset at 10,000. This means we can usually
    fetch at most two 10k pages. For very active markets, older trades may be
    unreachable from this endpoint.
    """
    all_trades: list[dict] = []

    for offset in range(0, MAX_OFFSET + 1, LIMIT):
        batch = fetch_trades_page(condition_id, offset=offset, taker_only=taker_only)

        if not batch:
            break

        all_trades.extend(batch)
        print(f"Fetched {len(batch):,} trades at offset {offset:,}. Total: {len(all_trades):,}")

        if len(batch) < LIMIT:
            break

        time.sleep(SLEEP_SECONDS)

    return pd.DataFrame(all_trades)


def normalize_trades(trades: pd.DataFrame, local_tz: ZoneInfo) -> pd.DataFrame:
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

    # Defensive de-dupe. Data API paging can occasionally overlap at page edges.
    dedupe_cols = ["transactionHash", "asset", "outcome", "price", "size", "timestamp"]
    df = df.drop_duplicates(subset=[c for c in dedupe_cols if c in df.columns])

    return df.sort_values("datetime_utc")


def evaluate_candidate_market(
    market: dict,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    local_tz: ZoneInfo,
    taker_only: bool | None,
) -> CandidateResult:
    print()
    print(f"Checking market: {market.get('question')}")
    print(f"Condition ID: {market.get('condition_id')}")

    raw = fetch_all_trades(market["condition_id"], taker_only=taker_only)

    if raw.empty:
        return CandidateResult(
            market=market,
            trades=raw,
            window_count=0,
            total_count=0,
            first_utc=None,
            last_utc=None,
            first_local=None,
            last_local=None,
            likely_truncated_before_start=False,
        )

    df = normalize_trades(raw, local_tz=local_tz)
    window = df[(df["datetime_utc"] >= start_utc) & (df["datetime_utc"] < end_utc)]

    first_utc = df["datetime_utc"].min()
    last_utc = df["datetime_utc"].max()
    first_local = first_utc.tz_convert(local_tz)
    last_local = last_utc.tz_convert(local_tz)

    # If we hit the API's practical deepest page and the oldest visible trade is
    # still after the requested start, the endpoint almost certainly truncated
    # earlier trades away from us.
    likely_truncated = len(df) >= (LIMIT + 1) and first_utc > start_utc

    print(f"Visible trade range local: {first_local} to {last_local}")
    print(f"Visible trade count: {len(df):,}")
    print(f"Trades inside requested window: {len(window):,}")

    if likely_truncated:
        print("WARNING: oldest visible trade is after requested start; public Data API pagination likely truncated older trades.")

    return CandidateResult(
        market=market,
        trades=df,
        window_count=len(window),
        total_count=len(df),
        first_utc=first_utc,
        last_utc=last_utc,
        first_local=first_local,
        last_local=last_local,
        likely_truncated_before_start=likely_truncated,
    )


def pick_best_market_with_trades(
    candidates: list[dict],
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    local_tz: ZoneInfo,
    taker_only: bool | None,
) -> CandidateResult:
    results = [
        evaluate_candidate_market(
            market=m,
            start_utc=start_utc,
            end_utc=end_utc,
            local_tz=local_tz,
            taker_only=taker_only,
        )
        for m in candidates
    ]

    results = sorted(
        results,
        key=lambda r: (
            r.window_count,
            r.total_count,
            0 if r.first_utc is None else -abs((r.first_utc - start_utc).total_seconds()),
        ),
        reverse=True,
    )

    best = results[0]

    if best.window_count == 0:
        print_available_markets(candidates)
        raise ValueError("No candidate market has trades inside the requested window.")

    return best


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
    drop_flat_zero_volume: bool = False,
) -> pd.DataFrame:
    df = normalize_trades(trades, local_tz=local_tz) if "datetime_utc" not in trades.columns else trades.copy()

    start_utc = start_local.tz_convert("UTC")
    end_utc = end_local.tz_convert("UTC")

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

        bars["volume_shares"] = bars["volume_shares"].fillna(0)
        bars["trade_count"] = bars["trade_count"].fillna(0).astype(int)

        price_cols = ["open_prob", "high_prob", "low_prob", "close_prob"]
        for col in price_cols:
            bars[col] = bars.groupby("outcome")[col].ffill()

        bars = bars.dropna(subset=["close_prob"]).copy()
    else:
        bars = bars.dropna(subset=["close_prob"]).copy()
        bars["volume_shares"] = bars["volume_shares"].fillna(0)
        bars["trade_count"] = bars["trade_count"].fillna(0).astype(int)

    if drop_flat_zero_volume:
        price_cols = ["open_prob", "high_prob", "low_prob", "close_prob"]
        flat = bars[price_cols].nunique(axis=1).eq(1)
        zero_volume = bars["volume_shares"].eq(0)
        bars = bars[~(flat & zero_volume)].copy()

    bars["datetime_et"] = bars["datetime_utc"].dt.tz_convert(local_tz)

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

    parser.add_argument("--event", required=True, help="Polymarket event URL or slug.")
    parser.add_argument("--start", required=True, help='Local start time, e.g. "2026-03-29 00:00:00" or ISO with offset.')
    parser.add_argument("--end", required=True, help='Local end time, e.g. "2026-03-30 00:00:00" or ISO with offset.')
    parser.add_argument("--timezone", default="America/New_York", help='IANA timezone. Default: "America/New_York".')
    parser.add_argument("--market-type", default="moneyline", help="Market type to select. Examples: moneyline, spread, total.")
    parser.add_argument("--market-query", default=None, help="Optional text filter for the market question.")
    parser.add_argument("--list-markets", action="store_true", help="List markets for the event and exit.")
    parser.add_argument("--outfile", default=None, help="Output CSV filename.")
    parser.add_argument("--no-fill-missing", action="store_true", help="Only output 5-minute intervals that had trades.")
    parser.add_argument("--drop-flat-zero-volume", action="store_true", help="Drop forward-filled zero-volume flat candles from output.")
    parser.add_argument("--include-maker-trades", action="store_true", help="Set takerOnly=false on Data API requests.")
    parser.add_argument("--allow-truncated", action="store_true", help="Write CSV even when Data API likely cannot return older trades due pagination cap.")

    args = parser.parse_args()

    slug = extract_slug(args.event)
    local_tz = ZoneInfo(args.timezone)

    start_local = parse_local_timestamp(args.start, local_tz)
    end_local = parse_local_timestamp(args.end, local_tz)

    if end_local <= start_local:
        raise ValueError(f"End time must be after start time. Got start={start_local}, end={end_local}")

    start_utc = start_local.tz_convert("UTC")
    end_utc = end_local.tz_convert("UTC")

    print(f"Event slug: {slug}")
    print(f"Local window: {start_local} to {end_local}")
    print(f"UTC window:   {start_utc} to {end_utc}")

    event = get_event_by_slug(slug)
    markets = get_markets_from_event(event)

    if args.list_markets:
        print_available_markets(markets)
        return

    candidates = filter_candidate_markets(
        markets=markets,
        market_type=args.market_type,
        market_query=args.market_query,
    )

    print()
    print(f"Candidate markets after filters: {len(candidates)}")

    taker_only = False if args.include_maker_trades else None

    selected = pick_best_market_with_trades(
        candidates=candidates,
        start_utc=start_utc,
        end_utc=end_utc,
        local_tz=local_tz,
        taker_only=taker_only,
    )

    market = selected.market
    trades = selected.trades

    print()
    print("Selected market:")
    print(f"Question: {market.get('question')}")
    print(f"Slug: {market.get('slug')}")
    print(f"Market type: {market.get('sports_market_type')}")
    print(f"Condition ID: {market.get('condition_id')}")
    print(f"Outcomes: {market.get('outcomes')}")
    print(f"Visible trade range local: {selected.first_local} to {selected.last_local}")
    print(f"Visible trades: {selected.total_count:,}")
    print(f"Trades inside requested window: {selected.window_count:,}")

    if selected.likely_truncated_before_start and not args.allow_truncated:
        print()
        print("ERROR: This market appears truncated by the public Data API pagination cap.", file=sys.stderr)
        print(f"Requested start local: {start_local}", file=sys.stderr)
        print(f"Oldest visible trade:  {selected.first_local}", file=sys.stderr)
        print("The CSV would start late and be misleading, so I am refusing to write it.", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  1. Run with a narrower --start close to the oldest visible trade.", file=sys.stderr)
        print("  2. Add --allow-truncated if you knowingly want the partial Data API result.", file=sys.stderr)
        print("  3. Use an on-chain/indexer source for full historical raw trades.", file=sys.stderr)
        raise SystemExit(2)

    bars = make_complete_5m_bars(
        trades=trades,
        start_local=start_local,
        end_local=end_local,
        local_tz=local_tz,
        fill_missing=not args.no_fill_missing,
        drop_flat_zero_volume=args.drop_flat_zero_volume,
    )

    outfile = args.outfile or f"{slug}_{args.market_type}_5m_full.csv"
    bars.to_csv(outfile, index=False)

    print()
    print(f"Saved CSV: {Path(outfile).resolve()}")
    print(f"Rows: {len(bars):,}")
    print(f"Rows with trades: {(bars['trade_count'] > 0).sum():,}")
    print(f"Zero-volume rows: {(bars['volume_shares'] == 0).sum():,}")
    print()
    print(bars.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
