"""Unit tests for api/services/nl_query.py — NL-to-SQL query service.

Pure static tests — Claude API calls and DB execution are mocked.
"""
from unittest.mock import MagicMock, patch


from api.services.nl_query import _generate_sql, run_nl_query


def _mock_db():
    return MagicMock()


def _mock_db_result(columns, rows):
    """Return a MagicMock that behaves like a SQLAlchemy result proxy."""
    result = MagicMock()
    result.keys.return_value = columns
    result.fetchall.return_value = rows
    return result


# ── _generate_sql ─────────────────────────────────────────────────────────────

def test_generate_sql_returns_none_when_no_api_key():
    with patch("api.services.llm._is_key_set", return_value=False):
        result = _generate_sql("List companies with high risk")
    assert result is None


def test_generate_sql_returns_sql_from_claude():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="SELECT * FROM companies ORDER BY risk_score DESC LIMIT 10")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with patch("api.services.llm._is_key_set", return_value=True):
        with patch("anthropic.Anthropic", return_value=mock_client):
            result = _generate_sql("Top 10 highest risk companies")

    assert result == "SELECT * FROM companies ORDER BY risk_score DESC LIMIT 10"


def test_generate_sql_returns_none_on_exception():
    with patch("api.services.llm._is_key_set", return_value=True):
        with patch("anthropic.Anthropic", side_effect=Exception("API error")):
            result = _generate_sql("any question")
    assert result is None


# ── run_nl_query — no SQL generated ───────────────────────────────────────────

def test_run_nl_query_returns_error_when_no_sql_generated():
    db = _mock_db()
    with patch("api.services.nl_query._generate_sql", return_value=None):
        result = run_nl_query("What are the top companies?", db)
    assert result["error"] is not None
    assert result["sql"] is None
    assert result["rows"] == []
    db.execute.assert_not_called()


# ── run_nl_query — SQL safety blocking ───────────────────────────────────────

def test_run_nl_query_blocks_non_select_sql():
    db = _mock_db()
    with patch("api.services.nl_query._generate_sql", return_value="INSERT INTO companies VALUES (1)"):
        result = run_nl_query("add a company", db)
    assert result["error"] is not None
    assert "SELECT" in result["error"]
    db.execute.assert_not_called()


def test_run_nl_query_blocks_delete_statement():
    db = _mock_db()
    with patch("api.services.nl_query._generate_sql", return_value="DELETE FROM companies WHERE orgnr='123'"):
        result = run_nl_query("remove company", db)
    assert result["error"] is not None
    db.execute.assert_not_called()


def test_run_nl_query_blocks_drop_embedded_in_select():
    # SQL starts with SELECT but contains DROP — must be blocked
    sql = "SELECT * FROM companies; DROP TABLE companies"
    db = _mock_db()
    with patch("api.services.nl_query._generate_sql", return_value=sql):
        result = run_nl_query("list companies", db)
    assert result["error"] is not None
    db.execute.assert_not_called()


def test_run_nl_query_blocks_update_statement():
    db = _mock_db()
    with patch("api.services.nl_query._generate_sql", return_value="UPDATE companies SET risk_score=0"):
        result = run_nl_query("clear risk", db)
    assert result["error"] is not None
    db.execute.assert_not_called()


def test_run_nl_query_blocks_truncate_statement():
    db = _mock_db()
    with patch("api.services.nl_query._generate_sql", return_value="TRUNCATE companies"):
        result = run_nl_query("clear table", db)
    assert result["error"] is not None
    db.execute.assert_not_called()


# ── run_nl_query — valid SELECT ───────────────────────────────────────────────

def test_run_nl_query_executes_valid_select_and_returns_rows():
    sql = "SELECT orgnr, navn, risk_score FROM companies ORDER BY risk_score DESC LIMIT 5"
    db = _mock_db()
    db.execute.return_value = _mock_db_result(
        ["orgnr", "navn", "risk_score"],
        [("123456789", "Test AS", 12), ("987654321", "Other AS", 8)],
    )
    with patch("api.services.nl_query._generate_sql", return_value=sql):
        result = run_nl_query("Top 5 riskiest companies", db)

    assert result["error"] is None
    assert result["sql"] == sql
    assert result["columns"] == ["orgnr", "navn", "risk_score"]
    assert len(result["rows"]) == 2
    assert result["rows"][0] == {"orgnr": "123456789", "navn": "Test AS", "risk_score": 12}


def test_run_nl_query_returns_empty_rows_for_no_results():
    sql = "SELECT orgnr FROM companies WHERE navn = 'Nonexistent'"
    db = _mock_db()
    db.execute.return_value = _mock_db_result(["orgnr"], [])
    with patch("api.services.nl_query._generate_sql", return_value=sql):
        result = run_nl_query("find nonexistent", db)

    assert result["error"] is None
    assert result["rows"] == []


def test_run_nl_query_select_is_case_insensitive():
    sql = "select orgnr from companies limit 1"
    db = _mock_db()
    db.execute.return_value = _mock_db_result(["orgnr"], [("123",)])
    with patch("api.services.nl_query._generate_sql", return_value=sql):
        result = run_nl_query("one company", db)
    assert result["error"] is None


def test_run_nl_query_select_with_leading_whitespace_is_allowed():
    sql = "  SELECT orgnr FROM companies LIMIT 1"
    db = _mock_db()
    db.execute.return_value = _mock_db_result(["orgnr"], [("123",)])
    with patch("api.services.nl_query._generate_sql", return_value=sql):
        result = run_nl_query("one company", db)
    assert result["error"] is None


# ── run_nl_query — SQL execution error ───────────────────────────────────────

def test_run_nl_query_returns_error_on_sql_execution_failure():
    sql = "SELECT * FROM nonexistent_table"
    db = _mock_db()
    db.execute.side_effect = Exception("relation does not exist")
    with patch("api.services.nl_query._generate_sql", return_value=sql):
        result = run_nl_query("query bad table", db)

    assert result["error"] is not None
    assert "SQL-feil" in result["error"]
    assert result["sql"] == sql
    assert result["rows"] == []
