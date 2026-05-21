"""
Analyze odds variability across all March Madness games.

This script calculates various volatility metrics for each game's prediction market,
including standard deviation, range, coefficient of variation, and movement patterns.
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime


def calculate_variability_metrics(df: pd.DataFrame, outcome: str) -> dict:
    """
    Calculate comprehensive variability metrics for a single outcome.

    Metrics:
    - Standard deviation of close probabilities
    - Min/max range
    - Coefficient of variation (CV)
    - Number of direction changes
    - Largest single jump
    - Average absolute change between intervals
    """
    outcome_data = df[df['outcome'] == outcome].sort_values('datetime_utc')

    if outcome_data.empty:
        return None

    probs = outcome_data['close_prob'].values

    # Filter out any NaN values
    probs = probs[~np.isnan(probs)]

    if len(probs) < 2:
        return None

    # Basic statistics
    mean_prob = np.mean(probs)
    std_prob = np.std(probs)
    min_prob = np.min(probs)
    max_prob = np.max(probs)
    prob_range = max_prob - min_prob

    # Coefficient of variation (normalized volatility)
    cv = (std_prob / mean_prob * 100) if mean_prob > 0 else 0

    # Calculate changes between consecutive intervals
    changes = np.diff(probs)
    abs_changes = np.abs(changes)

    # Direction changes (how many times trend reversed)
    direction_changes = np.sum(np.diff(np.sign(changes)) != 0)

    # Largest single move
    max_jump = np.max(abs_changes) if len(abs_changes) > 0 else 0

    # Average absolute change
    avg_abs_change = np.mean(abs_changes) if len(abs_changes) > 0 else 0

    # Starting and ending probabilities
    start_prob = probs[0]
    end_prob = probs[-1]
    total_change = end_prob - start_prob

    # Count intervals with trades vs no trades
    intervals_with_trades = (outcome_data['trade_count'] > 0).sum()
    total_intervals = len(outcome_data)
    pct_active = (intervals_with_trades / total_intervals * 100) if total_intervals > 0 else 0

    # Volume statistics
    total_volume = outcome_data['volume_shares'].sum()
    avg_volume = outcome_data['volume_shares'].mean()

    return {
        'mean_prob': mean_prob,
        'std_prob': std_prob,
        'min_prob': min_prob,
        'max_prob': max_prob,
        'prob_range': prob_range,
        'coefficient_variation': cv,
        'direction_changes': direction_changes,
        'max_jump': max_jump,
        'avg_abs_change': avg_abs_change,
        'start_prob': start_prob,
        'end_prob': end_prob,
        'total_change': total_change,
        'total_intervals': total_intervals,
        'intervals_with_trades': intervals_with_trades,
        'pct_active_intervals': pct_active,
        'total_volume': total_volume,
        'avg_volume': avg_volume,
    }


def analyze_game_file(file_path: Path) -> dict:
    """Analyze a single game CSV file."""

    # Parse filename to extract metadata
    filename = file_path.stem
    parts = filename.split('_')

    # Extract slug (first part before underscore)
    slug = parts[0]

    # Determine category
    if slug.startswith('cbb-'):
        category = 'Mens'
    elif slug.startswith('cwbb-'):
        category = 'Womens'
    else:
        category = 'Unknown'

    # Read the CSV
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        return None

    if df.empty:
        return None

    # Get unique outcomes (teams)
    outcomes = df['outcome'].unique()

    if len(outcomes) != 2:
        print(f"Warning: {file_path.name} has {len(outcomes)} outcomes instead of 2")
        return None

    # Calculate metrics for each team
    team1_metrics = calculate_variability_metrics(df, outcomes[0])
    team2_metrics = calculate_variability_metrics(df, outcomes[1])

    if team1_metrics is None or team2_metrics is None:
        return None

    # Determine favorite (higher average probability)
    if team1_metrics['mean_prob'] > team2_metrics['mean_prob']:
        favorite = outcomes[0]
        underdog = outcomes[1]
        favorite_metrics = team1_metrics
        underdog_metrics = team2_metrics
    else:
        favorite = outcomes[1]
        underdog = outcomes[0]
        favorite_metrics = team2_metrics
        underdog_metrics = team1_metrics

    # Overall game metrics
    total_volume = team1_metrics['total_volume'] + team2_metrics['total_volume']
    total_trades = (df['trade_count'] > 0).sum()

    # Time range
    df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
    time_span_hours = (df['datetime_utc'].max() - df['datetime_utc'].min()).total_seconds() / 3600

    result = {
        'slug': slug,
        'category': category,
        'file_name': file_path.name,
        'favorite': favorite,
        'underdog': underdog,

        # Favorite metrics
        'fav_mean_prob': favorite_metrics['mean_prob'],
        'fav_std_prob': favorite_metrics['std_prob'],
        'fav_min_prob': favorite_metrics['min_prob'],
        'fav_max_prob': favorite_metrics['max_prob'],
        'fav_prob_range': favorite_metrics['prob_range'],
        'fav_cv': favorite_metrics['coefficient_variation'],
        'fav_direction_changes': favorite_metrics['direction_changes'],
        'fav_max_jump': favorite_metrics['max_jump'],
        'fav_avg_abs_change': favorite_metrics['avg_abs_change'],
        'fav_start_prob': favorite_metrics['start_prob'],
        'fav_end_prob': favorite_metrics['end_prob'],
        'fav_total_change': favorite_metrics['total_change'],
        'fav_pct_active': favorite_metrics['pct_active_intervals'],
        'fav_total_volume': favorite_metrics['total_volume'],

        # Underdog metrics
        'und_mean_prob': underdog_metrics['mean_prob'],
        'und_std_prob': underdog_metrics['std_prob'],
        'und_min_prob': underdog_metrics['min_prob'],
        'und_max_prob': underdog_metrics['max_prob'],
        'und_prob_range': underdog_metrics['prob_range'],
        'und_cv': underdog_metrics['coefficient_variation'],
        'und_direction_changes': underdog_metrics['direction_changes'],
        'und_max_jump': underdog_metrics['max_jump'],
        'und_avg_abs_change': underdog_metrics['avg_abs_change'],
        'und_start_prob': underdog_metrics['start_prob'],
        'und_end_prob': underdog_metrics['end_prob'],
        'und_total_change': underdog_metrics['total_change'],
        'und_pct_active': underdog_metrics['pct_active_intervals'],
        'und_total_volume': underdog_metrics['total_volume'],

        # Game-level metrics
        'total_volume': total_volume,
        'total_intervals': team1_metrics['total_intervals'],
        'time_span_hours': time_span_hours,
        'avg_combined_cv': (favorite_metrics['coefficient_variation'] + underdog_metrics['coefficient_variation']) / 2,
        'max_cv': max(favorite_metrics['coefficient_variation'], underdog_metrics['coefficient_variation']),
        'prob_spread_start': abs(favorite_metrics['start_prob'] - underdog_metrics['start_prob']),
        'prob_spread_end': abs(favorite_metrics['end_prob'] - underdog_metrics['end_prob']),
        'spread_change': abs(favorite_metrics['end_prob'] - underdog_metrics['end_prob']) -
                        abs(favorite_metrics['start_prob'] - underdog_metrics['start_prob']),
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Analyze odds variability across March Madness games"
    )

    parser.add_argument(
        "--data-dir",
        default="march_madness_odds_data",
        help="Directory containing game CSV files",
    )
    parser.add_argument(
        "--output",
        default="odds_variability_analysis.csv",
        help="Output CSV file name",
    )
    parser.add_argument(
        "--filter-category",
        choices=["Mens", "Womens"],
        help="Only analyze Mens or Womens games",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"Error: Directory {data_dir} does not exist")
        return

    # Find all game CSV files (exclude log files)
    game_files = [
        f for f in data_dir.glob("*.csv")
        if not f.name.startswith("batch_")
    ]

    print(f"Found {len(game_files)} game files to analyze")
    print(f"Analyzing variability metrics...\n")

    results = []

    for i, file_path in enumerate(game_files, 1):
        if i % 10 == 0:
            print(f"Processed {i}/{len(game_files)} files...")

        result = analyze_game_file(file_path)

        if result:
            # Apply category filter if specified
            if args.filter_category and result['category'] != args.filter_category:
                continue

            results.append(result)

    if not results:
        print("No results to save")
        return

    # Create DataFrame
    df_results = pd.DataFrame(results)

    # Sort by average CV (most volatile first)
    df_results = df_results.sort_values('avg_combined_cv', ascending=False)

    # Save to CSV
    output_path = Path(args.output)
    df_results.to_csv(output_path, index=False)

    print(f"\n{'='*80}")
    print("VARIABILITY ANALYSIS COMPLETE")
    print(f"{'='*80}")
    print(f"Games analyzed: {len(df_results)}")
    print(f"Output file: {output_path.resolve()}")
    print(f"Columns: {len(df_results.columns)}")
    print(f"\nTop 5 Most Volatile Games (by avg CV):")
    print("-" * 80)

    for idx, row in df_results.head(5).iterrows():
        print(f"\n{row['favorite']} vs {row['underdog']}")
        print(f"  Category: {row['category']}")
        print(f"  Average CV: {row['avg_combined_cv']:.2f}%")
        print(f"  Favorite prob range: {row['fav_prob_range']:.3f} ({row['fav_min_prob']:.3f} - {row['fav_max_prob']:.3f})")
        print(f"  Total volume: {row['total_volume']:,.0f} shares")

    print(f"\n{'='*80}")
    print("Summary Statistics:")
    print(f"{'='*80}")
    print(f"Mean CV across all games: {df_results['avg_combined_cv'].mean():.2f}%")
    print(f"Median CV: {df_results['avg_combined_cv'].median():.2f}%")
    print(f"Max CV: {df_results['max_cv'].max():.2f}%")
    print(f"Mean probability range: {df_results['fav_prob_range'].mean():.3f}")
    print(f"Mean total volume: {df_results['total_volume'].mean():,.0f} shares")

    if 'category' in df_results.columns:
        print(f"\nBy Category:")
        for cat in df_results['category'].unique():
            cat_data = df_results[df_results['category'] == cat]
            print(f"  {cat}: {len(cat_data)} games, avg CV = {cat_data['avg_combined_cv'].mean():.2f}%")


if __name__ == "__main__":
    main()
