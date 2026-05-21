"""
Create histogram of average CV for Men's vs Women's games by rounds.
Based on the March Madness odds data.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def load_and_prepare_data():
    """Load the organizer data and variability analysis."""

    # Load the organizer to get round information
    organizer_df = pd.read_csv('data/helper_data/March_madness_url_organizer - Data.csv')

    # Load the variability analysis
    variability_df = pd.read_csv('data/helper_data/odds_variability_analysis.csv')

    # Merge on slug to get round information
    merged_df = variability_df.merge(
        organizer_df[['URL Slug', 'Round']],
        left_on='slug',
        right_on='URL Slug',
        how='left'
    )

    return merged_df

def create_histogram(df):
    """Create grouped bar chart showing average CV by round and gender."""

    # Map round names to standardized format
    round_mapping = {
        'First': '1st Round',
        'Second': '2nd Round',
        'Third': '3rd Round',
        'Fourth': '4th Round',
        'Elite Eight': '3rd Round',
        'Sweet Sixteen': '3rd Round',
        'Final Four': '4th Round',
        'Championship': '4th Round'
    }

    df['Round_Standardized'] = df['Round'].map(round_mapping)

    # Filter out any rows without round information
    df = df[df['Round_Standardized'].notna()]

    # Calculate average CV by category and round
    avg_cv_by_round = df.groupby(['category', 'Round_Standardized'])['avg_combined_cv'].mean().reset_index()

    # Prepare data for plotting
    rounds = ['1st Round', '2nd Round', '3rd Round', '4th Round']
    mens_data = []
    womens_data = []

    for round_name in rounds:
        mens_val = avg_cv_by_round[
            (avg_cv_by_round['category'] == 'Mens') &
            (avg_cv_by_round['Round_Standardized'] == round_name)
        ]['avg_combined_cv']

        womens_val = avg_cv_by_round[
            (avg_cv_by_round['category'] == 'Womens') &
            (avg_cv_by_round['Round_Standardized'] == round_name)
        ]['avg_combined_cv']

        mens_data.append(mens_val.values[0] if len(mens_val) > 0 else 0)
        womens_data.append(womens_val.values[0] if len(womens_val) > 0 else 0)

    # Create the grouped bar chart
    x = np.arange(len(rounds))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 7))

    bars1 = ax.bar(x - width/2, mens_data, width, label="Men's", color='#4472C4', alpha=0.8)
    bars2 = ax.bar(x + width/2, womens_data, width, label="Women's", color='#ED7D31', alpha=0.8)

    # Customize the plot
    ax.set_ylabel('Average Coefficient of Variation (%)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Tournament Round', fontsize=12, fontweight='bold')
    ax.set_title('Volatility (CV) Comparison: Men\'s vs Women\'s March Madness by Round',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(rounds)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels on top of bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}%',
                   ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    # Save the figure
    output_path = 'cv_histogram_by_round.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to: {output_path}")

    # Also display summary statistics
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print("\nAverage CV by Round and Gender:")
    print("-"*60)
    for i, round_name in enumerate(rounds):
        print(f"\n{round_name}:")
        print(f"  Men's:   {mens_data[i]:.2f}%")
        print(f"  Women's: {womens_data[i]:.2f}%")
        diff = mens_data[i] - womens_data[i]
        print(f"  Difference: {diff:+.2f}% ({'Men higher' if diff > 0 else 'Women higher'})")

    print("\n" + "="*60)
    print(f"Overall Men's Average CV:   {np.mean(mens_data):.2f}%")
    print(f"Overall Women's Average CV: {np.mean(womens_data):.2f}%")
    print("="*60)

    plt.show()

def main():
    print("Loading data...")
    df = load_and_prepare_data()

    print(f"Total games: {len(df)}")
    print(f"Games with round info: {df['Round'].notna().sum()}")
    print(f"\nBreakdown by category:")
    print(df['category'].value_counts())

    print("\nCreating histogram...")
    create_histogram(df)

if __name__ == "__main__":
    main()
