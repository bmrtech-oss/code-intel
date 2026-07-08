from scripts.evaluate_graph_engines import render_markdown_table


def test_render_markdown_table_includes_expected_columns_and_values():
    results = [
        {
            "engine": "Memtrace",
            "avg_lookback_ms": 12.34,
            "avg_filter_ms": 56.78,
            "total_avg_ms": 69.12,
        }
    ]

    markdown = render_markdown_table(results)

    assert "| Engine | Avg Lookback (ms) | Avg Filter (ms) | Total Avg (ms) |" in markdown
    assert "| Memtrace | 12.34 | 56.78 | 69.12 |" in markdown
