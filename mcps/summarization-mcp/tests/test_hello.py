"""Hello unit test module."""

from summarization.hello import hello


def test_hello():
    """Test the hello function."""
    assert hello() == "Hello summarization"
